-- Migration: Add organizations, super admin role, and team management
-- Created: 2024
-- Dependencies: Requires migrations/001_add_users_and_auth.sql to be run first

-- Update users table to support super_admin role
ALTER TABLE public.users 
DROP CONSTRAINT IF EXISTS users_role_check;

ALTER TABLE public.users 
ADD CONSTRAINT users_role_check CHECK (role IN ('customer', 'admin', 'super_admin'));

-- Create organizations table
CREATE TABLE IF NOT EXISTS public.organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  slug text NOT NULL UNIQUE, -- URL-friendly identifier
  description text,
  super_admin_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Create organization_members table (junction table)
CREATE TABLE IF NOT EXISTS public.organization_members (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'admin' CHECK (role IN ('admin', 'viewer')),
  invited_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  invited_at timestamptz,
  joined_at timestamptz,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(organization_id, user_id)
);

-- Add organization_id to tickets table
ALTER TABLE public.tickets 
ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id) ON DELETE SET NULL;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_organizations_super_admin_id ON public.organizations(super_admin_id);
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON public.organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organization_members_organization_id ON public.organization_members(organization_id);
CREATE INDEX IF NOT EXISTS idx_organization_members_user_id ON public.organization_members(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_organization_id ON public.tickets(organization_id);

-- Add comments for documentation
COMMENT ON TABLE public.organizations IS 'Organizations created by super admins. Each organization has one super admin.';
COMMENT ON TABLE public.organization_members IS 'Team members of organizations. Super admins can invite admins to their organization.';
COMMENT ON COLUMN public.organizations.super_admin_id IS 'The super admin who created and owns this organization.';
COMMENT ON COLUMN public.organization_members.role IS 'Role within the organization: admin (can manage tickets) or viewer (read-only).';

