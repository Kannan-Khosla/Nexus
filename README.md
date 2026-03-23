# Nexus - AI-Powered Support Platform

A comprehensive FastAPI-based AI support ticketing system with Supabase integration, featuring intelligent ticket routing, email integration, file attachments, and advanced admin capabilities.

## Project Structure

```
.
├── main.py                 # FastAPI application entry point
├── config.py               # Configuration management (Pydantic Settings)
├── auth.py                 # Authentication utilities (JWT, password hashing)
├── logger.py               # Logging configuration
├── middleware.py           # Error handling middleware
├── email_service.py        # Email service (SMTP, SendGrid, AWS SES)
├── routing_service.py      # Automatic ticket routing service
├── storage.py              # File storage service (Supabase Storage)
├── supabase_config.py      # Supabase client configuration
│
├── frontend/               # React frontend application
│   ├── src/
│   │   ├── components/     # React components
│   │   │   ├── admin/      # Admin-specific components
│   │   │   └── customer/   # Customer-specific components
│   │   ├── contexts/       # React Context for state management
│   │   ├── services/       # API service layer
│   │   └── ...
│   ├── package.json        # Node.js dependencies
│   └── vite.config.js      # Vite configuration
│
├── migrations/             # Database migrations (run in order)
│   ├── 001_add_users_and_auth.sql
│   ├── 002_ticket_priorities_slas.sql
│   ├── 003_attachments.sql
│   ├── 004_email_integration.sql
│   ├── 005_knowledge_base.sql
│   ├── 006_advanced_admin_features.sql
│   ├── 007_fix_messages_sender_constraint.sql
│   ├── 008_email_templates.sql
│   ├── 008_ticket_soft_delete.sql
│   ├── 009_organizations_and_super_admin.sql
│   ├── 010_ticket_routing_rules.sql
│   └── 011_ticket_tags_and_categories.sql
│
├── tests/                  # Test suite
│   ├── test_api.py         # Integration tests
│   ├── test_helpers.py     # Unit tests
│   ├── test_priority_sla_endpoints.py
│   └── conftest.py         # Pytest fixtures
│
├── docs/                   # Project documentation
│   ├── setup/              # Setup and installation guides
│   ├── troubleshooting/    # Troubleshooting guides
│   ├── guides/             # How-to guides
│   ├── apis.md             # API reference
│   ├── architecture.md     # Architecture documentation
│   ├── database.md         # Database schema
│   └── development.md      # Development guide
│
├── scripts/                # Utility scripts
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Quick Start

### 1. Install Dependencies

**Backend:**
```bash
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```env
# OpenAI
OPENAI_API_KEY=your_openai_key

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Optional: Admin token for protected endpoints
ADMIN_TOKEN=choose_a_secure_token

# Optional: AI reply rate limiting
AI_REPLY_WINDOW_SECONDS=60
AI_REPLY_MAX_PER_WINDOW=2
```

### 3. Setup Database

Run migrations in order in your Supabase SQL Editor:

1. `migrations/001_add_users_and_auth.sql`
2. `migrations/002_ticket_priorities_slas.sql`
3. `migrations/003_attachments.sql`
4. `migrations/004_email_integration.sql`
5. `migrations/005_knowledge_base.sql`
6. `migrations/006_advanced_admin_features.sql`
7. `migrations/007_fix_messages_sender_constraint.sql`
8. `migrations/008_email_templates.sql`
9. `migrations/008_ticket_soft_delete.sql`
10. `migrations/009_organizations_and_super_admin.sql`
11. `migrations/010_ticket_routing_rules.sql`
12. `migrations/011_ticket_tags_and_categories.sql`

See `migrations/README.md` for detailed instructions.

### 4. Start the Application

**Backend:**
```bash
python -m uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm run dev
```

- Backend API: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- API Docs: `http://localhost:8000/docs`

## Features

### Core Features
- ✅ AI-powered customer support with OpenAI integration
- ✅ Ticket threading and conversation history
- ✅ Human agent handoff and escalation
- ✅ Real-time Supabase integration
- ✅ JWT-based authentication
- ✅ Role-based access control (Customer, Admin, Super Admin)

### Advanced Features
- ✅ File attachments with Supabase Storage
- ✅ Email integration (SMTP, SendGrid, AWS SES)
- ✅ Email templates and automated responses
- ✅ Automatic ticket routing based on rules
- ✅ Tags and categories for ticket organization
- ✅ Soft delete with trash management
- ✅ Organization management (Super Admin)
- ✅ Team member invitations
- ✅ Priority and SLA management
- ✅ Knowledge base integration

### Frontend Features
- ✅ Modern React application with Vite
- ✅ Tailwind CSS with custom techy theme
- ✅ Responsive design
- ✅ Real-time updates
- ✅ Admin dashboard with advanced filtering
- ✅ Customer portal
- ✅ Email composer and thread viewer
- ✅ File upload and management

## Documentation

- [Setup Guides](docs/setup/) - Installation and configuration
- [API Documentation](docs/apis.md) - API endpoints reference
- [Architecture](docs/architecture.md) - System architecture
- [Database Schema](docs/database.md) - Database documentation
- [Development Guide](docs/development.md) - Development setup
- [Troubleshooting](docs/troubleshooting/) - Common issues and fixes

## Testing

Run the test suite:
```bash
pytest tests/
```


