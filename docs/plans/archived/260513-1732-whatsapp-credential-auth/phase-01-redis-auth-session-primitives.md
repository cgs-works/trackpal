# Phase 1 — Redis auth session + lockout primitives

**Complexity:** M

## Objective

Introduce Redis-backed primitives to support WhatsApp credential authentication:

- An **authenticated session** keyed by phone with TTL (15 minutes).
- A **failed-attempt counter** and **temporary lockout** keyed by phone.

This phase must be safe to ship on its own (not yet wired into the endpoint).

## Tasks (2–10 min each)

1. **Add settings for lockout policy**
   - Edit: `backend/app/core/config.py`
   - Add env-backed ints with sensible defaults:
     - `whatsapp_auth_fail_threshold` (default `5`)
     - `whatsapp_auth_lock_minutes` (default `5`)
     - `whatsapp_auth_fail_window_minutes` (default `15`)
   - Keep auth-session TTL using existing `whatsapp_session_ttl_minutes`.

2. **Define Pydantic models for auth + lockout payloads**
   - New file: `backend/app/services/whatsapp_auth_session_service.py`
   - Models:
     - `WhatsAppAuthSession(phone, user_id, username, role, authenticated_at)`
     - `WhatsAppAuthFailState(count, first_failed_at, last_failed_at)`
     - `WhatsAppAuthLockState(locked_until)`

3. **Implement Redis key helpers and basic CRUD**
   - In `whatsapp_auth_session_service.py`
   - Key prefixes (keep them explicit, stable, and testable):
     - `wa:auth:`
     - `wa:auth:fail:`
     - `wa:auth:lock:`
   - Methods:
     - `get_auth_session(phone)` / `set_auth_session(session, ttl_seconds)` / `clear_auth_session(phone)`
     - `get_lock_state(phone)`

4. **Implement failure tracking + lockout logic**
   - In `whatsapp_auth_session_service.py`
   - Methods:
     - `record_failed_attempt(phone, *, now=...) -> tuple[count, locked]`
     - If `count >= threshold`: set lock key with `locked_until` and TTL `lock_minutes`.
     - Clear/reset fail counter on lock.
   - Ensure **no password** is persisted.

5. **Add isolated unit tests for the new service**
   - New file: `backend/tests/test_whatsapp_auth_session_service.py`
   - Use the same fake-redis pattern used in `test_whatsapp_session_service.py`.
   - Cover:
     - Auth session set/get/clear round-trip.
     - Lockout is created after N failures.
     - Lockout payload includes a future `locked_until`.
     - Fail counter resets after lock is set.

6. **Wire into typing/export conventions**
   - Ensure new service is importable as `app.services.whatsapp_auth_session_service`.
   - If the repo uses `backend/app/services/__init__.py` exports, update accordingly (only if needed).

## Verification

- Run isolated tests:
  - `cd backend && uv run pytest tests/test_whatsapp_auth_session_service.py -v`
- Run existing session tests to ensure no regressions:
  - `cd backend && uv run pytest tests/test_whatsapp_session_service.py -v`

## Exit Criteria

- New settings are available via env vars and have defaults.
- Auth session + lockout primitives work via tests using fake Redis.
- No existing WhatsApp CRUD/menu tests are modified in this phase.
