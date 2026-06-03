# AGENTS.md

## Project Overview

Trackpal is a WhatsApp-driven CRM for independent delivery businesses. Architecture:

- **`backend/`** — Python FastAPI (>=3.12, SQLAlchemy 2.0 async, Pydantic v2, Alembic, Redis)
- **`frontend/`** — Vue 3 (Composition API, Pinia, vue-router, Axios, plain JS via Vite)
- **`n8n/`** — n8n workflow JSON exports (WhatsApp bot + subscription reminders)
- **`docs/`** — System documentation (`docs/SUMMARY.md` is the index)

Integrated services: Evolution API (WhatsApp provisioning), n8n (webhook automation), Render (backend host), Cloudflare Pages (frontend host).

## Setup Commands

### Backend

```bash
cd backend
uv sync                        # Install all dependency groups (includes dev)
uv sync --no-dev               # Production install only
uv run alembic upgrade head    # Run database migrations
uv run python -m scripts.seed  # Seed master user (requires env vars)
```

### Frontend

```bash
cd frontend
npm install                    # Install dependencies
npm run dev                    # Start Vite dev server (port 5173, proxies /api -> :8000)
npm run build                  # Production build to frontend/dist/
npm run preview                # Preview production build locally
```

## Environment Variables

### Backend (`backend/.env`)

See `backend/.env.example` for all vars. Required:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL+asyncpg, e.g. `postgresql+asyncpg://user:pass@host:5432/dbname?sslmode=require` |
| `SECRET_KEY` | JWT signing key. Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `DATA_ENCRYPTION_KEY` | Fernet key for reversible encryption. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `N8N_API_KEY` | Shared API key for n8n X-API-Key header |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `EVOLUTION_API_URL` / `EVOLUTION_API_KEY` | Evolution API instance for WhatsApp provisioning |
| `REDIS_PRIMARY_URL` / `REDIS_BACKUP_URL` | Redis HA endpoints (`redis://` or `rediss://`) |
| `MASTER_USERNAME` / `MASTER_PASSWORD` / `MASTER_NAME` / `MASTER_PHONE` | Master seed credentials |
| OAuth vars | `GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI`, `MICROSOFT_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI/TENANT_ID` |

### Frontend (`frontend/.env`)

| Variable | Description |
|---|---|
| `VITE_API_URL` | Backend API base URL, e.g. `http://localhost:8000/api/v1` |

## Development Workflow

### Backend

```bash
cd backend
uv run uvicorn app.main:app --reload    # Dev server on :8000
uv run alembic revision --autogenerate -m "description"   # Create migration
uv run alembic upgrade head            # Apply migrations
uv run python -m scripts.seed          # Seed master user
```

### Frontend

```bash
cd frontend
npm run dev               # Dev server on :5173 with API proxy to :8000
npm run build             # Production build to dist/
```

Vite proxy config (`frontend/vite.config.js`) forwards `/api` requests to `http://localhost:8000`.

### n8n

Workflow JSON files in `n8n/` can be imported into an n8n instance. Import via n8n UI → Workflows → Add from file.

### Docs

Docs are in `docs/` with `docs/SUMMARY.md` as entry point. Agent should update docs when changing behavior.

## Testing Instructions

### Backend (pytest)

```bash
cd backend
uv run pytest                      # Run all tests
uv run pytest -x                   # Stop on first failure
uv run pytest -k "test_name"       # Filter by test name
uv run pytest --coverage           # Coverage report (requires pytest-cov)
uv run pytest -n auto              # Parallel (uses pytest-xdist)
```

Test details:
- **Framework**: pytest 9 + pytest-asyncio
- **Database**: SQLite in-memory (`sqlite+aiosqlite:///:memory:`, auto-fixture `setup_database`)
- **Fixtures file**: `backend/tests/conftest.py`
- **Mocking**: External Evolution API calls disabled via `evolution_client.api_key = ""`
- **HTTP client**: `httpx.AsyncClient` with ASGITransport (no live server)

### Frontend (vitest)

```bash
cd frontend
npm test                         # vitest run
npx vitest                       # Watch mode
npx vitest run -t "test name"    # Filter by test name
```

Test details:
- **Framework**: vitest 4 under jsdom environment
- **Mocking**: `vi.mock("axios", ...)` pattern in store tests
- **Test files**: `frontend/src/**/__tests__/*.spec.js`

## Code Style & Linting

- **Python**: Ruff is available (`.ruff_cache/` present). Run via `ruff check .` and `ruff format .` from `backend/`. No explicit config file — uses Ruff defaults.
- **JS/Vue**: No ESLint or Prettier config found. Vite handles transpilation. Follow existing patterns: Composition API `<script setup>`, Pinia stores, Vue Router.
- No TypeScript — all frontend code is plain ESM JavaScript.
- No pre-commit hooks configured.

## Build & Deployment

### Frontend → Cloudflare Pages

```bash
cd frontend
npm run build                    # Output: frontend/dist/
```

Set `VITE_API_URL` env var in Cloudflare Pages dashboard. Build command: `npm run build`. Output dir: `dist`.

### Backend → Render

Deployment is defined in `render.yaml` (root dir):

- **Service name**: `trackpal-api`
- **Runtime**: Python
- **Region**: Oregon (free plan)
- **Root dir**: `backend/`
- **Build**: `pip install uv && uv sync`
- **Start**: `uv run alembic upgrade head && uv run python -m scripts.seed && uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Env vars**: See `render.yaml` for complete list. Sensitive vars (`DATABASE_URL`, `SECRET_KEY`, etc.) must be set manually in Render dashboard.

No Docker setup exists.

## Pull Request Guidelines

- **Title format**: `[<area>] <Brief description>` — e.g. `[backend] Fix auth token expiry`
- **Areas**: backend, frontend, n8n, infra, docs, devops
- **Before submitting**: Ensure all tests pass and code follows existing patterns
- **Issue templates** exist at `.github/ISSUE_TEMPLATE/` for: bug-report, feature-request, epic, task

## Key Technical Context

### Backend Architecture

- FastAPI app in `backend/app/main.py` with lifespan events
- SQLAlchemy async session per request via dependency injection
- JWT auth (python-jose) with access + refresh tokens
- Redis HA with failover for WhatsApp session state (circuit breaker pattern)
- Evolution API client for WhatsApp instance provisioning
- Fernet encryption for stored tenant OAuth credentials
- OAuth 2.0 for mailbox integration (Google + Microsoft)

### Database Migrations (Alembic)

- Config: `backend/alembic.ini` + `backend/alembic/env.py`
- Versions in `backend/alembic/versions/`
- Models in `backend/app/models/`

### n8n Integration

- n8n workflows in `n8n/` as JSON exports
- Backend exposes `/api/v1/n8n/identify` endpoint (X-API-Key auth) for n8n to resolve phone → client
- `N8N_API_KEY` shared secret between backend and n8n

## Common Gotchas

1. **DATA_ENCRYPTION_KEY must be set** before importing app code. Test conftest sets it via `os.environ` before any imports.
2. **Alembic autogenerate** requires a running database with models imported in `env.py`.
3. **Frontend API proxy** only works in dev — production uses `VITE_API_URL` directly.
4. **Redis HA**: Primary and backup URLs must be reachable. Circuit breaker opens after 3 failures.
5. **Seed script** idempotent — safe to run on every deploy (Render start command runs it).
