# Backend

Stack: **Python FastAPI + SQLAlchemy async + Supabase PostgreSQL**

## Directory structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, CORS (from CORS_ORIGINS), lifespan, router mount
│   │                        #   lifespan: init_redis() / close_redis()
│   ├── api/
│   │   ├── dependencies.py  # get_current_user, require_role, verify_n8n_api_key_header
│   │   └── v1/
│   │       ├── router.py    # v1 router aggregation
│   │       └── endpoints/   # One file per resource
│   ├── core/
│   │   ├── config.py        # Pydantic Settings (env vars: DATABASE_URL, SECRET_KEY, N8N_API_KEY,
│   │   │                    #   CORS_ORIGINS, EVOLUTION_API_URL, EVOLUTION_API_KEY, JWT TTLs,
│   │   │                    #   Master creds, Redis HA URLs/pool/breaker/TTL)
│   │   ├── database.py      # AsyncSession factory
│   │   ├── phone.py         # normalize_phone() — canonical digits-only phone; uses shared
│   │   │                    #   _strip_phone_suffixes() from input_validation to strip JID/device suffixes
│   │   ├── input_validation.py  # Centralized reusable validation policy for username, email, phone,
│   │   │                       #   and full_name. Exports standalone functions (validate_username,
│   │   │                       #   validate_full_name, validate_email, validate_phone) and
│   │   │                       #   InputValidationError exception. Used by schemas, services, seed,
│   │   │                       #   and WhatsApp console flows
│   │   ├── redis_client.py  # RedisConnectionManager + FailoverPolicy — active-passive HA,
│   │   │                    #   primary/backup pools, circuit breaker, half-open recovery
│   │   └── security.py      # JWT create/decode, bcrypt hash/verify, API key verify
│   ├── models/
│   │   ├── base.py          # Base declarative + TimestampMixin
│   │   ├── user.py          # User model (unified auth)
│   │   ├── master_profile.py
│   │   ├── tenant_profile.py
│   │   └── refresh_session.py
│   ├── schemas/             # Pydantic V2 request/response models (normalize phone on input)
│   ├── services/            # Business logic layer
│   │   ├── auth_service.py  # identify_by_phone() normalizes phone before lookup
│   │   ├── tenant_service.py
│   │   ├── profile_service.py
│   │   ├── evolution_client.py
│   │   ├── whatsapp_session_service.py   # WhatsAppSessionService — Redis-backed session CRUD,
│   │   │                                 #   TTL management, failover-aware used_backup signal
│   │   ├── whatsapp_console_service.py   # WhatsAppConsoleService — conversation routing,
│   │   │                                 #   menus, multi-step CRUD flows, reset/help/fallback
│   │   └── contingency_reply_policy.py   # ContingencyReplyPolicy — relayable texts for
│   │                                     #   backup-session-reset / total-unavailability
│   ├── crud/                # Data access helpers
│   └── __init__.py
├── alembic/                 # Async Alembic migrations (reads DATABASE_URL from env)
│   └── env.py
├── scripts/
│   └── seed.py              # Creates initial Master user (idempotent)
├── tests/
│   ├── conftest.py          # Async fixtures (test DB, client, auth headers; Evolution API disabled)
│   ├── test_auth.py         # Login, refresh, logout, identify, refresh-token-as-bearer rejection
│   ├── test_contingency_reply_policy.py  # Degraded state reply texts
│   ├── test_input_validation_policy.py   # Central policy: username, email, phone, full_name rules
│   ├── test_phone_normalization_migration.py  # Phone canonicalisation DB migration test
│   ├── test_phone_normalizer.py          # Phone canonicalization
│   ├── test_profile.py      # Profile get/update, password change, dashboard, phone conflict
│   ├── test_redis_connection_manager.py  # Primary/backup pools, execute routing
│   ├── test_redis_failover_policy.py     # Circuit breaker, half-open, threshold
│   ├── test_tenants.py      # CRUD, soft-delete, role enforcement, duplicate username
│   ├── test_whatsapp_auth_session_service.py      # Auth session CRUD, failure counter, lockout
│   ├── test_whatsapp_create_flow.py                # Multi-step create tenant flow
│   ├── test_whatsapp_credential_auth_flow.py       # Conversational login, lockout, bypass regression
│   ├── test_whatsapp_edit_flow.py                  # Multi-step edit tenant flow
│   ├── test_whatsapp_endpoint.py                   # /integrations/n8n/console endpoint
│   ├── test_whatsapp_lifecycle_flow.py             # Deactivate/delete lifecycle flows
│   ├── test_whatsapp_list_select_flow.py           # Tenant list + detail selection flow
│   ├── test_whatsapp_menu_flow.py                  # Menu, reset, help, fallback, TTL not refreshed on noise
│   └── test_whatsapp_session_service.py            # Session CRUD, TTL, explicit delete, used_backup
└── pyproject.toml           # UV project config, dependencies
```

## Key modules

### Core

- **`config.py`** — reads `DATABASE_URL`, `SECRET_KEY`, `N8N_API_KEY`, `CORS_ORIGINS`, `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, Master seed credentials, and Redis HA settings (`REDIS_PRIMARY_URL`, `REDIS_BACKUP_URL`, `REDIS_POOL_SIZE`, socket/connect timeout, health check interval, failover threshold, breaker open seconds, session TTL) from env.
- **`phone.py`** — `normalize_phone(value)` uses shared `_strip_phone_suffixes()` from `input_validation` to strip JID suffixes (`@c.us`, `@s.whatsapp.net`) and device suffixes (`:device`), then removes all non-digits. Returns canonical digits-only string or `None`. Applied in schemas, services, and identity lookup.
- **`input_validation.py`** — Central policy module with standalone functions (`validate_username`, `validate_full_name`, `validate_email`, `validate_phone`) and an `InputValidationError(field, message, code)` exception. Rules:
  - **username**: lowercase ASCII letters, digits, `_`; must start with letter; max 20 chars; leading/trailing whitespace rejected.
  - **full_name**: Unicode/accented letters, digits, and spaces allowed; leading/trailing whitespace rejected; multiple internal spaces collapsed to one.
  - **email**: syntax validation + normalization via `email-validator` with `check_deliverability=False`. Optional `None` when not required.
  - **phone**: validates via `phonenumbers` (E.164-interpretable input); accepts optional leading `+`; rejects extensions, noisy suffixes, and invalid characters; strips WhatsApp JID (`@c.us`, `@s.whatsapp.net`) and device (`:`) suffixes before parsing; returns digits-only canonical form (no `+` prefix).
Used by Pydantic schemas, service layer, seed script, and WhatsApp console flows.
- **`redis_client.py`** — `RedisConnectionManager` owns primary and backup `Redis` clients (pools) for the process lifetime. `FailoverPolicy` implements circuit breaker (CLOSED → OPEN → HALF_OPEN) based on consecutive failure threshold and open window. `execute()` routes operations to the active store, records success/failure, and falls back to backup when the breaker opens.
- **`security.py`** — uses `PyJWT` (HS256) for tokens, `bcrypt` directly for password hashing (no passlib).
- **`database.py`** — creates async engine + `sessionmaker` bound to `AsyncSession`.

### API Dependencies

- **`get_current_user`** — decodes Bearer JWT, validates `type == "access"`, loads User, rejects deactivated tenants.
- **`require_role("master")`** — wraps `get_current_user` with role check.
- **`verify_n8n_api_key_header`** — validates `X-API-Key` against configured key.

### Services

- **`AuthService`** — `authenticate()` (login), `create_tokens()` (JWT + refresh session), `refresh_access_token()` (rotation + inactive check), `revoke_refresh_token()` (logout), `identify_by_phone()` (n8n hook, normalizes phone before lookup).
- **`TenantService`** — CRUD with deactivate (revokes refresh sessions), activate, delete (only inactive, also removes Evolution instance), phone uniqueness, username uniqueness, password auto-generation. Enforces `input_validation` policy defensively before persistence.
- **`ProfileService`** — get/update profile (cross-table phone uniqueness), change password. Enforces `input_validation` policy defensively before persistence.
- **`EvolutionClient`** — async HTTP client for Evolution API. Creates WhatsApp instances (`/instance/create`), configures n8n integration (`/n8n/create/{name}`), and deletes instances (`/instance/delete/{name}`) on tenant removal. Transaction safety: rollback DB on Evolution failure. Skipped with warning if `EVOLUTION_API_URL` or `EVOLUTION_API_KEY` not configured.
- **`WhatsAppAuthSessionService`** — manages Redis-backed authenticated session + lockout state. Three primitives keyed by canonical phone: `wa:auth:{phone}` (auth session, TTL 15 min sliding), `wa:auth:fail:{phone}` (failure counter window, default 15 min), `wa:auth:lock:{phone}` (temporary lockout after threshold, default 5 min). No password stored in payloads. Uses `RedisConnectionManager.execute()` for HA-aware operations.
- **`WhatsAppMasterConsoleFacade`** — orchestrator for auth-gated WhatsApp Master Console. Entry point for `POST /api/v1/integrations/n8n/console`. Three-step gate: (1) check lockout, (2) check auth session (`wa:auth:{phone}`) → delegate to `WhatsAppConsoleService` for menu/CRUD, (3) run conversational login flow (username → password → credential verification → create auth session). Global commands (`0`, `menu`, `cancelar`) work during login. Reset clears conversation session only, not auth session.
- **`WhatsAppSessionService`** — manages ephemeral conversation state in Redis via `RedisConnectionManager.execute()`. Stores `ConversationSession` as JSON under `session:{phone}`. Supports `get_session`, `create_session`, `save_session` (with `touch_ttl` parameter), `update_session`, and `clear_session`. TTL refreshed only on valid flow progress. Exposes `used_backup` signal for contingency detection.
- **`WhatsAppConsoleService`** — routes WhatsApp messages through conversation flows. Handles menu display, numeric selection, create/edit/deactivate/delete tenant flows, help, fallback, global reset, contingency reset (backup missing session), and TTL refresh discipline. Returns deterministic reply text for n8n transport. Validates each field step via `input_validation` policy and reprompts on failure without losing previously collected data.
- **`ContingencyReplyPolicy`** — defines two relayable replies: `SESSION_RESET` (failover backup lacks session) and `TEMPORARY_UNAVAILABLE` (both Redis stores down).

### Database migrations

Alembic is configured to read `DATABASE_URL` from the environment variable at runtime (see `alembic/env.py`). Falls back to the hardcoded value in `alembic.ini` only if the env var is not set.

### Tenant creation flow

```
POST /api/v1/tenants
  → Pydantic schema validates fields (422 on invalid format)
  → TenantService normalizes via input_validation policy
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
| `REDIS_URL` | No | `""` | Redis URL (legacy fallback) |
| `REDIS_PRIMARY_URL` | No | `""` | Redis primary URL (`redis://` or `rediss://`) |
| `REDIS_BACKUP_URL` | No | `""` | Redis backup URL (`redis://` or `rediss://`) |
| `REDIS_POOL_SIZE` | No | `20` | Max connections per pool |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | No | `5.0` | Socket timeout (seconds) |
| `REDIS_CONNECT_TIMEOUT_SECONDS` | No | `5.0` | Connection timeout (seconds) |
| `REDIS_HEALTH_CHECK_INTERVAL_SECONDS` | No | `30.0` | Health check interval (seconds) |
| `REDIS_FAILOVER_FAILURE_THRESHOLD` | No | `3` | Consecutive failures before breaker opens |
| `REDIS_BREAKER_OPEN_SECONDS` | No | `30` | Breaker open window (seconds) |
| `WHATSAPP_SESSION_TTL_MINUTES` | No | `15` | WhatsApp session TTL (minutes) |
| `WHATSAPP_AUTH_FAIL_THRESHOLD` | No | `5` | Consecutive login failures before temporary lockout |
| `WHATSAPP_AUTH_LOCK_MINUTES` | No | `5` | Lockout duration (minutes) after threshold reached |
| `WHATSAPP_AUTH_FAIL_WINDOW_MINUTES` | No | `15` | Failure counter window (minutes); resets after this time without reaching threshold |

## Tests

589 tests across 18 test files. Uses `aiosqlite` in-memory DB. Evolution API calls are disabled in tests by clearing `evolution_client.api_key`. Redis operations use fake/test doubles — no Redis cloud dependency.

```bash
cd backend && uv run pytest -v
```
