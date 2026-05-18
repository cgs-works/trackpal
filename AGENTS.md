# Trackpal — AGENTS.md

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

## MCP Servers

Configured in `.mcp.json`:

- **supabase** — Hosted Supabase MCP (`https://mcp.supabase.com/mcp`), lazy lifecycle
- **n8n-mcp** — Local npx-based MCP (`n8n-mcp`) with API key auth, connects to `https://rs-n8n.wilfredocamacho.dev`

## Skills

This repo uses 10 local skills under `.agents/skills/`. Each matches specific code patterns and tasks:

| Skill | When to use |
|-------|-------------|
| **fastapi-expert** | Building FastAPI endpoints, Pydantic models, auth flows, async SQLAlchemy operations, JWT, WebSocket, OpenAPI |
| **n8n-code-javascript** | Writing JavaScript code in n8n Code nodes — `$input`, `$json`, `$node`, HTTP requests, data transforms |
| **n8n-expression-syntax** | Writing or debugging n8n expressions (`{{ }}`, `$json`, `$node`), fixing syntax errors in node fields |
| **n8n-mcp-tools-expert** | Using n8n MCP tools — searching nodes, validating configs, managing workflows/credentials, instance audits |
| **n8n-node-configuration** | Configuring n8n node parameters, understanding field dependencies and displayOptions, surgical node edits |
| **n8n-validation-expert** | Interpreting n8n validation errors, handling false positives, auto-fix guidance |
| **n8n-workflow-patterns** | Designing n8n workflow architecture — webhook processing, API integration, DB operations, AI agents, batch processing, scheduled tasks |
| **python-pro** | Writing type-annotated async Python 3.12+ with mypy strict, pytest suites, black/ruff validation, error handling |
| **supabase-postgres-best-practices** | Writing/optimizing Postgres queries, schema design, indexing, connection pooling, RLS, locking |
| **vue-expert-js** | Building Vue 3 components with `<script setup>`, Pinia stores, composables, JSDoc-typed code (no TypeScript), Vite config |

## PR Guidelines

Title: `[backend|frontend|n8n] Brief description`. Run `uv run pytest` + `npm run build`. No hardcoded secrets in workflow JSON.

## Key Architecture Decisions

- WhatsApp console → Master manages tenants from phone
- Canonical tenants → `tenants.owner_user_id` links tenant account to login user; catalog uses `services`/`plans`
- Tenant isolation → app-level tenant filters plus Postgres RLS context (`app.current_user_id`, `app.current_role`, `app.active_tenant_id`)
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
