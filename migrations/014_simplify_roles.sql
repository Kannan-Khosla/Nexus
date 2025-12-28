-- Migration: Simplify to Single-Role Admin System
-- Created: 2024
-- Description: Removes organizations, customers, super_admins. Enforces single 'admin' role.

-- 1. Drop Organization related tables
DROP TABLE IF EXISTS public.organization_members CASCADE;
DROP TABLE IF EXISTS public.organizations CASCADE;

-- 2. Update Tickets table
-- Remove organization_id column
ALTER TABLE public.tickets 
DROP COLUMN IF EXISTS organization_id;

-- 3. Update Users table
-- Remove old constraint
ALTER TABLE public.users 
DROP CONSTRAINT IF EXISTS users_role_check;

-- Update all existing users to 'admin'
UPDATE public.users SET role = 'admin';

-- Add new constraint enforcing only 'admin' role
ALTER TABLE public.users 
ADD CONSTRAINT users_role_check CHECK (role = 'admin');

-- Set default role to 'admin'
ALTER TABLE public.users 
ALTER COLUMN role SET DEFAULT 'admin';
