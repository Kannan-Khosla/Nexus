-- Migration: Fix missing columns and add ticket_summary view
-- Created: 2024
-- Description: Adds missing 'context' to tickets, 'confidence' to messages, and creates ticket_summary view.

-- 1. Add 'context' to tickets if missing
ALTER TABLE public.tickets 
ADD COLUMN IF NOT EXISTS context text;

-- 2. Add 'confidence' to messages if missing
ALTER TABLE public.messages 
ADD COLUMN IF NOT EXISTS confidence float;

-- 3. Create ticket_summary view
DROP VIEW IF EXISTS public.ticket_summary;

CREATE OR REPLACE VIEW public.ticket_summary AS
SELECT
    t.id AS ticket_id,
    t.context,
    t.subject,
    t.status,
    COUNT(m.id) AS total_messages,
    AVG(COALESCE(m.confidence, 0)) AS avg_confidence,
    t.updated_at
FROM
    public.tickets t
LEFT JOIN
    public.messages m ON t.id = m.ticket_id
GROUP BY
    t.id, t.context, t.subject, t.status, t.updated_at;

-- Grant permissions (since we disabled RLS, this might be redundant but safe)
GRANT SELECT ON public.ticket_summary TO anon, authenticated, service_role;
