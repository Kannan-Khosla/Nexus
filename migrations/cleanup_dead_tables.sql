-- CLEANUP: Drop tables that have no backend API endpoints.
-- These were created by migrations 005, 006, and 009 but never wired to the application.
-- 
-- ⚠️ WARNING: Run this ONLY after confirming no external tools depend on these tables.
-- Execute manually in Supabase SQL Editor.

-- Migration 005: Knowledge Base (completely unused)
DROP TABLE IF EXISTS public.article_feedback CASCADE;
DROP TABLE IF EXISTS public.article_tag_mappings CASCADE;
DROP TABLE IF EXISTS public.articles CASCADE;
DROP TABLE IF EXISTS public.article_tags CASCADE;
DROP TABLE IF EXISTS public.article_categories CASCADE;

-- Migration 006: Advanced Admin Features (unused tables only)
-- NOTE: tags, ticket_tags, and ticket_activities ARE used by main.py — keep those.
DROP TABLE IF EXISTS public.ticket_merges CASCADE;
DROP TABLE IF EXISTS public.canned_responses CASCADE;
DROP TABLE IF EXISTS public.macros CASCADE;
DROP TABLE IF EXISTS public.automation_rules CASCADE;
DROP TABLE IF EXISTS public.ticket_custom_fields CASCADE;
DROP TABLE IF EXISTS public.custom_fields CASCADE;
DROP TABLE IF EXISTS public.team_members CASCADE;
DROP TABLE IF EXISTS public.teams CASCADE;
DROP TABLE IF EXISTS public.roles CASCADE;

-- Migration 009: Organizations (endpoints removed from main.py)
DROP TABLE IF EXISTS public.organization_members CASCADE;
DROP TABLE IF EXISTS public.organizations CASCADE;

-- Clean up orphaned columns added by dead migrations
ALTER TABLE public.users DROP COLUMN IF EXISTS role_id;
ALTER TABLE public.users DROP COLUMN IF EXISTS team_id;
ALTER TABLE public.tickets DROP COLUMN IF EXISTS organization_id;
