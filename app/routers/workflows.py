"""Multi-agent workflow router — run analysis pipelines on tickets."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_admin
from app.supabase_config import supabase
from app.logger import setup_logger
from app.schemas import (
    ClassifierOutput,
    ResearcherOutput,
    DrafterOutput,
    ReviewerOutput,
    WorkflowAnalysisResponse,
    WorkflowStepResult,
)
from app.agent_orchestrator import AgentStep, run_pipeline
from app.embedding_service import embed_text

logger = setup_logger(__name__)
router = APIRouter(prefix="/workflows", tags=["Workflows"])


# ------------------------------------------------------------------
# Pipeline definition — 4 specialised agents
# ------------------------------------------------------------------
TICKET_PIPELINE = [
    AgentStep(
        name="Classifier",
        system_prompt=(
            "You are a ticket classifier. Analyze the support ticket and return JSON "
            "with: category (billing/technical/account/general/bug/feature_request), "
            "sentiment (positive/neutral/negative/frustrated), "
            "complexity (simple/moderate/complex), tags (array of relevant keyword tags)."
        ),
        output_model=ClassifierOutput,
    ),
    AgentStep(
        name="Researcher",
        system_prompt=(
            "You are a research agent. Given a support ticket and its classification, "
            "suggest a resolution strategy. Return JSON with: relevant_docs (array of "
            "objects with title and summary — leave empty if none), "
            "suggested_resolution (string with concrete steps), "
            "confidence (float 0-1 indicating how confident you are in the resolution)."
        ),
        output_model=ResearcherOutput,
    ),
    AgentStep(
        name="Drafter",
        system_prompt=(
            "You are a response drafter. Using the ticket details, classification, and "
            "research, draft a professional customer-facing response. Return JSON with: "
            "draft_response (the full response text), tone (empathetic/formal/friendly/technical), "
            "key_points (array of the main points addressed)."
        ),
        output_model=DrafterOutput,
    ),
    AgentStep(
        name="Reviewer",
        system_prompt=(
            "You are a quality reviewer. Review the drafted response for accuracy, tone, "
            "completeness, and professionalism. Return JSON with: approved (bool), "
            "feedback (string with specific improvement notes or 'Looks good'), "
            "revised_response (the improved version of the response), "
            "quality_score (float 0-1)."
        ),
        output_model=ReviewerOutput,
    ),
]


def _build_ticket_input(ticket: dict, messages: list[dict]) -> str:
    """Build a text summary of the ticket for the pipeline."""
    lines = [
        f"Subject: {ticket.get('subject', 'N/A')}",
        f"Context: {ticket.get('context', 'N/A')}",
        f"Priority: {ticket.get('priority', 'N/A')}",
        f"Status: {ticket.get('status', 'N/A')}",
        "",
        "Customer messages:",
    ]
    for msg in messages:
        if msg.get("sender") == "customer":
            lines.append(f"  - {msg.get('message', '')}")
    return "\n".join(lines)


def _get_rag_context(ticket: dict) -> str:
    """Optionally search the knowledge base for relevant context."""
    try:
        query = f"{ticket.get('subject', '')} {ticket.get('context', '')}"
        query_vec = embed_text(query)
        rpc = supabase.rpc(
            "match_chunks",
            {"query_embedding": query_vec, "match_count": 3, "match_threshold": 0.6},
        ).execute()
        if rpc.data:
            snippets = [r["content"] for r in rpc.data]
            return "Relevant knowledge base excerpts:\n" + "\n---\n".join(snippets)
    except Exception as e:
        logger.warning(f"RAG context lookup failed (non-fatal): {e}")
    return ""


# ------------------------------------------------------------------
# Run analysis on a ticket
# ------------------------------------------------------------------
@router.post("/analyze-ticket/{ticket_id}", response_model=WorkflowAnalysisResponse)
def analyze_ticket(ticket_id: str, current_user: dict = Depends(get_current_admin)):
    ticket_q = (
        supabase.table("tickets")
        .select("*")
        .eq("id", ticket_id)
        .limit(1)
        .execute()
    )
    if not ticket_q.data:
        raise HTTPException(404, "Ticket not found")
    ticket = ticket_q.data[0]

    msgs_q = (
        supabase.table("messages")
        .select("sender, message, created_at")
        .eq("ticket_id", ticket_id)
        .order("created_at")
        .execute()
    )
    messages = msgs_q.data or []

    analysis_row = {
        "ticket_id": ticket_id,
        "pipeline_name": "ticket_analysis",
        "status": "running",
        "steps": [],
        "started_by": current_user["id"],
    }
    insert = supabase.table("workflow_analyses").insert(analysis_row).execute()
    analysis_id = insert.data[0]["id"] if insert.data else None

    ticket_input = _build_ticket_input(ticket, messages)
    rag_context = _get_rag_context(ticket)

    step_results = run_pipeline(TICKET_PIPELINE, ticket_input, extra_context=rag_context)

    final_output = step_results[-1]["output"] if step_results else None

    if analysis_id:
        supabase.table("workflow_analyses").update({
            "status": "completed",
            "steps": step_results,
            "final_output": final_output,
            "completed_at": datetime.utcnow().isoformat(),
        }).eq("id", analysis_id).execute()

    return WorkflowAnalysisResponse(
        id=analysis_id or "unknown",
        ticket_id=ticket_id,
        pipeline_name="ticket_analysis",
        status="completed",
        steps=[
            WorkflowStepResult(
                agent_name=s["agent_name"],
                output=s["output"],
                duration_ms=s["duration_ms"],
            )
            for s in step_results
        ],
        final_output=final_output,
    )


# ------------------------------------------------------------------
# List / get analyses
# ------------------------------------------------------------------
@router.get("/analyses")
def list_analyses(current_user: dict = Depends(get_current_admin)):
    result = (
        supabase.table("workflow_analyses")
        .select("id, ticket_id, pipeline_name, status, started_at, completed_at")
        .order("started_at", desc=True)
        .limit(50)
        .execute()
    )
    return {"analyses": result.data or []}


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str, current_user: dict = Depends(get_current_admin)):
    result = (
        supabase.table("workflow_analyses")
        .select("*")
        .eq("id", analysis_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Analysis not found")
    return result.data[0]
