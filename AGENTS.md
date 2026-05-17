# AGENTS.md

## Project Overview

Trackpal — multi-tenant SaaS. Master manages tenants via WhatsApp console + web dashboard. Spanish market.

**Stack:** Python ≥3.12 / FastAPI / SQLAlchemy async / PostgreSQL / Redis HA / JWT+brypt / Evolution API / n8n / Vue 3+Pinia / Vite

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
├── app/api/v1/endpoints/           # auth, me, dashboard, tenants, integrations
├── app/api/dependencies.py         # get_current_user, require_role, verify_n8n
├── app/core/                       # config, database, security, redis, validation, phone
├── app/models/                     # user, master/tenant_profile, refresh_session
├── app/schemas/                    # auth, tenant, me, dashboard, whatsapp
├── app/services/                   # auth, tenant, profile, evolution_client,
│                                   # whatsapp_console_service (1327 LOC), session services, facade
├── tests/                          # 22 files, ~11.6k LOC
└── scripts/seed.py

frontend/
├── src/
│   ├── main.js / App.vue / style.css
│   ├── router/index.js             # 3 rutas + guards
│   ├── services/api.js             # Axios + interceptors
│   ├── stores/auth.js              # Pinia: token, user, login/logout
│   └── views/                      # LoginView, MasterDashboardView, TenantDashboardView
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

## PR Guidelines

Title: `[backend|frontend|n8n] Brief description`. Run `uv run pytest` + `npm run build`. No hardcoded secrets in workflow JSON.

## Key Architecture Decisions

- WhatsApp console → Master manages tenants from phone
- n8n bridge → decouples Evolution webhooks from backend
- Redis HA + circuit breaker → 3 failures → backup, half-open 30s
- JWT + refresh rotation → short-lived tokens, refresh invalidated on use
- Phone canonicalization → digits-only + JID stripping
- Test with SQLite in-memory → fast, no PG needed

## Security

API keys in env vars. `X-API-Key` for n8n endpoint. Refresh tokens hashed in DB. Phone numbers as PII — normalize early, log minimally. Lockout after 5 failed WhatsApp auth attempts (`WA_AUTH_MAX_FAILED_ATTEMPTS`).

## Debugging

| Symptom | Cause | Fix |
|---|---|---|
| `/health` 503 | Redis down | Check `REDIS_PRIMARY_URL` or reset circuit breaker |
| n8n empty reply | API key mismatch | Align `N8N_API_KEY` in backend + n8n Config |
| Auth locked after 5 tries | Lockout active | Wait 5 min or del `wa:auth:lock:*` in Redis |
| Frontend login CORS | Vite proxy not running | Ensure `npm run dev` + backend on :8000 |
| Tenant creation fails | Evolution API timeout | Check `EVOLUTION_API_URL` + key |
| Alembic conflict | Stale chain | `uv run alembic stamp head && uv run alembic upgrade head` |
