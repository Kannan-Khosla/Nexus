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
