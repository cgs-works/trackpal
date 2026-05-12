# Backend

Stack: **Python FastAPI + SQLAlchemy async + Supabase PostgreSQL**

## Directory structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, CORS, lifespan, router mount
│   ├── api/
│   │   ├── dependencies.py  # get_current_user, require_role, verify_n8n_api_key_header
│   │   └── v1/
│   │       ├── router.py    # v1 router aggregation
│   │       └── endpoints/   # One file per resource
│   ├── core/
│   │   ├── config.py        # Pydantic Settings (env vars)
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
│   ├── crud/                # Data access helpers
│   └── __init__.py
├── alembic/                 # Async Alembic migrations
├── scripts/
│   └── seed.py              # Creates initial Master user
├── tests/
│   ├── conftest.py          # Async fixtures (test DB, client, auth headers)
│   ├── test_auth.py         # Login, refresh, logout, identify tests
│   ├── test_profile.py      # Profile get/update, password change, dashboard
│   └── test_tenants.py      # CRUD, soft-delete, role enforcement
└── pyproject.toml           # UV project config, dependencies
```

## Key modules

### Core

- **`config.py`** — reads `DATABASE_URL`, `SECRET_KEY`, `N8N_API_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` from env.
- **`security.py`** — wraps `PyJWT` (HS256), `passlib[bcrypt]` for password hashing.
- **`database.py`** — creates async engine + `sessionmaker` bound to `AsyncSession`.

### API Dependencies

- **`get_current_user`** — decodes Bearer JWT, validates `type == "access"`, loads User, rejects deactivated tenants.
- **`require_role("master")`** — wraps `get_current_user` with role check.
- **`verify_n8n_api_key_header`** — validates `X-API-Key` against configured key.

### Services

- **`AuthService`** — `authenticate()` (login), `create_tokens()` (JWT + refresh session), `refresh_access_token()` (rotation + inactive check), `revoke_refresh_token()` (logout), `identify_by_phone()` (n8n hook).
- **`TenantService`** — CRUD with deactivate (revokes refresh sessions), activate, delete (only inactive), phone uniqueness, username uniqueness, password auto-generation.
- **`ProfileService`** — get/update profile (cross-table phone uniqueness), change password.

## Tests

28 tests across 3 files. Uses `aiosqlite` in-memory DB via `AsyncEngine` with `create_all`/`drop_all` per module. Fixtures provide authenticated client for master and tenant roles.

```bash
uv run pytest -v
```
