"""Compliance router — create requirement templates and evaluate documents."""

import json
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_admin
from app.supabase_config import supabase
from app.logger import setup_logger
from app.schemas import (
    ComplianceTemplateRequest,
    EvaluateRequest,
    RequirementResult,
    EvaluationResponse,
)
from app.embedding_service import embed_text
from app.helpers import client as openai_client

logger = setup_logger(__name__)
router = APIRouter(prefix="/compliance", tags=["Compliance"])

EVAL_SYSTEM_PROMPT = (
    "You are a compliance auditor. You will receive a requirement description and "
    "relevant excerpts from a document. Evaluate whether the document satisfies the "
    "requirement. Return JSON with fields: status (pass|fail|partial|not_applicable), "
    "reasoning (one sentence), confidence (float 0-1), evidence (quote from document "
    "or empty string)."
)


# ------------------------------------------------------------------
# Templates CRUD
# ------------------------------------------------------------------
@router.post("/templates")
def create_template(
    body: ComplianceTemplateRequest,
    current_user: dict = Depends(get_current_admin),
):
    row = {
        "name": body.name,
        "description": body.description,
        "requirements": [r.model_dump() for r in body.requirements],
        "created_by": current_user["id"],
    }
    result = supabase.table("compliance_templates").insert(row).execute()
    if not result.data:
        raise HTTPException(500, "Failed to create template")
    return result.data[0]


@router.get("/templates")
def list_templates(current_user: dict = Depends(get_current_admin)):
    result = (
        supabase.table("compliance_templates")
        .select("id, name, description, requirements, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return {"templates": result.data or []}


@router.get("/templates/{template_id}")
def get_template(template_id: str, current_user: dict = Depends(get_current_admin)):
    result = (
        supabase.table("compliance_templates")
        .select("*")
        .eq("id", template_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Template not found")
    return result.data[0]


# ------------------------------------------------------------------
# Evaluate a document against a template
# ------------------------------------------------------------------
@router.post("/evaluate", response_model=EvaluationResponse)
def evaluate_document(
    body: EvaluateRequest,
    current_user: dict = Depends(get_current_admin),
):
    tmpl = (
        supabase.table("compliance_templates")
        .select("*")
        .eq("id", body.template_id)
        .limit(1)
        .execute()
    )
    if not tmpl.data:
        raise HTTPException(404, "Template not found")
    template = tmpl.data[0]
    requirements = template["requirements"]

    doc = (
        supabase.table("knowledge_documents")
        .select("id, title")
        .eq("id", body.document_id)
        .limit(1)
        .execute()
    )
    if not doc.data:
        raise HTTPException(404, "Document not found in knowledge base")

    results: list[RequirementResult] = []
    pass_count = 0

    for req in requirements:
        query_text = f"{req['title']} {req['description']}"
        query_vec = embed_text(query_text)

        rpc = supabase.rpc(
            "match_chunks",
            {
                "query_embedding": query_vec,
                "match_count": 3,
                "match_threshold": 0.5,
            },
        ).execute()

        relevant_chunks = [
            r for r in (rpc.data or []) if r["document_id"] == body.document_id
        ]

        context = "\n\n".join(c["content"] for c in relevant_chunks) or "(No relevant sections found.)"

        try:
            completion = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": EVAL_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Requirement: {req['title']}\n"
                            f"Description: {req['description']}\n\n"
                            f"Document excerpts:\n{context}"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content
            parsed = json.loads(raw)
            result = RequirementResult(
                requirement_id=req["id"],
                status=parsed.get("status", "fail"),
                reasoning=parsed.get("reasoning", ""),
                confidence=float(parsed.get("confidence", 0.0)),
                evidence=parsed.get("evidence", ""),
            )
        except Exception as e:
            logger.error(f"Evaluation failed for requirement {req['id']}: {e}")
            result = RequirementResult(
                requirement_id=req["id"],
                status="fail",
                reasoning=f"Evaluation error: {e}",
                confidence=0.0,
            )

        if result.status in ("pass", "partial"):
            pass_count += 1
        results.append(result)

    total = len(requirements) or 1
    overall_score = round(pass_count / total, 2)

    summary_lines = [f"Overall compliance: {overall_score * 100:.0f}%"]
    fails = [r for r in results if r.status == "fail"]
    if fails:
        summary_lines.append(f"{len(fails)} requirement(s) failed.")
    summary = " ".join(summary_lines)

    eval_row = {
        "template_id": body.template_id,
        "document_id": body.document_id,
        "results": [r.model_dump() for r in results],
        "overall_score": overall_score,
        "summary": summary,
        "evaluated_by": current_user["id"],
    }
    insert = supabase.table("compliance_evaluations").insert(eval_row).execute()
    eval_id = insert.data[0]["id"] if insert.data else "unknown"

    return EvaluationResponse(
        id=eval_id,
        document_id=body.document_id,
        template_id=body.template_id,
        results=results,
        overall_score=overall_score,
        summary=summary,
    )


# ------------------------------------------------------------------
# List / get evaluations
# ------------------------------------------------------------------
@router.get("/evaluations")
def list_evaluations(current_user: dict = Depends(get_current_admin)):
    result = (
        supabase.table("compliance_evaluations")
        .select("id, template_id, document_id, overall_score, summary, evaluated_at")
        .order("evaluated_at", desc=True)
        .execute()
    )
    return {"evaluations": result.data or []}


@router.get("/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str, current_user: dict = Depends(get_current_admin)):
    result = (
        supabase.table("compliance_evaluations")
        .select("*")
        .eq("id", evaluation_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Evaluation not found")
    return result.data[0]
