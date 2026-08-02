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

For detailed conventions on error handling and logging, see:
- [Error Handling](error-handling.md)
- [Logging Guidelines](logging-guidelines.md)

## Validation

All field validation goes through `app/core/input_validation/`. This is the single source of truth used by:
- Pydantic schema `@field_validator` decorators
- WhatsApp console flow step handlers
- Service-layer defensive normalization

Error codes are machine-readable strings (`username_required`, `phone_invalid`) mapped to translated messages via the i18n system.

## Phone Format

All phone numbers stored as canonical digits-only (no `+` prefix, no `@c.us` JID suffix, no `:N` device suffix).

LID rule:
- Inputs containing `@lid` are **not** canonical phones.
- `normalize_phone()` must return `None` for `@lid` values.
- LID identity uses dedicated `whatsapp_lid` columns (master/tenant/client), not phone fields.

Key functions:
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

## WhatsApp Console Navigation Convention

All WhatsApp consoles follow the strict numeric navigation contract:
- `8` — Siguiente / Next (advance to next page/screen)
- `9` — Regresar / Back (return to previous screen without cancelling session)
- `0` — Cancelar / Cancel (cancel flow or close console)

The shared module `app/services/whatsapp_navigation.py` provides helper predicates:
- `is_cancel(msg)` — returns True for `0`, `cancelar`, `cancel`, `salir`, `cerrar`, `exit`, `close`
- `is_back(msg)` — returns True for `9`
- `is_next(msg)` — returns True for `8`

A screen-stack API (`push_screen`, `pop_screen`, `replace_screen`, `clear_navigation`) is available for flows that require multi-screen navigation tracking, stored in session `temp_data["_nav"]`.

Contract tests in `test_whatsapp_console_navigation_contract.py` scan all source and catalog files for conflicting navigation patterns.

## Redis Keys

| Pattern | Purpose | TTL |
|---------|---------|-----|
| `session:{phone}` | Ephemeral conversation state | 15 min (configurable) |
| `wa:auth:{phone}` | Auth session after credential verification | 15 min (configurable) |
| `wa:auth:fail:{phone}` | Consecutive failure counter | 15 min window |
| `wa:auth:lock:{phone}` | Lockout marker after threshold | 5 min (configurable) |
| `session:admin:{phone}` | Tenant conversation state | 15 min (configurable) |
| `wa:client_ctx:{admin_phone}` | Client Context Shortcut session state | 5 min |
| `session:unreg:{phone}` or `session:unreg:{lid}` | Unauthenticated code lookup session state (unregistered identity) | 15 min (configurable) |
| `stepup:fail:{user_id}` | Consecutive step-up failure counter (export/deletion) | 15 min window |
| `stepup:lock:{user_id}` | Step-up lockout marker after threshold | 15 min |
| `mailbox:lookup:queue` | Pending external lookup job queue | Until popped |
| `mailbox:lookup:queue:seen` | Queue deduplication members | Until popped |
| `lookup:dispatch-lock:{job_id}` | Short-lived per-job dispatch lock | 90 sec (configurable) |
| `lookup:lease:{job_id}` | Execution lease metadata | Lease lifetime |
| `lookup:executor-leases:{executor_id}` | Sorted set of leases used for capacity counting | Lease lifetime |
| `lookup:callback-nonce:{executor_id}:{nonce}` | Single-use callback replay protection | Signature skew window |
| `lookup:result:{job_id}` | Fernet-encrypted lookup result | 120 sec (configurable) |
| `lookup:executor-cooldown:{executor_id}` | Executor failure cooldown marker | 300 sec (configurable) |

## n8n Integration Conventions

1. **Config Set node pattern**: All environment-specific values (backend URL, n8n API key, Evolution base URL) live in a single n8n Set node named `Config`. This works around the missing Variables UI in n8n community edition. Values are referenced via `$('Config').first().json.<field_name>`.
2. **neverError**: Both HTTP Request nodes (Console Call and Evolution Send) set `neverError: true`. This prevents workflow failure when backend or Evolution returns non-2xx responses.
3. **Input normalisation**: The `Parse Input` Code node derives `phone` from `senderPn` first. If inbound id is `@lid` and no PN exists, send empty `phone` plus `sender_lid`; never derive phone digits from LID.
4. **Reply fallback**: The `Merge Reply` Code node provides a static Spanish fallback message when backend returns no reply, except when `no_reply=true` in the response (the fallback is skipped to keep the response silent).
5. **``reply_to`` routing**: When the backend returns `reply_to`, the Evolution Go Send node uses that JID as the send target instead of the original sender's phone. This keeps contextual administrative replies private to the admin chat.
6. **``no_reply`` silence**: When the backend returns `no_reply=true`, a new IF node routes the data directly to Check Close Session, bypassing all Evolution API send calls. This prevents blocked identities and context collisions from generating user-facing messages.
5. **Workflow files**: Exported as `n8n/TrackPal WhatsApp Bot.json` and `n8n/TrackPal Subscription Reminders.json`. Config values are visible in plaintext in the JSON export; treat both files as secrets-bearing.

## Migration Guidelines

- New migrations use Alembic's auto-generation or manual DDL
- Phone value migrations must detect cross-table collisions before applying changes
- Backward compatibility: `get_by_phone` searches both canonical and `+`-prefixed variants

## Tenant Scope and RLS

- `Tenant` is the only tenant entity for active code; obsolete `tenant_profiles` was dropped after migration.
- Tenant WhatsApp console uses `session:admin:{phone}` as logical key for Redis session isolation.
- Subscription secrets are encrypted with Fernet via `app/core/encryption.py` and require `DATA_ENCRYPTION_KEY`.
- Evolution instance tokens are encrypted with the same Fernet mechanism (`app/core/encryption.py`) and `DATA_ENCRYPTION_KEY`, stored in `tenants.evolution_instance_token`.
- Tenant-scoped queries must filter by `tenant_id` in application code.
- Postgres/Supabase tenant-scoped operations must set transaction-local RLS context before SQL using dotted GUC names only: `app.current_user_id`, `app.current_role`, `app.active_tenant_id`.
- Master catalog operations require explicit switched tenant context. Do not infer tenant scope from arbitrary request payload IDs.
- Export jobs (`export_jobs`) have RLS policies restricting access to the owning tenant and master role.
- Master export operations (`/tenants/{tenant_id}/export/*`) set internal RLS context via `set_internal_rls_context()` before accessing tenant-owned data.
- Tenant Data Export uses an isolated storage adapter (`app/services/export_storage/`) with a dedicated private R2 bucket — never the public diagnostic bucket.
