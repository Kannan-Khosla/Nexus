"""RAG Knowledge Base router — upload, search, chat, analytics, and ticket tools."""

import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
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

    _log_kb_usage(
        [{"document_id": r.document_id, "chunk_id": r.chunk_id, "similarity": r.similarity} for r in results],
        None, "search",
    )

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

    _log_kb_usage(
        [{"document_id": s.document_id, "chunk_id": s.chunk_id, "similarity": s.similarity} for s in sources],
        None, "chat",
    )

    return ChatResponse(answer=answer, sources=sources)


# ------------------------------------------------------------------
# Ticket assist — RAG-powered response suggestion for agents
# ------------------------------------------------------------------
@router.post("/ticket-assist/{ticket_id}")
def ticket_assist(ticket_id: str, current_user: dict = Depends(get_current_admin)):
    """Search KB for a ticket's context and generate a suggested agent response."""
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

    confidence = float(parsed.get("confidence", 0.0))

    _log_kb_usage(sources, ticket_id, "ticket_assist", confidence)

    return {
        "suggested_response": parsed.get("suggested_response", ""),
        "confidence": confidence,
        "reasoning": parsed.get("reasoning", ""),
        "sources": sources,
        "ticket_id": ticket_id,
    }


# ------------------------------------------------------------------
# Usage logging helper
# ------------------------------------------------------------------
def _log_kb_usage(
    sources: list[dict],
    ticket_id: str | None,
    query_type: str,
    confidence: float | None = None,
):
    """Fire-and-forget: log which KB chunks were matched."""
    try:
        rows = []
        for src in sources:
            rows.append({
                "document_id": src.get("document_id"),
                "chunk_id": src.get("chunk_id"),
                "ticket_id": ticket_id,
                "query_type": query_type,
                "similarity_score": src.get("similarity"),
                "confidence_score": confidence,
            })
        if rows:
            supabase.table("kb_usage_logs").insert(rows).execute()
    except Exception as e:
        logger.debug(f"KB usage logging failed (non-fatal): {e}")


# ------------------------------------------------------------------
# Auto-generate KB article from a resolved ticket
# ------------------------------------------------------------------
ARTICLE_GEN_PROMPT = (
    "You are a technical writer. Given a support ticket conversation (customer "
    "problem + agent resolution), write a clear, concise knowledge base article "
    "that would help future agents or customers with the same issue.\n\n"
    "Return JSON with:\n"
    "- title (string): a clear, searchable article title\n"
    "- content (string): the full article in markdown, including Problem, Solution, "
    "and any relevant notes\n"
    "- tags (array of strings): 3-5 relevant keyword tags"
)


@router.post("/generate-article/{ticket_id}")
def generate_article_from_ticket(
    ticket_id: str,
    auto_save: bool = Query(default=False),
    current_user: dict = Depends(get_current_admin),
):
    """Analyze a resolved ticket and generate a draft KB article."""
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

    conversation = "\n".join(
        f"[{m['sender']}]: {m['message']}" for m in messages_data
    )

    user_content = (
        f"Ticket Subject: {ticket.get('subject', 'N/A')}\n"
        f"Context: {ticket.get('context', 'N/A')}\n"
        f"Priority: {ticket.get('priority', 'N/A')}\n"
        f"Status: {ticket.get('status', 'N/A')}\n\n"
        f"Conversation:\n{conversation}"
    )

    try:
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": ARTICLE_GEN_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(completion.choices[0].message.content)
    except Exception as e:
        logger.error(f"Article generation failed: {e}", exc_info=True)
        raise HTTPException(502, f"AI generation failed: {e}")

    title = parsed.get("title", f"Article from ticket {ticket_id[:8]}")
    content = parsed.get("content", "")
    tags = parsed.get("tags", [])

    result = {
        "title": title,
        "content": content,
        "tags": tags,
        "source_ticket_id": ticket_id,
    }

    if auto_save and content.strip():
        chunks = chunk_text(content)
        doc_row = {
            "title": title,
            "source": "auto_generated",
            "file_name": None,
            "content_hash": content_hash(content),
            "total_chunks": len(chunks),
            "metadata": {"source_ticket_id": ticket_id, "tags": tags},
            "created_by": current_user["id"],
        }
        doc_result = supabase.table("knowledge_documents").insert(doc_row).execute()
        if doc_result.data:
            doc_id = doc_result.data[0]["id"]
            try:
                embeddings = embed_batch(chunks)
                chunk_rows = [
                    {
                        "document_id": doc_id,
                        "chunk_index": idx,
                        "content": c,
                        "token_count": count_tokens(c),
                        "embedding": emb,
                    }
                    for idx, (c, emb) in enumerate(zip(chunks, embeddings))
                ]
                supabase.table("document_chunks").insert(chunk_rows).execute()
            except Exception as e:
                logger.error(f"Embedding for auto-article failed: {e}")
            result["document_id"] = doc_id
            result["saved"] = True
        else:
            result["saved"] = False
    else:
        result["saved"] = False

    return result


# ------------------------------------------------------------------
# Similar ticket finder
# ------------------------------------------------------------------
def _ensure_ticket_embedding(ticket_id: str) -> list[float] | None:
    """Return the embedding for a ticket, creating it if needed."""
    existing = (
        supabase.table("ticket_embeddings")
        .select("embedding")
        .eq("ticket_id", ticket_id)
        .limit(1)
        .execute()
    )
    if existing.data and existing.data[0].get("embedding"):
        return existing.data[0]["embedding"]

    ticket_q = (
        supabase.table("tickets")
        .select("subject, context")
        .eq("id", ticket_id)
        .limit(1)
        .execute()
    )
    if not ticket_q.data:
        return None
    ticket = ticket_q.data[0]

    msgs_q = (
        supabase.table("messages")
        .select("sender, message")
        .eq("ticket_id", ticket_id)
        .eq("sender", "customer")
        .order("created_at")
        .limit(5)
        .execute()
    )
    customer_msgs = " ".join(m["message"] for m in (msgs_q.data or []))
    summary = f"{ticket.get('subject', '')} {ticket.get('context', '')} {customer_msgs}"[:1000]

    try:
        emb = embed_text(summary)
    except Exception as e:
        logger.error(f"Ticket embedding failed: {e}")
        return None

    supabase.table("ticket_embeddings").upsert({
        "ticket_id": ticket_id,
        "embedding": emb,
        "summary_text": summary[:500],
    }).execute()

    return emb


@router.post("/similar-tickets/{ticket_id}")
def find_similar_tickets(
    ticket_id: str,
    current_user: dict = Depends(get_current_admin),
):
    """Find resolved tickets similar to the given ticket."""
    emb = _ensure_ticket_embedding(ticket_id)
    if emb is None:
        raise HTTPException(404, "Ticket not found or embedding failed")

    rpc_result = supabase.rpc(
        "match_tickets",
        {
            "query_embedding": emb,
            "exclude_ticket_id": ticket_id,
            "match_count": 5,
            "match_threshold": 0.55,
        },
    ).execute()

    similar_ids = [r["ticket_id"] for r in (rpc_result.data or [])]
    similarity_map = {r["ticket_id"]: r["similarity"] for r in (rpc_result.data or [])}

    if not similar_ids:
        return {"similar_tickets": []}

    tickets_q = (
        supabase.table("tickets")
        .select("id, subject, context, status, priority, created_at")
        .in_("id", similar_ids)
        .execute()
    )

    results = []
    for t in (tickets_q.data or []):
        last_msg = (
            supabase.table("messages")
            .select("message, sender")
            .eq("ticket_id", t["id"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        resolution = ""
        if last_msg.data and last_msg.data[0].get("sender") in ("admin", "ai"):
            resolution = last_msg.data[0]["message"][:200]

        results.append({
            "ticket_id": t["id"],
            "subject": t.get("subject", ""),
            "context": t.get("context", ""),
            "status": t.get("status", ""),
            "priority": t.get("priority", ""),
            "created_at": t.get("created_at", ""),
            "similarity": round(similarity_map.get(t["id"], 0), 4),
            "resolution_preview": resolution,
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return {"similar_tickets": results}


# ------------------------------------------------------------------
# KB Health & Analytics
# ------------------------------------------------------------------
@router.get("/analytics")
def kb_analytics(current_user: dict = Depends(get_current_admin)):
    """Return KB health metrics: document stats, usage, gaps, stale docs."""
    docs_q = supabase.table("knowledge_documents").select(
        "id, title, source, total_chunks, created_at"
    ).execute()
    all_docs = docs_q.data or []

    chunks_q = supabase.table("document_chunks").select("id", count="exact").execute()
    total_chunks = chunks_q.count or 0

    usage_q = supabase.table("kb_usage_logs").select(
        "document_id, similarity_score, confidence_score, query_type, created_at"
    ).order("created_at", desc=True).limit(500).execute()
    usage_rows = usage_q.data or []

    doc_hit_count: dict[str, int] = {}
    doc_avg_similarity: dict[str, list[float]] = {}
    confidence_scores: list[float] = []
    low_confidence_count = 0
    query_type_counts: dict[str, int] = {}

    for row in usage_rows:
        did = row.get("document_id")
        if did:
            doc_hit_count[did] = doc_hit_count.get(did, 0) + 1
            sim = row.get("similarity_score")
            if sim is not None:
                doc_avg_similarity.setdefault(did, []).append(sim)

        conf = row.get("confidence_score")
        if conf is not None:
            confidence_scores.append(conf)
            if conf < 0.5:
                low_confidence_count += 1

        qt = row.get("query_type", "unknown")
        query_type_counts[qt] = query_type_counts.get(qt, 0) + 1

    doc_titles = {d["id"]: d["title"] for d in all_docs}

    top_documents = sorted(doc_hit_count.items(), key=lambda x: x[1], reverse=True)[:10]
    top_docs_list = [
        {
            "document_id": did,
            "title": doc_titles.get(did, "Unknown"),
            "hit_count": count,
            "avg_similarity": round(
                sum(doc_avg_similarity.get(did, [0])) / max(len(doc_avg_similarity.get(did, [1])), 1), 3
            ),
        }
        for did, count in top_documents
    ]

    referenced_ids = set(doc_hit_count.keys())
    stale_docs = [
        {"document_id": d["id"], "title": d["title"], "created_at": d["created_at"]}
        for d in all_docs
        if d["id"] not in referenced_ids
    ]

    auto_generated = [d for d in all_docs if d.get("source") == "auto_generated"]

    avg_confidence = (
        round(sum(confidence_scores) / len(confidence_scores), 3) if confidence_scores else None
    )

    return {
        "total_documents": len(all_docs),
        "total_chunks": total_chunks,
        "auto_generated_articles": len(auto_generated),
        "total_queries": len(usage_rows),
        "avg_confidence": avg_confidence,
        "low_confidence_queries": low_confidence_count,
        "query_type_breakdown": query_type_counts,
        "top_documents": top_docs_list,
        "stale_documents": stale_docs,
    }
