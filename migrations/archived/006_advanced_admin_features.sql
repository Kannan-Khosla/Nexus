-- Migration: Add advanced admin features (teams, roles, custom fields, tags, automations, macros, etc.)
-- Created: 2024
-- Dependencies: Requires migrations/001_add_users_and_auth.sql and migrations/002_ticket_priorities_slas.sql to be run first

-- Create teams table
CREATE TABLE IF NOT EXISTS public.teams (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  description text,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL
);

-- Create roles table for role-based permissions
CREATE TABLE IF NOT EXISTS public.roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  description text,
  permissions_json jsonb NOT NULL DEFAULT '{}', -- JSON object with permission flags
  is_system_role boolean NOT NULL DEFAULT false, -- System roles cannot be deleted
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Create team_members table (many-to-many relationship)
CREATE TABLE IF NOT EXISTS public.team_members (
  team_id uuid NOT NULL REFERENCES public.teams(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'leader', 'manager')),
  joined_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (team_id, user_id)
);

-- Update users table to add new columns
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS role_id uuid REFERENCES public.roles(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS team_id uuid REFERENCES public.teams(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS avatar_url text,
ADD COLUMN IF NOT EXISTS phone text,
ADD COLUMN IF NOT EXISTS timezone text DEFAULT 'UTC';

-- Create tags table for ticket tagging
CREATE TABLE IF NOT EXISTS public.tags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  color text NOT NULL DEFAULT '#3B82F6', -- Hex color code
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL
);

-- Create ticket_tags table (many-to-many relationship)
CREATE TABLE IF NOT EXISTS public.ticket_tags (
  ticket_id uuid NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
  tag_id uuid NOT NULL REFERENCES public.tags(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  PRIMARY KEY (ticket_id, tag_id)
);

-- Create custom_fields table
CREATE TABLE IF NOT EXISTS public.custom_fields (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  field_name text NOT NULL UNIQUE,
  field_label text NOT NULL,
  field_type text NOT NULL CHECK (field_type IN ('text', 'textarea', 'number', 'date', 'datetime', 'select', 'multiselect', 'checkbox', 'url', 'email')),
  field_options jsonb, -- For select/multiselect options
  is_required boolean NOT NULL DEFAULT false,
  is_active boolean NOT NULL DEFAULT true,
  order_index integer NOT NULL DEFAULT 0,
  placeholder text,
  help_text text,
  validation_rules jsonb, -- JSON with validation rules (min, max, pattern, etc.)
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL
);

-- Create ticket_custom_fields table
CREATE TABLE IF NOT EXISTS public.ticket_custom_fields (
  ticket_id uuid NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
  custom_field_id uuid NOT NULL REFERENCES public.custom_fields(id) ON DELETE CASCADE,
  value text, -- Store as text, application layer handles type conversion
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (ticket_id, custom_field_id)
);

-- Create automation_rules table
CREATE TABLE IF NOT EXISTS public.automation_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  trigger_conditions jsonb NOT NULL, -- JSON with trigger conditions
  actions jsonb NOT NULL, -- JSON with actions to execute
  is_active boolean NOT NULL DEFAULT true,
  priority integer NOT NULL DEFAULT 0, -- Higher priority runs first
  run_count integer NOT NULL DEFAULT 0, -- Track how many times rule has run
  last_run_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL
);

-- Create macros table
CREATE TABLE IF NOT EXISTS public.macros (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  title text, -- Email subject or title
  description text,
  actions jsonb NOT NULL, -- JSON with macro actions (assign, status, reply, etc.)
  is_active boolean NOT NULL DEFAULT true,
  is_shared boolean NOT NULL DEFAULT false, -- Whether macro is shared with all agents
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL
);

-- Create canned_responses table
CREATE TABLE IF NOT EXISTS public.canned_responses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  content text NOT NULL, -- Response content
  category text,
  is_active boolean NOT NULL DEFAULT true,
  is_shared boolean NOT NULL DEFAULT false,
  usage_count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL
);

-- Create ticket_activities table for audit log
CREATE TABLE IF NOT EXISTS public.ticket_activities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id uuid NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
  user_id uuid REFERENCES public.users(id) ON DELETE SET NULL, -- Null for system actions
  action_type text NOT NULL CHECK (action_type IN ('created', 'updated', 'assigned', 'unassigned', 'status_changed', 'priority_changed', 'tag_added', 'tag_removed', 'custom_field_updated', 'merged', 'closed', 'reopened', 'note_added', 'escalated', 'deleted')),
  old_value text, -- JSON or text representation of old value
  new_value text, -- JSON or text representation of new value
  metadata jsonb, -- Additional metadata about the action
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Create ticket_merges table
CREATE TABLE IF NOT EXISTS public.ticket_merges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  primary_ticket_id uuid NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
  merged_ticket_id uuid NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
  merged_by uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  merge_reason text,
  merged_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(primary_ticket_id, merged_ticket_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_teams_name ON public.teams(name);
CREATE INDEX IF NOT EXISTS idx_teams_is_active ON public.teams(is_active);

CREATE INDEX IF NOT EXISTS idx_roles_name ON public.roles(name);
CREATE INDEX IF NOT EXISTS idx_roles_is_system_role ON public.roles(is_system_role);

CREATE INDEX IF NOT EXISTS idx_team_members_team_id ON public.team_members(team_id);
CREATE INDEX IF NOT EXISTS idx_team_members_user_id ON public.team_members(user_id);

CREATE INDEX IF NOT EXISTS idx_users_role_id ON public.users(role_id);
CREATE INDEX IF NOT EXISTS idx_users_team_id ON public.users(team_id);

CREATE INDEX IF NOT EXISTS idx_tags_name ON public.tags(name);
CREATE INDEX IF NOT EXISTS idx_tags_color ON public.tags(color);

CREATE INDEX IF NOT EXISTS idx_ticket_tags_ticket_id ON public.ticket_tags(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_tags_tag_id ON public.ticket_tags(tag_id);

CREATE INDEX IF NOT EXISTS idx_custom_fields_field_name ON public.custom_fields(field_name);
CREATE INDEX IF NOT EXISTS idx_custom_fields_field_type ON public.custom_fields(field_type);
CREATE INDEX IF NOT EXISTS idx_custom_fields_is_active ON public.custom_fields(is_active);
CREATE INDEX IF NOT EXISTS idx_custom_fields_order_index ON public.custom_fields(order_index);

CREATE INDEX IF NOT EXISTS idx_ticket_custom_fields_ticket_id ON public.ticket_custom_fields(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_custom_fields_custom_field_id ON public.ticket_custom_fields(custom_field_id);

CREATE INDEX IF NOT EXISTS idx_automation_rules_name ON public.automation_rules(name);
CREATE INDEX IF NOT EXISTS idx_automation_rules_is_active ON public.automation_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_automation_rules_priority ON public.automation_rules(priority);

CREATE INDEX IF NOT EXISTS idx_macros_name ON public.macros(name);
CREATE INDEX IF NOT EXISTS idx_macros_is_active ON public.macros(is_active);
CREATE INDEX IF NOT EXISTS idx_macros_is_shared ON public.macros(is_shared);
CREATE INDEX IF NOT EXISTS idx_macros_created_by ON public.macros(created_by);

CREATE INDEX IF NOT EXISTS idx_canned_responses_name ON public.canned_responses(name);
CREATE INDEX IF NOT EXISTS idx_canned_responses_category ON public.canned_responses(category);
CREATE INDEX IF NOT EXISTS idx_canned_responses_is_active ON public.canned_responses(is_active);
CREATE INDEX IF NOT EXISTS idx_canned_responses_is_shared ON public.canned_responses(is_shared);
CREATE INDEX IF NOT EXISTS idx_canned_responses_created_by ON public.canned_responses(created_by);

CREATE INDEX IF NOT EXISTS idx_ticket_activities_ticket_id ON public.ticket_activities(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_activities_user_id ON public.ticket_activities(user_id);
CREATE INDEX IF NOT EXISTS idx_ticket_activities_action_type ON public.ticket_activities(action_type);
CREATE INDEX IF NOT EXISTS idx_ticket_activities_created_at ON public.ticket_activities(created_at);

CREATE INDEX IF NOT EXISTS idx_ticket_merges_primary_ticket_id ON public.ticket_merges(primary_ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_merges_merged_ticket_id ON public.ticket_merges(merged_ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_merges_merged_by ON public.ticket_merges(merged_by);

-- Add comments for documentation
COMMENT ON TABLE public.teams IS 'Teams for organizing agents and ticket assignment';
COMMENT ON TABLE public.roles IS 'Role-based access control with JSON permissions';
COMMENT ON TABLE public.team_members IS 'Many-to-many relationship between teams and users';
COMMENT ON TABLE public.tags IS 'Tags for categorizing tickets';
COMMENT ON TABLE public.ticket_tags IS 'Many-to-many relationship between tickets and tags';
COMMENT ON TABLE public.custom_fields IS 'Custom field definitions for tickets';
COMMENT ON TABLE public.ticket_custom_fields IS 'Custom field values for specific tickets';
COMMENT ON TABLE public.automation_rules IS 'Automation rules with trigger conditions and actions';
COMMENT ON TABLE public.macros IS 'Macros for automating ticket actions';
COMMENT ON TABLE public.canned_responses IS 'Pre-written responses for common scenarios';
COMMENT ON TABLE public.ticket_activities IS 'Audit log of all ticket activities';
COMMENT ON TABLE public.ticket_merges IS 'Tracks ticket merge operations';

