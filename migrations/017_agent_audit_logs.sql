-- Migration: 017_agent_audit_logs
-- Description: Create audit log table to track AI agent policy decisions safely

CREATE TABLE IF NOT EXISTS public.agent_audit_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    action_type VARCHAR(255) NOT NULL,
    target_id VARCHAR(255) NOT NULL, -- Flexible ID (ticket ID, user ID, etc.)
    confidence_score NUMERIC(5, 4) NOT NULL,
    payload JSONB DEFAULT '{}'::jsonb,
    context JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) NOT NULL, -- e.g., 'approve', 'reject', 'escalate'
    reason TEXT, -- captures why a decision was rejected/escalated
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for querying recent rejected or escalated agent actions quickly
CREATE INDEX IF NOT EXISTS idx_agent_audit_logs_status ON public.agent_audit_logs(status);
CREATE INDEX IF NOT EXISTS idx_agent_audit_logs_target ON public.agent_audit_logs(target_id);
CREATE INDEX IF NOT EXISTS idx_agent_audit_logs_created_at ON public.agent_audit_logs(created_at DESC);

-- Optional RLS (Row Level Security) if you want only admins to see logs
ALTER TABLE public.agent_audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable read access for authenticated admins only" ON public.agent_audit_logs
    FOR SELECT
    USING (
      auth.role() = 'authenticated' -- You can refine this using your specific custom claims/roles check
    );
