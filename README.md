# Trackpal

Multi-tenant platform for managing WhatsApp-based service delivery. The Master operator manages tenant lifecycle through a WhatsApp chatbot console and a web dashboard.

## Stack

- **Backend**: Python 3.12, FastAPI, PostgreSQL (asyncpg), Redis (HA), Alembic
- **Frontend**: Vue 3, Vite, Pinia, vue-router
- **Infrastructure**: Render (backend), Cloudflare Pages (frontend), Evolution API (WhatsApp), n8n (automation)

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
- `frontend/` — Vue 3 SPA
- `docs/` — Project documentation
- `n8n/` — n8n workflow export
