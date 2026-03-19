# Database Migrations

## Migration Order (Active)

Run these in sequence in the Supabase SQL Editor:

| # | File | Purpose |
|---|------|---------|
| 000 | `000_base_schema.sql` | Core `tickets` and `messages` tables |
| 001 | `001_add_users_and_auth.sql` | Users, ratings, escalations, auth |
| 002 | `002_ticket_priorities_slas.sql` | Priority levels, SLA definitions, time tracking |
| 003 | `003_attachments.sql` | File attachment support |
| 004 | `004_email_integration.sql` | Email accounts, threads, sending |
| 007 | `007_fix_messages_sender_constraint.sql` | Fix sender constraint on messages |
| 008a | `008_email_templates.sql` | Email template system |
| 008b | `008_ticket_soft_delete.sql` | Soft delete (trash) for tickets |
| 010 | `010_ticket_routing_rules.sql` | Ticket routing rules |
| 011 | `011_ticket_tags_and_categories.sql` | Tags and categories for tickets |
| 012 | `012_email_polling.sql` | IMAP email polling |
| 013 | `013_email_spam_filtering.sql` | Spam filtering columns |
| 014 | `014_simplify_roles.sql` | Simplified role system |
| 015 | `015_fix_missing_columns_and_view.sql` | Fix missing columns and create `ticket_summary` view |
| 016 | `016_add_assigned_to_column.sql` | Add `assigned_to` column to tickets |

## Archived (Dead / No Backend Support)

The `archived/` subfolder contains migrations that were created but have **no corresponding API endpoints** in the backend. These tables exist in the database but are not used:

- `005_knowledge_base.sql` — Article/knowledge base system (never implemented)
- `006_advanced_admin_features.sql` — Teams, roles, custom fields, macros, automations (never implemented)
- `009_organizations_and_super_admin.sql` — Multi-org support (removed)

## How to Run

1. Open [Supabase Dashboard](https://app.supabase.com) → SQL Editor
2. Paste the migration SQL
3. Click Run

> ⚠️ Always run in order. Always backup first.
