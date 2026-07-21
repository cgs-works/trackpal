# TrackPal

Multi-tenant platform for managing WhatsApp-based service delivery. The Master operator manages tenant lifecycle through a WhatsApp console and a web dashboard. Tenant Admins use plan-aware Web and WhatsApp interfaces for profile, WhatsApp linking, mailbox code retrieval, code-service selection, and access control; Pro adds clients, catalog, subscriptions, reminders, and Public API Catalog.

Clients of Pro tenants have read-only Web and WhatsApp access to profile and active subscription information, can search for access codes through WhatsApp, and can change their password through the Web Dashboard.

## Stack

- **Backend**: Python 3.12, FastAPI, PostgreSQL (asyncpg), Redis (HA), Alembic
- **Frontend**: React 19, TypeScript, Vite, Zustand, TanStack Router
- **Infrastructure**: Render (backend), Cloudflare Pages (frontend), Evolution API (WhatsApp), n8n (automation, bot + reminders)

## Quick Start (Local Dev)

```bash
cd backend
uv sync                    # installs deps with uv
cp .env.example .env       # set DATABASE_URL (PostgreSQL), etc.
uv run alembic upgrade head # run migrations
uv run python -m scripts.seed # create initial Master user
uv run uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

## Documentation

Full documentation: [docs/SUMMARY.md](docs/SUMMARY.md)

## Project Structure

- `backend/` — Python FastAPI application
- `frontend/` — React 19 SPA
- `docs/` — Project documentation
- `n8n/` — n8n workflow exports (WhatsApp bot + subscription reminders)
