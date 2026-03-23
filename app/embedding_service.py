"""Embedding, chunking, and document text extraction for RAG and compliance."""

import hashlib
import io
from typing import Optional

import tiktoken
from openai import OpenAI

from app.config import settings
from app.logger import setup_logger

logger = setup_logger(__name__)

_client = OpenAI(api_key=settings.openai_api_key)
_encoder = tiktoken.encoding_for_model("gpt-4o-mini")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def embed_text(text: str) -> list[float]:
    """Return a 1536-dim embedding vector for *text*."""
    resp = _client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return resp.data[0].embedding


def embed_batch(texts: list[str], batch_size: int = 512) -> list[list[float]]:
    """Embed a list of texts, splitting into sub-batches if needed."""
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = _client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        all_embeddings.extend([d.embedding for d in resp.data])
    return all_embeddings


def count_tokens(text: str) -> int:
    return len(_encoder.encode(text))


def chunk_text(
    text: str,
    max_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[str]:
    """Split *text* into overlapping token-window chunks."""
    tokens = _encoder.encode(text)
    if len(tokens) <= max_tokens:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(_encoder.decode(chunk_tokens))
        if end >= len(tokens):
            break
        start += max_tokens - overlap_tokens
    return chunks


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def extract_text_from_upload(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from PDF, DOCX, or TXT uploads."""
    lower = filename.lower()

    if lower.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    elif lower.endswith((".docx", ".doc")):
        return _extract_docx(file_bytes)
    elif lower.endswith((".txt", ".md", ".csv")):
        return file_bytes.decode("utf-8", errors="replace")
    else:
        return file_bytes.decode("utf-8", errors="replace")


def _extract_pdf(data: bytes) -> str:
    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
