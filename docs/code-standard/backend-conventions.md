# Backend Coding Conventions

## Language & Runtime

- Python 3.12+ with strict typing (`from __future__ import annotations`)
- Async/await throughout (FastAPI, asyncpg, async Redis)
- Package manager: `uv` with `uv.lock`

## Project Structure

- Layers follow strict dependency direction: `api → services → repositories → models`
- `api` depends on `services` and `schemas`
- `services` depends on `repositories`, `core`, and `models`
- `repositories` depends on `models` and `core`
- `core` has no internal dependencies (except `config` consumed everywhere)

## Naming

- **Files**: snake_case (`auth_service.py`, `tenant.py`, `catalog_service.py`)
- **Classes**: PascalCase (`AuthService`, `Tenant`, `Service`, `Plan`)
- **Functions/methods**: snake_case (`get_by_username`, `create_tenant`)
- **Constants**: UPPER_SNAKE_CASE for module-level constants
- **Private methods**: `_leading_underscore` (Python convention)
- **Type aliases**: PascalCase (`CurrentUser`, `DbDep`)

## Testing

- Test framework: `pytest` + `pytest-asyncio`
- Test database: in-memory SQLite via `aiosqlite` (see `conftest.py`)
- Evolution API disabled in tests (`evolution_client.api_key = ""`)
- Fake Redis (`_FakeRedis`, `_FakeManager`) used for endpoint tests
- Fixtures: `db_session`, `client`, `master_user`, `active_tenant_user`, `deactivated_tenant_user`, `auth_headers`

## Dependency Injection

FastAPI dependencies live in `app/api/dependencies.py`:
- `get_db` — async SQLAlchemy session per request
- `get_current_user` — JWT token validation + user loading
- `require_role(role)` — role-based access control
- `verify_n8n_api_key_header` — API key validation for integrations

## Security

- Passwords: bcrypt via `bcrypt` library (not passlib)
- JWTs: `python-jose` with HS256 algorithm
- Refresh tokens: SHA-256 hashed, stored in `refresh_sessions` table
- Token rotation: refresh token revoked after use (rotation)
- API key: `X-API-Key` header validated against `settings.n8n_api_key`
- No passwords stored in Redis or logs

## Validation

All field validation goes through `app/core/input_validation/`. This is the single source of truth used by:
- Pydantic schema `@field_validator` decorators
- WhatsApp console flow step handlers
- Service-layer defensive normalization

Error codes are machine-readable strings (`username_required`, `phone_invalid`) mapped to translated messages via the i18n system.

## Phone Format

All phone numbers stored as canonical digits-only (no `+` prefix, no `@c.us` JID suffix, no `:N` device suffix). Key functions:
- `normalize_phone()` in `app/core/phone.py`
- `_strip_phone_suffixes()` in `app/core/input_validation/contact_validators.py`
- `validate_phone()` in `app/core/input_validation/contact_validators.py`

## I18n / Localization Conventions

- **Backend is source of truth**: All translation strings live in `app/core/i18n/` as Python dicts in `catalogs_en_*.py` and `catalogs_es_*.py` files.
- **Catalogs**: In-memory dicts loaded at import. No per-request file I/O. Precomputed merged catalogs with English fallback at startup.
- **Translation function**: `t(locale, key, **params)` — named-placeholder templates via `str.format`. Missing keys fall back to English; warning logged with in-process counter.
- **User-facing errors**: Services raise `UserFacingError(code, params)`; endpoints catch and translate via `translate_error(locale, exc)`.
- **Locale resolution**: REST endpoints use `resolve_locale(db, tenant_id)` from `app/api/dependencies.py`; WhatsApp tenant console uses `_current_locale` ContextVar set per-message.
- **Order of error handling**: Endpoints must catch `UserFacingError` *before* `ValueError` to enable i18n translation.
- **`resolve_locale()` timing**: Must be called *before* mutating service calls. Post-rollback RLS context may prevent reading tenant row after a failed transaction.
- **Frontend contract**: All frontend strings come from `GET /api/v1/i18n/catalog` — no translated strings hardcoded in frontend source.
- **WhatsApp console**: Tenant messages use `self._t(key, **params)` which reads `_current_locale` ContextVar. Master console stays hardcoded Spanish.
- **n8n**: Pure transport — no translation logic. Backend renders all localized messages.
- **Missing key behavior**: English fallback + `logger.warning` at 1st, 10th, 100th, 1000th, and every 10000th occurrence.

## WhatsApp / Telegram Reply Templates

Tenant WhatsApp console uses i18n key constants stored as class-level attributes (`KEY_MAIN_MENU`, `KEY_HELP_TEXT`, etc.) and resolved via `self._t()`. Master console continues with hardcoded Spanish class constants.

## Redis Keys

| Pattern | Purpose | TTL |
|---------|---------|-----|
| `session:{phone}` | Ephemeral conversation state | 15 min (configurable) |
| `wa:auth:{phone}` | Auth session after credential verification | 15 min (configurable) |
| `wa:auth:fail:{phone}` | Consecutive failure counter | 15 min window |
| `wa:auth:lock:{phone}` | Lockout marker after threshold | 5 min (configurable) |
| `session:admin:{phone}` | Tenant conversation state | 15 min (configurable) |

## n8n Integration Conventions

1. **Config Set node pattern**: All environment-specific values (backend URL, API keys, Evolution API URL) live in a single n8n Set node named `Config`. This works around the missing Variables UI in n8n community edition. Values are referenced via `$('Config').first().json.<field_name>`.
2. **neverError**: Both HTTP Request nodes (Console Call and Evolution API Send) set `neverError: true`. This prevents workflow failure when backend or Evolution API returns non-2xx responses.
3. **Input normalisation**: The `Parse Input` Code node always normalises phone numbers (strip JID suffixes, `+` prefix, device suffixes) before passing to backend.
4. **Reply fallback**: The `Merge Reply` Code node provides a static Spanish fallback message when backend returns no reply.
5. **Workflow files**: Exported as `n8n/Trackpal WhatsApp Bot.json` and `n8n/Trackpal Subscription Reminders.json`. Config values are visible in plaintext in the JSON export; treat both files as secrets-bearing.

## Migration Guidelines

- New migrations use Alembic's auto-generation or manual DDL
- Phone value migrations must detect cross-table collisions before applying changes
- Backward compatibility: `get_by_phone` searches both canonical and `+`-prefixed variants

## Tenant Scope and RLS

- `Tenant` is the only tenant entity for active code; obsolete `tenant_profiles` was dropped after migration.
- Tenant WhatsApp console uses `session:admin:{phone}` as logical key for Redis session isolation.
- Subscription secrets are encrypted with Fernet via `app/core/encryption.py` and require `DATA_ENCRYPTION_KEY`.
- Tenant-scoped queries must filter by `tenant_id` in application code.
- Postgres/Supabase tenant-scoped operations must set transaction-local RLS context before SQL using dotted GUC names only: `app.current_user_id`, `app.current_role`, `app.active_tenant_id`.
- Master catalog operations require explicit switched tenant context. Do not infer tenant scope from arbitrary request payload IDs.
