# Phase 02: Backend Auth and Client Context

## Objective

- Make `client` a safe authenticated role with valid tenant context and dashboard/profile behavior.

## Scope

- Files/modules this phase may touch:
  - `backend/app/services/auth_service.py`
  - `backend/app/api/dependencies.py`
  - `backend/app/api/v1/endpoints/auth.py`
  - `backend/app/api/v1/endpoints/dashboard.py`
  - `backend/app/api/v1/endpoints/me.py`
  - `backend/app/services/profile_service.py`
  - `backend/app/schemas/auth.py`
  - `backend/app/schemas/dashboard.py`
  - `backend/app/schemas/me.py`
  - `backend/tests/test_auth.py`
- Files/modules this phase must not touch:
  - Frontend.
  - Full client CRUD endpoints beyond minimal support needed for tests.

## Preconditions

- Phase 1 completed.
- `Client` model exists and can be queried.

## Tasks

1. Context: inspect existing tenant auth hardening in `AuthService.create_tokens()`, refresh flow, and `get_current_user()`.
2. Extend active tenant resolution:
   - For `client`, resolve active tenant through `Client.owner_user_id == user.id`, `Client.is_active`, and parent `Tenant.is_active`.
   - Return `None` if missing/inactive.
3. Extend token creation:
   - `create_tokens()` returns `None` for client if no active tenant context.
   - Access token includes `active_tenant_id` for client.
4. Extend refresh logic:
   - Reject refresh for inactive clients or inactive parent tenant.
   - Preserve or recompute client active tenant context safely.
5. Extend dependencies:
   - `get_current_user()` validates client active status after decoding token.
   - Map invalid/missing client RLS context to HTTP 401/403, never 500.
   - Add `ClientUser` alias if useful.
6. Extend dashboard/profile:
   - Add `ClientDashboardResponse`.
   - `/dashboard` returns readonly client profile payload for role `client`.
   - `/me` returns client profile fields.
   - `/me` profile update rejects client role with 403 or ignores unsupported edits; password change remains allowed.
7. Update auth schemas if needed to allow `role='client'` and include display/local username fields only where useful.
8. Add tests:
   - Client login returns token, role `client`, active tenant id.
   - Inactive client login returns 401.
   - Inactive tenant parent rejects client login/refresh.
   - Malformed client token missing active tenant id returns 401/403 on protected endpoint, not 500.
   - Client can change password.
   - Client cannot update readonly profile.
9. Verify and record results.

## Acceptance Criteria

- User-visible or system-observable result:
  - Client auth works only for active client + active tenant.
  - Client dashboard/profile endpoints do not crash.
- Required changed files:
  - Auth service/dependencies/dashboard/me schemas/tests.
- Required unchanged behavior:
  - Master and tenant login/refresh/switch-tenant behavior unchanged.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_auth.py tests/test_profile.py -q`
- Expected results:
  - Auth/profile tests pass including new client cases.
- Evidence to record in `SUMMARY.md`:
  - pytest result line.

## Idempotence and Recovery

- Safe to re-run:
  - Unit/API tests.
- Recovery if interrupted:
  - Keep role-specific changes isolated; revert client branches if master/tenant auth fails.
- Rollback notes:
  - Remove client role branches and tests if Phase 1 is rolled back.

## Exit Criteria

- [ ] Client tokens include active tenant id.
- [ ] Inactive client/tenant cannot authenticate.
- [ ] Client dashboard response works in backend tests.
- [ ] Existing auth behavior still passes.
