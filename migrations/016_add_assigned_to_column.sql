-- Migration: Add assigned_to column to tickets
-- Created: 2024
-- Description: Adds missing 'assigned_to' column to tickets table as text (stores email).

-- 1. Add 'assigned_to' column
ALTER TABLE public.tickets 
ADD COLUMN IF NOT EXISTS assigned_to text;

-- 2. Create index for filtering performance
CREATE INDEX IF NOT EXISTS idx_tickets_assigned_to ON public.tickets(assigned_to);
