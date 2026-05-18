# Phase 03: Client Management API

## Objective

- Add tenant-scoped backend APIs for client lifecycle management.

## Scope

- Files/modules this phase may touch: `backend/app/schemas/client.py`, `backend/app/services/client_service.py`, `backend/app/api/v1/endpoints/clients.py`, `backend/app/api/v1/router.py`, `backend/app/services/tenant_service.py`, `backend/tests/test_clients.py`, `backend/tests/test_tenants.py`.
- Files/modules this phase must not touch: frontend UI.

## Preconditions

- Phase 1 and Phase 2 completed.
- Auth dependencies can provide active tenant id for tenant role.

## Tasks

1. Inspect `CatalogService` and `catalog.py` for tenant-scoped endpoint and conflict patterns.
2. Create client schemas: create/update/response, with full name, local username, password on create, phone, active status, technical username in response.
3. Create `ClientService` with list/get/create/update/deactivate/activate/delete inactive.
4. Build technical username from tenant `client_prefix` plus local username.
5. Catch `IntegrityError`, rollback, and raise `ValueError` for duplicate username/phone/technical username.
6. Revoke client refresh sessions on deactivate.
7. Delete only inactive clients; delete associated user/profile consistently and ensure no orphan `users` rows remain.
8. Update `TenantService.update_tenant()` so prefix changes recompute affected client `users.username` values transactionally.
   - Catch `IntegrityError` from username collisions, rollback, raise a conflict-domain `ValueError`, and map endpoint response to HTTP 409.
   - Return a clean error message suitable for Master UI display.
9. Update client local username edits so associated `users.username` is recomputed transactionally.
10. Update `TenantService.delete_tenant()` so tenant deletion explicitly deletes associated client owner users before/with tenant deletion.
   - Use FK-safe order: delete client owner `users` rows and rely on cascade to remove `clients`, or delete `clients` first and then their owner `users`; verify no orphan `client` role users remain.
11. Add `/clients` endpoints and include router.
12. Add tests for CRUD, duplicates, cross-tenant access, lifecycle, inactive login, prefix update login, local username update login, and tenant deletion client-user cleanup.
13. Verify and record results in `SUMMARY.md`.

## Acceptance Criteria

- Tenant can manage clients through REST API.
- Duplicate local username/phone per tenant returns 409.
- Cross-tenant client access is blocked.
- Prefix/local username changes keep `users.username` consistent.
- Tenant deletion does not leave orphan `client` role users.
- Prefix collision during tenant prefix edit returns HTTP 409, not 500.
- Existing tenant/catalog APIs still work.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_clients.py tests/test_tenants.py tests/test_auth.py -q`
- Expected results:
  - Client lifecycle tests pass.
- Evidence to record in `SUMMARY.md`:
  - pytest result line.

## Idempotence and Recovery

- Safe to re-run: tests and API calls against fresh test DB.
- Recovery if interrupted: finish service before enabling router to avoid broken imports.
- Rollback notes: remove router include and client service/schema if backing out.
  - If prefix update fails mid-transaction, rollback must leave old prefix and old client login usernames intact.

## Exit Criteria

- [ ] `/api/v1/clients` CRUD works for tenant.
- [ ] Lifecycle rules enforced.
- [ ] Prefix/local username changes keep `users.username` consistent.
- [ ] Tenant delete cleans associated client users.
- [ ] Prefix update collision rolls back and returns 409 with clean API/UI message.
- [ ] Tests cover conflicts and cross-tenant access.
