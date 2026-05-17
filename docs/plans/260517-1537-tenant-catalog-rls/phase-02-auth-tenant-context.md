# Phase 02: Auth, Tenant Context, and Existing Tenant Flows

## Objective

Move existing auth/profile/dashboard/tenant CRUD from `TenantProfile` to canonical `Tenant`, keep tenant login stable through `users`, and add Master switch-tenant context by reissuing tokens with `active_tenant_id`.

## Scope

- Files/modules this phase may touch:
  - `backend/app/core/security.py`
  - `backend/app/api/dependencies.py`
  - `backend/app/schemas/auth.py`
  - `backend/app/schemas/tenant.py`
  - `backend/app/services/auth_service.py`
  - `backend/app/services/tenant_service.py`
  - `backend/app/services/profile_service.py`
  - `backend/app/api/v1/endpoints/auth.py`
  - `backend/app/api/v1/endpoints/tenants.py`
  - `backend/app/api/v1/endpoints/me.py`
  - `backend/app/api/v1/endpoints/dashboard.py`
  - `backend/app/api/v1/endpoints/integrations.py`
  - relevant auth/tenant/profile/dashboard tests
- Files/modules this phase must not touch:
  - Catalog CRUD endpoints, except tenant context helpers used later.
  - Frontend UI except if needed to keep login response parsing stable; defer UI changes to Phase 5.

## Preconditions

- Phase 1 models and migration exist.
- `Tenant` can be queried by `owner_user_id`.
- Existing tests provide master and tenant user fixtures.

## Tasks

1. Context: search all `TenantProfile` references.
   - Use `rg "TenantProfile|tenant_profile|full_name" backend/app backend/tests`.
   - Classify references: canonical tenant CRUD, profile response, auth active check, WhatsApp adapter, tests.
2. Implement: update token helpers.
   - Extend `create_access_token` to accept optional `active_tenant_id`.
   - Keep existing `sub`, `role`, `type`, `exp` claims unchanged.
   - Include `active_tenant_id` only when available.
   - Refresh tokens can remain tenant-agnostic unless executor finds refresh flow must preserve active Master tenant.
3. Implement: update auth service.
   - Tenant login: authenticate `User(role="tenant")`, load `Tenant` by `owner_user_id`, reject inactive tenant, issue token with `active_tenant_id = tenant.id`.
   - Master login: issue token without active tenant.
   - Refresh tenant token: re-resolve owner tenant and include active tenant.
   - Refresh Master token: preserve `active_tenant_id` when the request provides a still-valid current access token or session context that already has an active tenant. Do not silently return an unswitched Master token while the UI is operating in tenant support mode.
   - If the existing refresh endpoint only receives a refresh token, extend refresh flow safely so Master support context can be preserved without trusting stale/invalid tenant IDs. Acceptable designs: include active tenant in refresh session metadata, accept current access token as optional context, or require explicit switch renewal before catalog calls. Document final choice.
4. Implement: add Master switch endpoint.
   - Endpoint candidate: `POST /api/v1/auth/switch-tenant` or `POST /api/v1/tenants/{tenant_id}/switch`.
   - Requires Master role.
   - Validates target tenant exists and is active.
   - Reissues access token (and optionally refresh token if current token model requires pair symmetry) with `active_tenant_id`.
   - Provide a way to clear support context, either a dedicated endpoint or a switch endpoint mode that returns an unswitched Master token.
   - Return same `TokenResponse` shape plus active tenant metadata.
5. Implement: update dependency layer.
   - Add a typed current-user/context object if helpful, e.g. `CurrentPrincipal` with `user`, `active_tenant_id`, `is_master`.
   - `get_current_user` should reject inactive tenant users using `Tenant.owner_user_id`.
   - Add tenant-scoped dependency for later phases:
     - tenant users: active tenant comes from their owner tenant;
     - master users: active tenant must be present and valid.
6. Implement: update tenant service and endpoints.
   - Master creates `User(role="tenant")` + `Tenant(owner_user_id=user.id, ...)`.
   - List/get/update/deactivate/activate/delete operate on `Tenant.id`, not user id.
   - Deactivation revokes refresh sessions for `tenant.owner_user_id`.
   - Delete inactive tenant deletes owner user only if that remains desired current behavior; otherwise document change. Recommended: preserve current behavior by deleting owner user with tenant.
   - Update response schemas with `id` = tenant id and `username` from owner user.
7. Implement: update profile/dashboard.
   - Tenant self-profile uses `Tenant` by owner user.
   - Master dashboard counts `Tenant` rows.
   - Profile response can keep public field names (`full_name`) mapped from `Tenant.name` for frontend compatibility, or update frontend in Phase 5.
8. Implement: update WhatsApp Master Console adapter.
   - Replace `TenantProfile` wrapper with `Tenant` wrapper exposing the interface expected by `WhatsAppConsoleService`.
   - Preserve fields `id`, `full_name`, `email`, `phone`, `username`, `evolution_instance_name`, `is_active`, `created_at` for console compatibility.
9. Verify: update and run targeted tests.
10. Confirm: record token claim shape and switch endpoint path in `SUMMARY.md` decision/progress notes.

## Acceptance Criteria

- User-visible or system-observable result:
  - Existing Master login and tenant login still work.
  - Master tenant CRUD still works against canonical `tenants`.
  - Tenant dashboard/profile still loads.
  - Master can switch into an active tenant context and receive token with `active_tenant_id`.
  - Master token refresh preserves valid active tenant context or fails/forces reswitch predictably; it must not silently drop tenant context mid-catalog workflow.
- Required changed files:
  - Auth/security/dependencies/schemas/services/endpoints listed above.
- Required unchanged behavior:
  - Username/password auth remains.
  - Roles remain `master` and `tenant`.
  - Existing n8n API key auth remains unchanged.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_auth.py -v`
  - `cd backend && uv run pytest tests/test_tenants.py -v`
  - `cd backend && uv run pytest tests/test_profile.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -v`
- Expected results:
  - Tenant login returns `user.role == "tenant"` and active tenant context.
  - Deactivated tenant login/refresh rejected.
  - Master switched token refresh behavior is covered and deterministic.
  - Master-only tenant endpoints remain protected.
  - WhatsApp Master Console tests adapt to new tenant model.
- Evidence to record in `SUMMARY.md`:
  - Test commands and pass/fail summary.
  - Final switch endpoint path.

## Idempotence and Recovery

- Safe to re-run:
  - Auth tests recreate fixture data.
  - Switch endpoint can be called repeatedly and should return fresh token each time.
- Recovery if interrupted:
  - If auth shape changes break frontend, keep backend response backward-compatible by preserving `user` object fields.
- Rollback notes:
  - Token claim changes are additive; rollback by ignoring `active_tenant_id` if needed.

## Exit Criteria

- [ ] No backend app code imports `TenantProfile` for active business logic except transitional migration/test compatibility.
- [ ] Tenant login derives active tenant from `owner_user_id`.
- [ ] Master switch tenant endpoint exists and is tested.
- [ ] Master support context clear/exit behavior exists and is tested.
- [ ] Master refresh preserves active tenant context or documented safe renewal behavior.
- [ ] Tenant CRUD and profile/dashboard work with `Tenant`.
- [ ] Phase progress noted in `SUMMARY.md`.
