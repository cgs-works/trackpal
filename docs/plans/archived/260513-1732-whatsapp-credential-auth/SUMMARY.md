# Implementation Plan: WhatsApp Credential Authentication (Master Console)

## Objective

- Decouple WhatsApp Master Console access from **phone-as-identity** by introducing a conversational **username + password** login.
- Keep **n8n transport-only**: receive message → call backend → send reply. No instance filters, no permission logic, no session persistence.
- Create an **ephemeral authenticated session in Redis** keyed by the current phone for **15 minutes**, after which the console requires login again.
- Add **temporary lockout** after consecutive credential failures to reduce brute-force risk.

PRD: `docs/prds/260513-1732-whatsapp-credential-auth/PRD.md`

## Scope

### In scope

- Backend-owned conversational login flow:
  - Prompt for `username`, then `password`.
  - Clear error messages for unknown username and wrong password.
  - Restrict access to role `master` only.
  - Global commands (`0`, `menu`, `menú`, `cancelar`, `ayuda`) remain consistent during login.
- Redis-backed **authenticated session** keyed by sender phone (canonical digits-only).
  - TTL: 15 minutes (reuse `WHATSAPP_SESSION_TTL_MINUTES`).
  - Separate from the existing **conversation flow session** so `0/menu` does **not** act as logout.
- Redis-backed **lockout state** (per phone) after repeated failures.
- Update `POST /api/v1/integrations/n8n/console` to:
  - Stop identifying the caller by phone.
  - Gate menu/CRUD behind the Redis authenticated session.
- n8n workflow export:
  - Remove instance filtering (e.g. `Is Sublify?`).
  - Replace backend/Evolution URLs and API keys with versionable placeholders (no secrets in repo).
- Automated tests for:
  - Login happy path + error paths.
  - Lockout behavior.
  - Expiration behavior (auth session removed → prompts login).
  - Tenant role credentials do not grant access.
  - No bypass to menu/CRUD without auth session.

### Out of scope (explicit)

- OTP / magic link / QR / device-trust hardening.
- Conversational login for role `tenant`.
- Explicit `/logout` command.
- Auditing/history persistence of failed attempts beyond what is required for lockout.

## Architecture & Approach

### Key idea

Introduce a **Redis auth session** keyed by phone that is created only after verifying **User credentials** (existing unified auth model). The existing WhatsApp CRUD/menu console remains backend-owned and unchanged in behavior, but it becomes **reachable only when an auth session exists**.

### Proposed backend components

- `WhatsAppAuthSessionService` (new):
  - `get_auth_session(phone)` / `set_auth_session(...)` / `clear_auth_session(phone)`.
  - Lockout helpers: `record_failed_login(phone)` / `get_lock_state(phone)`.
  - Redis keys (example):
    - `wa:auth:{phone}` (JSON payload, TTL 15m)
    - `wa:auth:fail:{phone}` (JSON payload, TTL = failure window)
    - `wa:auth:lock:{phone}` (JSON payload, TTL = lock duration)
- `WhatsAppMasterConsoleFacade` (new) or equivalent orchestration:
  1. Normalize phone.
  2. If locked → return lockout reply.
  3. If auth session exists → delegate to existing `WhatsAppConsoleService.process_message(is_master=True, ...)`.
  4. Otherwise run the conversational login flow (using the existing `WhatsAppSessionService` for multi-step state).

### Assumptions (make explicit)

- **Lockout policy defaults** (configurable): `5` failed attempts → lock for `5` minutes. Fail counter window: `15` minutes.
- Auth session TTL is **sliding** (refresh on successful/valid console progress), consistent with current WhatsApp session TTL semantics.
- Password must never be stored in Redis session payloads and must not be logged.

## Phases

- [x] **Phase 1 [M]: Redis auth session + lockout primitives** — Add settings, new auth-session service, and isolated unit tests.
- [x] **Phase 2 [L]: Conversational login flow + endpoint gating** — Implement username/password prompts, create auth session on success, and block menu/CRUD without auth.
- [x] **Phase 3 [M]: Security + regression coverage** — Brute-force lockout tests, expiry tests, role enforcement, and bypass regression tests.
- [x] **Phase 4 [S]: n8n workflow sanitization (placeholders + no instance filter)** — Update workflow JSON export and docs; ensure no secrets committed.
- [x] **Phase 5 [S]: Documentation updates + full verification** — Update ADR/architecture docs for the new auth model and run full test suite.

## Key File Targets (expected)

Backend:
- `backend/app/core/config.py` — add lockout settings.
- `backend/app/services/whatsapp_auth_session_service.py` — new Redis auth+lockout service.
- `backend/app/services/whatsapp_master_console_facade.py` (or similar) — new orchestrator.
- `backend/app/api/v1/endpoints/integrations.py` — console endpoint uses auth session gating; remove `identify_by_phone()` usage.
- `backend/app/services/whatsapp_console_service.py` — minimal changes only if needed (keep CRUD/menu stable).
- `backend/tests/test_whatsapp_credential_auth_flow.py` — new tests for login + lockout.
- `backend/tests/test_whatsapp_endpoint.py` — update contract tests for new behavior.

n8n/docs:
- `n8n/Trackpal WhatsApp Bot.json` — remove instance filter; replace secrets with env placeholders.
- `docs/architecture/n8n-workflow.md` — update to reflect placeholder pattern actually used in JSON.
- `docs/adr/0004-sesion-whatsapp-redis.md` — update the step “identify Master by phone” to “require Redis auth session; login via credentials”.
- (Optional) `docs/adr/0003-integracion-n8n-y-evolution-api.md` — ensure it reflects transport-only + no identity resolution in n8n.

## Verification Strategy

- Backend focused tests (per phase):
  - `cd backend && uv run pytest tests/test_whatsapp_credential_auth_flow.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -v`
- Full backend suite at the end:
  - `cd backend && uv run pytest -v`
- n8n workflow sanity checks:
  - JSON validity: `python -m json.tool "n8n/Trackpal WhatsApp Bot.json" > NUL` (Windows) / `> /dev/null` (bash)
  - Secrets check (example): `rg -n "onrender.com|X-API-Key|apikey" "n8n/Trackpal WhatsApp Bot.json"` and verify only placeholder/env expressions remain.

## Dependencies

- Redis connection manager already implemented (`app/core/redis_client.py`).
- Existing unified auth model + bcrypt verification (`AuthService.authenticate`).
- Existing WhatsApp Master Console CRUD/menu flows + tests.

## Risks & Mitigations

- **Accidental logout via reset commands** → keep auth session separate from conversation session; reset clears only the flow session.
- **Auth bypass by direct menu option** → always gate `process_message()` behind auth session in the facade/endpoint.
- **Lockout can be bypassed by clearing conversation session** → lockout stored in dedicated Redis keys.
- **Secrets committed in n8n export** → enforce placeholder/env usage and add a repo-level verification check step.

## Open Questions

- Exact lockout thresholds/durations (defaults proposed above) — confirm with product/security.
- Whether `/api/v1/integrations/n8n/identify` remains used elsewhere; if not, consider deprecating in a separate initiative.
