# Phase 1: Phone Canonicalization and Database Normalization

**Complexity:** M  
**Dependencies:** None

## Objective

Ensure every phone value used by the backend is canonical digits-only text without `+`, including Master/Tenant database storage, n8n identity lookup, WhatsApp console phone handling, and Redis session key inputs.

## Preconditions

- Existing backend tests pass before starting.
- Current phone fields remain `String(50)` in `master_profiles.phone` and `tenant_profiles.phone`; no schema type change is required.

## Tasks

1. Inspect all current phone input/output paths: `backend/app/schemas/tenant.py`, `backend/app/schemas/me.py`, `backend/app/services/profile_service.py`, `backend/app/services/tenant_service.py`, `backend/app/services/auth_service.py`, `backend/app/crud/users.py`, `backend/app/api/v1/endpoints/integrations.py`, and `backend/scripts/seed.py`.
2. Add a shared phone utility in `backend/app/core/phone.py` with a function/class that returns digits only, removes `+`, removes WhatsApp suffixes like `@c.us` and `@s.whatsapp.net`, strips device suffixes after `:`, and returns `None` for blank optional input.
3. Replace the local `_normalize_whatsapp_phone` helper in `backend/app/api/v1/endpoints/integrations.py` with the shared normalizer.
4. Apply normalization in `TenantCreate.phone` and `TenantUpdate.phone` validators in `backend/app/schemas/tenant.py`.
5. Apply normalization in profile update schemas or service paths that accept phone values in `backend/app/schemas/me.py` and/or `backend/app/services/profile_service.py`.
6. Apply normalization before Master seed persistence in `backend/scripts/seed.py`, including default `settings.master_phone`.
7. Apply normalization inside `AuthService.identify_by_phone()` before calling `user_crud.get_by_phone()`.
8. Apply normalization at the start of `user_crud.get_by_phone()` as a defensive data-access guard.
9. Update WhatsApp console request handling so `phone` passed to `WhatsAppConsoleService.process_message()` and `WhatsAppSessionService` is canonical digits-only.
10. Add Alembic migration under `backend/alembic/versions/` to backfill existing phone values in `master_profiles.phone` and `tenant_profiles.phone` to digits-only values.
11. In the migration, detect normalization collisions within and across the two profile tables and fail with an explicit error instead of silently overwriting uniqueness assumptions.
12. Add tests in `backend/tests/test_phone_normalizer.py` for `+123`, spaces/dashes, `123@c.us`, `123@s.whatsapp.net`, `123:45@s.whatsapp.net`, empty optional values, and already-canonical values.
13. Extend `backend/tests/test_auth.py` identify tests so lookup works when request phone includes `+` or WhatsApp suffix but stored DB phone is canonical without `+`.
14. Extend `backend/tests/test_tenants.py` and/or `backend/tests/test_profile.py` to prove tenant/profile phone persistence is canonical without `+`.
15. Update existing WhatsApp tests that assert `+` phone values so expected session keys/identity values use digits-only canonical strings.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_phone_normalizer.py -v`
  - `cd backend && uv run pytest tests/test_auth.py tests/test_tenants.py tests/test_profile.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_endpoint.py tests/test_whatsapp_session_service.py -v`
  - `cd backend && uv run alembic upgrade head`
  - `cd backend && uv run pytest -v`
- Expected results:
  - Phone normalization tests pass for all PRD formats.
  - New and updated Tenant/Profile records store phones without `+`.
  - n8n identify accepts `+` and JID-style inputs but looks up canonical DB values.
  - WhatsApp session keys are based on canonical digits-only phone values.
  - Alembic migration applies successfully on non-colliding data.

## Exit Criteria

- A single shared phone normalizer is used by identity lookup, persistence, seed, and WhatsApp console handling.
- Database phone storage is canonical digits-only for Master and Tenant profiles.
- Migration/backfill exists and fails safely on normalization collisions.
- No remaining test expectation requires phone values to be stored with `+`.
