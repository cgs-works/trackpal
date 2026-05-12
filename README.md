# Trackpal

SaaS de gestión de suscripciones (subscription management). Multi-tenant: Master administra tenants, cada tenant gestiona sus propios clientes y suscripciones a servicios de streaming.

## Stack

- **Backend**: Python FastAPI + SQLAlchemy async + Supabase PostgreSQL
- **Frontend**: Vue 3 (Composition API) + Pinia + Vue Router
- **Orquestación**: n8n + Evolution API (WhatsApp)
- **Infra**: ngrok (dev tunnel), Alembic (migrations)

## Quick start

```bash
# Backend
cd backend
uv sync
cp .env.example .env   # configurar DATABASE_URL, SECRET_KEY, N8N_API_KEY
uv run alembic upgrade head
uv run python scripts/seed.py
uv run uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Estructura del proyecto

```
trackpal/
├── backend/         # FastAPI + SQLAlchemy async
│   ├── app/         # Application code
│   ├── alembic/     # Migrations
│   ├── tests/       # pytest suite (34 tests)
│   └── scripts/     # seed.py
├── frontend/        # Vue 3 + Vite
│   └── src/
├── n8n/             # Workflow exports
├── docs/            # Documentation
└── CONTEXT.md       # Domain terminology and decisions
```

## Documentación

Ver [docs/SUMMARY.md](docs/SUMMARY.md) para el índice completo de documentación técnica.
