# Backend

Stack: **Python FastAPI + SQLAlchemy async + Supabase PostgreSQL**

## Directory structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, CORS (from CORS_ORIGINS), lifespan, router mount
│   ├── api/
│   │   ├── dependencies.py  # get_current_user, require_role, verify_n8n_api_key_header
│   │   └── v1/
│   │       ├── router.py    # v1 router aggregation
│   │       └── endpoints/   # One file per resource
│   ├── core/
│   │   ├── config.py        # Pydantic Settings (env vars: DATABASE_URL, SECRET_KEY, N8N_API_KEY,
│   │   │                    #   CORS_ORIGINS, EVOLUTION_API_URL, EVOLUTION_API_KEY, JWT TTLs, Master creds)
│   │   ├── database.py      # AsyncSession factory
│   │   └── security.py      # JWT create/decode, bcrypt hash/verify, API key verify
│   ├── models/
│   │   ├── base.py          # Base declarative + TimestampMixin
│   │   ├── user.py          # User model (unified auth)
│   │   ├── master_profile.py
│   │   ├── tenant_profile.py
│   │   └── refresh_session.py
│   ├── schemas/             # Pydantic V2 request/response models
│   ├── services/            # Business logic layer
│   │   ├── auth_service.py
│   │   ├── tenant_service.py
│   │   ├── profile_service.py
│   │   └── evolution_client.py
│   ├── crud/                # Data access helpers
│   └── __init__.py
├── alembic/                 # Async Alembic migrations (reads DATABASE_URL from env)
│   └── env.py
├── scripts/
│   └── seed.py              # Creates initial Master user (idempotent)
├── tests/
│   ├── conftest.py          # Async fixtures (test DB, client, auth headers; Evolution API disabled)
│   ├── test_auth.py         # Login, refresh, logout, identify, refresh-token-as-bearer rejection
│   ├── test_profile.py      # Profile get/update, password change, dashboard, phone conflict
│   └── test_tenants.py      # CRUD, soft-delete, role enforcement, duplicate username
└── pyproject.toml           # UV project config, dependencies
```

## Key modules

### Core

- **`config.py`** — reads `DATABASE_URL`, `SECRET_KEY`, `N8N_API_KEY`, `CORS_ORIGINS`, `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, Master seed credentials from env.
- **`security.py`** — uses `PyJWT` (HS256) for tokens, `bcrypt` directly for password hashing (no passlib).
- **`database.py`** — creates async engine + `sessionmaker` bound to `AsyncSession`.

### API Dependencies

- **`get_current_user`** — decodes Bearer JWT, validates `type == "access"`, loads User, rejects deactivated tenants.
- **`require_role("master")`** — wraps `get_current_user` with role check.
- **`verify_n8n_api_key_header`** — validates `X-API-Key` against configured key.

### Services

- **`AuthService`** — `authenticate()` (login), `create_tokens()` (JWT + refresh session), `refresh_access_token()` (rotation + inactive check), `revoke_refresh_token()` (logout), `identify_by_phone()` (n8n hook).
- **`TenantService`** — CRUD with deactivate (revokes refresh sessions), activate, delete (only inactive, also removes Evolution instance), phone uniqueness, username uniqueness, password auto-generation.
- **`ProfileService`** — get/update profile (cross-table phone uniqueness), change password.
- **`EvolutionClient`** — async HTTP client for Evolution API. Creates WhatsApp instances (`/instance/create`), configures n8n integration (`/n8n/create/{name}`), and deletes instances (`/instance/delete/{name}`) on tenant removal. Transaction safety: rollback DB on Evolution failure. Skipped with warning if `EVOLUTION_API_URL` or `EVOLUTION_API_KEY` not configured.

### Database migrations

Alembic is configured to read `DATABASE_URL` from the environment variable at runtime (see `alembic/env.py`). Falls back to the hardcoded value in `alembic.ini` only if the env var is not set.

### Tenant creation flow

```
POST /api/v1/tenants
  → Validate username/phone uniqueness
  → Create User + TenantProfile (db.flush())
  → EvolutionClient.create_instance(name)    — POST /instance/create
  → EvolutionClient.setup_n8n(name)          — POST /n8n/create/{name}
  → If Evolution fails: db.rollback(), return 409
  → If success: db.commit(), return 201
```

### Tenant deletion flow

```
DELETE /api/v1/tenants/{id}
  → Verify tenant is inactive
  → Get evolution_instance_name from profile
  → Delete User from DB (db.flush())
  → EvolutionClient.delete_instance(name)    — DELETE /instance/delete/{name}
  → If Evolution fails: db.rollback(), return 409
  → If success: db.commit(), return 204
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | PostgreSQL async connection string |
| `SECRET_KEY` | Yes | — | JWT signing key |
| `N8N_API_KEY` | Yes | — | API key for n8n identify endpoint |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Comma-separated allowed origins |
| `EVOLUTION_API_URL` | No | `""` | Evolution API base URL |
| `EVOLUTION_API_KEY` | No | `""` | Evolution API key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | JWT access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token TTL |

## Tests

34 tests across 3 files. Uses `aiosqlite` in-memory DB. Evolution API calls are disabled in tests by clearing `evolution_client.api_key`.

```bash
cd backend && uv run pytest -v
```
