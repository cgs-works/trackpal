# Phase 03: WhatsAppTenantConsoleFacade

## Objective

- Create the facade that auto-auths tenant admins by phone, resolves their tenant context, handles top-level session exit, and delegates the rest of the conversation to the tenant console service.

## Complexity / Risk

- Complexity: M
- Risk: Medium

## Scope

- Files/modules this phase may touch:
  - `backend/app/services/whatsapp_tenant_console_facade.py`
  - `backend/app/services/tenant_console_protocols.py`
  - `backend/tests/test_tenant_console_service.py`
  - `backend/app/services/tenant_service.py` (only if a dedicated owner lookup helper is preferred over `get_tenant()`)
- Files/modules this phase must not touch:
  - `backend/app/services/whatsapp_master_console_facade.py`
  - n8n workflow or Evolution integration code

## Preconditions

- Phase 01 endpoint routing is in place conceptually.
- Phase 02 protocol contracts are defined.
- The executor has confirmed how tenant lookup will work from `identify_by_phone()` results.

## Tasks

1. Create `WhatsAppTenantConsoleFacade` as a separate file/class.
   - Follow the orchestration style of `WhatsAppMasterConsoleFacade` where useful.
   - Omit auth-session, lockout, and Evolution-chat close responsibilities.
2. Define the constructor surface.
   - Required dependencies: `console_service`, `session_service`.
   - Optional dependency: `tenant_service`.
   - Instantiate `AuthService()` inside the facade, matching the existing facade style.
3. Implement `process_message()`.
   - Recommended signature: `process_message(phone, message, *, instance=None, db=None)` for endpoint parity.
   - Re-identify the caller if the team wants defense in depth; otherwise, accept pre-routed identity from the endpoint and document the chosen tradeoff.
   - Reject non-tenant and unknown callers with explicit Spanish replies.
4. Resolve the active tenant id.
   - Preferred minimal path: use `TenantService.get_tenant(db, identity["user_id"])`, since the current implementation already accepts either tenant id or owner user id.
   - If that implicit dual lookup feels too magical, add a dedicated owner-based helper and use that consistently.
5. Validate the tenant record before delegating.
   - Reject missing tenant rows.
   - Reject inactive tenant rows, even though `identify_by_phone()` already screens inactive tenants, so downstream service calls always have a real active tenant context.
6. Implement top-level `0` behavior.
   - Use logical phone key `admin:{phone}` when talking to `WhatsAppSessionService`.
   - If there is no active flow, clear the session and return a goodbye reply.
   - If there is an active flow, delegate to the tenant console service so it can perform contextual cancel behavior.
   - If backup Redis is active and the session is unexpectedly missing, return the documented contingency-safe response rather than crashing or accidentally logging the user out incorrectly.
7. Delegate all non-top-level behavior to `WhatsAppTenantConsoleService.process_message()` with the resolved `tenant_id` and session service.
8. Keep Redis infrastructure exception handling outside the facade if possible.
   - Let endpoint/helper-level code translate infra failures to `TEMPORARY_UNAVAILABLE`.
   - Do not swallow programming errors.
9. Add focused unit tests for facade-only behavior using mocks/fakes.

## Acceptance Criteria

- User-visible or system-observable result:
  - Tenant admins reach the tenant console only when their phone maps to an active tenant admin account.
  - Top-level `0` clears the tenant conversation session and returns a goodbye reply.
  - Non-tenant and unknown phones are rejected before any tenant flow runs.
- Required changed files:
  - `backend/app/services/whatsapp_tenant_console_facade.py`
  - `backend/tests/test_tenant_console_service.py`
- Required unchanged behavior:
  - Master facade behavior remains untouched.
  - Redis-unavailable handling still happens at the transport/wiring edge.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_tenant_console_service.py -q`
- Expected results:
  - Facade tests pass for unknown phone, wrong role, inactive tenant, active tenant, and top-level `0` behavior.
- Evidence to record in `SUMMARY.md`:
  - pytest summary line.
  - Final tenant-resolution strategy (`get_tenant(owner_user_id)` reuse vs new helper).

## Idempotence and Recovery

- Safe to re-run:
  - Facade unit tests are safe to rerun.
- Recovery if interrupted:
  - Keep facade self-contained so endpoint routing can continue pointing only to the Master path until tenant wiring is ready.
- Rollback notes:
  - Remove the tenant facade import/wiring and fallback to the pre-tenant endpoint behavior if this phase must be backed out.

## Exit Criteria

- [ ] `WhatsAppTenantConsoleFacade` exists and imports cleanly.
- [ ] Non-tenant and unknown callers are rejected explicitly.
- [ ] Active tenant admins resolve to a concrete `tenant_id`.
- [ ] Inactive tenants are rejected explicitly.
- [ ] Top-level `0` clears `session:admin:{phone}` and returns goodbye.
- [ ] Active-flow `0` is delegated for contextual cancel handling.
- [ ] Facade tests cover the main orchestration branches.
