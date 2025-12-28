
-- Migration: Base Schema (Reconstructed)
-- Created: 2024 (Inferred)

-- Create tickets table
CREATE TABLE IF NOT EXISTS public.tickets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject text,
    status text NOT NULL DEFAULT 'open',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Create messages table
CREATE TABLE IF NOT EXISTS public.messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id uuid REFERENCES public.tickets(id) ON DELETE CASCADE,
    sender text NOT NULL CHECK (sender IN ('customer', 'ai', 'system')), 
    message text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Note: 'user_id' is added in 001
-- Note: 'priority', 'sla_id' added in 002
-- Note: 'source' added in 004
-- Note: 'is_deleted' added in 008
