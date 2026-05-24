<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->

# Trackpal

## Project Overview

Trackpal — multi-tenant SaaS. Master manages tenants via WhatsApp console + web dashboard. Spanish market.

**Stack:** Python ≥3.12 / FastAPI / SQLAlchemy async / PostgreSQL / Redis HA / JWT+bcrypt / Evolution API / n8n / Vue 3+Pinia / Vite

## Documentation

All project documentation is in [docs/SUMMARY.md](docs/SUMMARY.md). Before planning or implementing, read it to understand the full documentation map. Key docs:

| Area | Location |
|------|----------|
| System architecture | `docs/architecture/system-overview.md` |
| API layer | `docs/architecture/api-layer.md` |
| Database schema | `docs/architecture/database-schema.md` |
| Redis HA | `docs/architecture/redis-ha.md` |
| WhatsApp console flow | `docs/architecture/whatsapp-console-flow.md` |
| Evolution integration | `docs/architecture/evolution-integration.md` |
| n8n workflow | `docs/architecture/n8n-workflow.md` |
| Frontend architecture | `docs/architecture/frontend-architecture.md` |
| Input validation policy | `docs/architecture/input-validation-policy.md` |
| Backend conventions | `docs/code-standard/backend-conventions.md` |
| Frontend conventions | `docs/code-standard/frontend-conventions.md` |
| Product goals | `docs/project-pdr/product-goals.md` |
| Business rules | `docs/project-pdr/business-rules.md` |

## Setup Commands

```bash
# Backend
cd backend && pip install uv && uv sync --group dev
uv run alembic upgrade head && uv run python -m scripts.seed
uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev    # proxies /api → :8000
npm run build                                 # → dist/

# n8n
# Import n8n/Trackpal\ WhatsApp\ Bot.json via n8n UI
```

**Key env vars** (22+ total, see `app/core/config.py` or `render.yaml`):
`DATABASE_URL`, `SECRET_KEY`, `MASTER_USERNAME/PASSWORD`, `MASTER_PHONE`, `N8N_API_KEY`, `EVOLUTION_API_URL/KEY`, `REDIS_PRIMARY_URL`, `REDIS_BACKUP_URL`

## Project Structure

```
backend/
├── app/main.py                     # FastAPI entry, CORS, lifespan
├── app/api/v1/endpoints/           # auth, me, dashboard, tenants, catalog, integrations
├── app/api/dependencies.py         # get_current_user, require_role, verify_n8n
├── app/core/                       # config, database, security, redis, validation, phone
├── app/models/                     # user, tenant, service, plan, profiles, refresh_session
├── app/schemas/                    # auth, tenant, catalog, me, dashboard, whatsapp
├── app/services/                   # auth, tenant, catalog, profile, evolution_client,
│                                   # whatsapp_console_service (1327 LOC), session services, facade
├── tests/                          # 22 files, ~11.6k LOC
└── scripts/seed.py

frontend/
├── src/
│   ├── main.js / App.vue / style.css
│   ├── router/index.js             # 3 rutas + guards
│   ├── services/api.js             # Axios + interceptors
│   ├── stores/auth.js              # Pinia: token, user, login/logout
│   └── views/                      # LoginView, MasterDashboardView, TenantDashboardView,
│                                   # ClientDashboardView
└── vite.config.js
```

**n8n pipeline:** `Webhook POST → Parse → Config → POST /api/v1/integrations/n8n/console → Merge → Evolution API sendText`

## Testing

```bash
cd backend
uv run pytest -v                          # All tests
uv run pytest tests/test_auth.py -v       # Single file
uv run pytest -v -k "tenant"              # By keyword
```

**Patterns:** async (pytest-asyncio), SQLite in-memory (aiosqlite), httpx ASGITransport client. Evolution + Redis mocked. Fixtures: `async_client`, `db_session`, `master_headers`, `tenant_headers`.

## Code Style

- **Backend:** Python 3.12+ type hints, FastAPI endpoints thin (logic in services/), SQLAlchemy async, Pydantic v2 schemas, bcrypt + JWT short-lived + refresh rotation, phone digits-only canonical form, Spanish UI
- **Frontend:** Vue 3 `<script setup>`, Pinia stores, Axios interceptors, router guards, plain JS (no TypeScript), **no frontend tests**
- **n8n:** Config Set node for vars, `neverError` on webhook, input normalization (strip `@c.us`), reply fallback on timeout

## Build & Deployment

| Target | Command |
|---|---|
| Render | `pip install uv && uv sync` → `uv run alembic upgrade head && uv run python -m scripts.seed && uv run uvicorn app.main:app` |
| Cloudflare Pages | `VITE_API_URL=<url> npm run build` → upload `dist/` |
| n8n | Import workflow JSON; set webhook URL in Evolution API instance (trigger: `/menu`) |
