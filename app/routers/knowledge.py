"""RAG Knowledge Base router — upload, search, and AI-powered chat."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional

from app.dependencies import get_current_admin
from app.supabase_config import supabase
from app.logger import setup_logger
from app.schemas import SearchRequest, ChatRequest, ChatResponse, SearchResultItem
from app.embedding_service import (
    embed_text,
    embed_batch,
    chunk_text,
    count_tokens,
    content_hash,
    extract_text_from_upload,
)
from app.helpers import client as openai_client

logger = setup_logger(__name__)
router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


# ------------------------------------------------------------------
# Upload a document → extract, chunk, embed, store
# ------------------------------------------------------------------
@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    source: Optional[str] = Form("manual"),
    current_user: dict = Depends(get_current_admin),
):
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(413, "File exceeds 20 MB limit")

    doc_title = title or file.filename or "Untitled"

    try:
        raw_text = extract_text_from_upload(file_bytes, file.filename or "file.txt")
    except Exception as e:
        logger.error(f"Text extraction failed: {e}", exc_info=True)
        raise HTTPException(422, f"Could not extract text from file: {e}")

    if not raw_text.strip():
        raise HTTPException(422, "Extracted text is empty")

    c_hash = content_hash(raw_text)
    chunks = chunk_text(raw_text)

    doc_row = {
        "title": doc_title,
        "source": source,
        "file_name": file.filename,
        "content_hash": c_hash,
        "total_chunks": len(chunks),
        "created_by": current_user["id"],
    }
    doc_result = supabase.table("knowledge_documents").insert(doc_row).execute()
    if not doc_result.data:
        raise HTTPException(500, "Failed to create document record")
    doc = doc_result.data[0]
    doc_id = doc["id"]

    try:
        embeddings = embed_batch(chunks)
    except Exception as e:
        supabase.table("knowledge_documents").delete().eq("id", doc_id).execute()
        logger.error(f"Embedding failed: {e}", exc_info=True)
        raise HTTPException(502, f"OpenAI embedding failed: {e}")

    chunk_rows = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        chunk_rows.append({
            "document_id": doc_id,
            "chunk_index": idx,
            "content": chunk,
            "token_count": count_tokens(chunk),
            "embedding": emb,
        })

    supabase.table("document_chunks").insert(chunk_rows).execute()

    logger.info(f"Document '{doc_title}' uploaded: {len(chunks)} chunks embedded")
    return {
        "id": doc_id,
        "title": doc_title,
        "chunks": len(chunks),
        "content_hash": c_hash,
    }


# ------------------------------------------------------------------
# List all knowledge-base documents
# ------------------------------------------------------------------
@router.get("/documents")
def list_documents(current_user: dict = Depends(get_current_admin)):
    result = (
        supabase.table("knowledge_documents")
        .select("id, title, source, file_name, total_chunks, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return {"documents": result.data or []}


# ------------------------------------------------------------------
# Delete a document and its chunks
# ------------------------------------------------------------------
@router.delete("/documents/{document_id}")
def delete_document(document_id: str, current_user: dict = Depends(get_current_admin)):
    existing = (
        supabase.table("knowledge_documents")
        .select("id")
        .eq("id", document_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(404, "Document not found")

    supabase.table("document_chunks").delete().eq("document_id", document_id).execute()
    supabase.table("knowledge_documents").delete().eq("id", document_id).execute()
    return {"deleted": document_id}


# ------------------------------------------------------------------
# Semantic search
# ------------------------------------------------------------------
@router.post("/search")
def search_knowledge(body: SearchRequest, current_user: dict = Depends(get_current_admin)):
    query_vec = embed_text(body.query)

    rpc_result = supabase.rpc(
        "match_chunks",
        {
            "query_embedding": query_vec,
            "match_count": body.top_k,
            "match_threshold": body.threshold,
        },
    ).execute()

    rows = rpc_result.data or []

    doc_ids = list({r["document_id"] for r in rows})
    titles_map: dict[str, str] = {}
    if doc_ids:
        docs = (
            supabase.table("knowledge_documents")
            .select("id, title")
            .in_("id", doc_ids)
            .execute()
        )
        titles_map = {d["id"]: d["title"] for d in (docs.data or [])}

    results = [
        SearchResultItem(
            chunk_id=r["id"],
            document_id=r["document_id"],
            document_title=titles_map.get(r["document_id"]),
            content=r["content"],
            similarity=round(r["similarity"], 4),
        )
        for r in rows
    ]
    return {"results": results}


# ------------------------------------------------------------------
# RAG chat — search → augment → generate
# ------------------------------------------------------------------
RAG_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question based ONLY on the "
    "provided context excerpts. If the context does not contain enough information, "
    "say so honestly. Cite the source document titles when possible."
)

TICKET_ASSIST_SYSTEM_PROMPT = (
    "You are an expert support agent assistant. A customer has submitted a support "
    "ticket and a human agent needs help crafting the best response.\n\n"
    "You will receive:\n"
    "1. The ticket subject and customer messages\n"
    "2. Relevant excerpts from the company's internal knowledge base\n\n"
    "Your job:\n"
    "- Write a professional, empathetic response the agent can send to the customer\n"
    "- Ground your answer in the knowledge base excerpts when available\n"
    "- Be specific and actionable — give concrete steps, not vague advice\n"
    "- Keep the tone warm but professional\n"
    "- If the knowledge base doesn't cover the issue, say so and suggest next steps\n\n"
    "Return JSON with fields:\n"
    "- suggested_response (string): the full response text ready to send\n"
    "- confidence (float 0-1): how confident you are this resolves the issue\n"
    "- reasoning (string): brief explanation of why you chose this approach"
)


@router.post("/chat", response_model=ChatResponse)
def chat_with_knowledge(body: ChatRequest, current_user: dict = Depends(get_current_admin)):
    query_vec = embed_text(body.question)

    rpc_result = supabase.rpc(
        "match_chunks",
        {
            "query_embedding": query_vec,
            "match_count": body.top_k,
            "match_threshold": 0.65,
        },
    ).execute()

    rows = rpc_result.data or []

    doc_ids = list({r["document_id"] for r in rows})
    titles_map: dict[str, str] = {}
    if doc_ids:
        docs = (
            supabase.table("knowledge_documents")
            .select("id, title")
            .in_("id", doc_ids)
            .execute()
        )
        titles_map = {d["id"]: d["title"] for d in (docs.data or [])}

    context_block = "\n\n---\n\n".join(
        f"[{titles_map.get(r['document_id'], 'Unknown')}]\n{r['content']}"
        for r in rows
    )

    if not context_block.strip():
        context_block = "(No relevant documents found in the knowledge base.)"

    messages = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context:\n{context_block}\n\nQuestion: {body.question}",
        },
    ]

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
    )
    answer = completion.choices[0].message.content

    sources = [
        SearchResultItem(
            chunk_id=r["id"],
            document_id=r["document_id"],
            document_title=titles_map.get(r["document_id"]),
            content=r["content"],
            similarity=round(r["similarity"], 4),
        )
        for r in rows
    ]

    return ChatResponse(answer=answer, sources=sources)


# ------------------------------------------------------------------
# Ticket assist — RAG-powered response suggestion for agents
# ------------------------------------------------------------------
@router.post("/ticket-assist/{ticket_id}")
def ticket_assist(ticket_id: str, current_user: dict = Depends(get_current_admin)):
    """Search KB for a ticket's context and generate a suggested agent response."""
    import json

    ticket_q = (
        supabase.table("tickets")
        .select("id, subject, context, status, priority")
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
    messages_data = msgs_q.data or []

    customer_msgs = [m["message"] for m in messages_data if m.get("sender") == "customer"]
    search_text = f"{ticket.get('subject', '')} {' '.join(customer_msgs[:5])}"

    try:
        query_vec = embed_text(search_text[:1000])
    except Exception as e:
        logger.error(f"Embedding failed for ticket assist: {e}")
        raise HTTPException(502, f"Embedding failed: {e}")

    rpc_result = supabase.rpc(
        "match_chunks",
        {
            "query_embedding": query_vec,
            "match_count": 6,
            "match_threshold": 0.55,
        },
    ).execute()
    rows = rpc_result.data or []

    doc_ids = list({r["document_id"] for r in rows})
    titles_map: dict[str, str] = {}
    if doc_ids:
        docs = (
            supabase.table("knowledge_documents")
            .select("id, title")
            .in_("id", doc_ids)
            .execute()
        )
        titles_map = {d["id"]: d["title"] for d in (docs.data or [])}

    context_block = "\n\n---\n\n".join(
        f"[{titles_map.get(r['document_id'], 'Unknown')}]\n{r['content']}"
        for r in rows
    )
    if not context_block.strip():
        context_block = "(No relevant documents found in the knowledge base.)"

    ticket_block = f"Subject: {ticket.get('subject', 'N/A')}\nContext: {ticket.get('context', 'N/A')}\nPriority: {ticket.get('priority', 'N/A')}"
    customer_block = "\n".join(f"- {m}" for m in customer_msgs[:5]) or "(No customer messages)"

    user_content = (
        f"Ticket details:\n{ticket_block}\n\n"
        f"Customer messages:\n{customer_block}\n\n"
        f"Knowledge base excerpts:\n{context_block}"
    )

    try:
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": TICKET_ASSIST_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content
        parsed = json.loads(raw)
    except Exception as e:
        logger.error(f"Ticket assist LLM call failed: {e}", exc_info=True)
        raise HTTPException(502, f"AI generation failed: {e}")

    sources = [
        {
            "chunk_id": r["id"],
            "document_id": r["document_id"],
            "document_title": titles_map.get(r["document_id"], "Unknown"),
            "content": r["content"],
            "similarity": round(r["similarity"], 4),
        }
        for r in rows
    ]

    return {
        "suggested_response": parsed.get("suggested_response", ""),
        "confidence": float(parsed.get("confidence", 0.0)),
        "reasoning": parsed.get("reasoning", ""),
        "sources": sources,
        "ticket_id": ticket_id,
    }
