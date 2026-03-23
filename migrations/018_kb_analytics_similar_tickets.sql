-- ============================================================
-- KB usage tracking for analytics
-- ============================================================

CREATE TABLE IF NOT EXISTS kb_usage_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    document_id UUID REFERENCES knowledge_documents(id) ON DELETE SET NULL,
    chunk_id UUID,
    ticket_id UUID,
    query_type TEXT NOT NULL,
    similarity_score FLOAT,
    confidence_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_usage_document ON kb_usage_logs(document_id);
CREATE INDEX IF NOT EXISTS idx_kb_usage_created ON kb_usage_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_kb_usage_type ON kb_usage_logs(query_type);

-- ============================================================
-- Ticket embeddings for similar-ticket search
-- ============================================================

CREATE TABLE IF NOT EXISTS ticket_embeddings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticket_id UUID NOT NULL UNIQUE,
    embedding vector(1536),
    summary_text TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticket_emb_ticket ON ticket_embeddings(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_emb_vector ON ticket_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- Similarity search for tickets
CREATE OR REPLACE FUNCTION match_tickets(
    query_embedding vector(1536),
    exclude_ticket_id UUID,
    match_count INT DEFAULT 5,
    match_threshold FLOAT DEFAULT 0.6
)
RETURNS TABLE (
    ticket_id UUID,
    summary_text TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        te.ticket_id,
        te.summary_text,
        1 - (te.embedding <=> query_embedding) AS similarity
    FROM ticket_embeddings te
    WHERE te.ticket_id != exclude_ticket_id
      AND 1 - (te.embedding <=> query_embedding) > match_threshold
    ORDER BY te.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
