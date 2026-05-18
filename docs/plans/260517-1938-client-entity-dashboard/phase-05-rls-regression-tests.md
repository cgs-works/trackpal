# Phase 05: RLS and Regression Tests

## Objective

- Harden client isolation and complete regression coverage across backend roles.

## Scope

- Files/modules this phase may touch:
  - Client/tenant migration RLS SQL.
  - `backend/app/core/database.py`
  - `backend/app/api/dependencies.py`
  - `backend/tests/test_rls_policy_sql.py`
  - `backend/tests/test_clients.py`
  - `backend/tests/test_auth.py`
  - `backend/tests/test_catalog.py`
- Files/modules this phase must not touch:
  - Frontend except if test-driven API response mismatch requires prior phase adjustment.

## Preconditions

- Phases 1-4 completed.
- Client API and frontend build already pass targeted checks.

## Tasks

1. Context: inspect current RLS tests and migration policy strings.
2. Finalize `clients` RLS policies:
   - Enable and force RLS on `clients`.
   - `USING` policy:
     - tenant role: parent tenant owned by current user and active.
     - client role: `owner_user_id == app.current_user_id` and parent tenant active and client active.
     - master role: only with active tenant context if support access is kept by shared dependency.
   - `WITH CHECK` policy:
     - tenant writes: row tenant must be owned by current tenant user and active.
     - client writes: no general client writes to `clients` unless needed for password-only flows; password updates touch `users`, not `clients`.
     - master writes: only if explicit active tenant context is allowed.
3. Verify dependency behavior:
   - `set_rls_context()` permits `client` with active tenant id.
   - Missing active tenant id for `client` maps to HTTP error.
4. Add SQL policy tests:
   - RLS enabled/forced on `clients`.
   - Policy includes tenant ownership checks.
   - Policy includes client self-access check.
   - `WITH CHECK` is role-aware and not only `tenant_id == active_tenant_id`.
5. Add API regression tests:
   - Tenant A cannot list/read/update/delete Tenant B clients.
   - Tenant A cannot manipulate Tenant B client `users` rows indirectly by guessing client ids.
   - Client cannot call tenant client management endpoints.
   - Client cannot access catalog management endpoints unless explicitly allowed; expected 403/404.
   - Client dashboard cannot expose other client data.
6. Run broader backend test suite and fix only issues in scope.
7. Record evidence.

## Acceptance Criteria

- User-visible or system-observable result:
  - Client data is isolated at API and DB-policy levels.
- Required changed files:
  - RLS migration/policy tests/client auth tests as needed.
- Required unchanged behavior:
  - Existing tenant catalog RLS tests still pass.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_auth.py tests/test_clients.py tests/test_catalog.py tests/test_rls_policy_sql.py -q`
  - `cd backend && uv run pytest -q`
- Expected results:
  - Targeted and full backend tests pass.
- Evidence to record in `SUMMARY.md`:
  - pytest result lines.

## Idempotence and Recovery

- Safe to re-run:
  - All tests.
- Recovery if interrupted:
  - Fix policy/test mismatches before docs phase.
- Rollback notes:
  - RLS policy edits stay in migration; if changed after migration exists, create follow-up migration rather than mutating applied migration in shared environments.

## Exit Criteria

- [ ] RLS SQL tests cover `clients`.
- [ ] API tests prove cross-tenant isolation.
- [ ] Full backend tests pass.
