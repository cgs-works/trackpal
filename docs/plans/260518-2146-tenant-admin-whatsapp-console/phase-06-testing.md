# Phase 06: Testing and Regression

## Objective

- Add comprehensive automated coverage for the new tenant-admin console behavior and update existing endpoint regressions so the new routing contract is explicit and durable.

## Complexity / Risk

- Complexity: L
- Risk: Medium

## Scope

- Files/modules this phase may touch:
  - `backend/tests/test_tenant_console_service.py`
  - `backend/tests/test_whatsapp_endpoint.py`
  - targeted existing client/catalog/profile/auth tests only if supporting schema changes require updates
- Files/modules this phase must not touch:
  - production runtime logic except for testability seams discovered during test implementation
  - real Redis, Evolution API, or n8n infrastructure

## Preconditions

- Phase 01 through Phase 05 are functionally wired.
- Test patterns from existing `test_whatsapp_*` suites have been reviewed.
- No schema changes are needed (Client has no email, Service/Plan are name-only — by design).
- **FINDING 4 applies here:** Existing endpoint tests expect unknown and tenant phones to receive the Master login prompt. If Phase 01 deferred test updates, this phase MUST update them. If Phase 01 already updated them, verify the new assertions are correct and add tenant-console-specific tests.

## Tasks

1. Create `backend/tests/test_tenant_console_service.py` as the primary tenant-console suite.
   - Reuse existing project patterns: async pytest, fake Redis/session service, and simple in-memory service doubles or mocks.
   - Avoid requiring real Redis.
2. Cover facade routing/orchestration scenarios.
   - unknown phone
   - inactive tenant
   - active tenant
   - top-level `0`
   - wrong-role rejection
3. Cover client flow scenarios.
   - list
   - list empty
   - create full wizard
   - create validation error
   - edit
   - deactivate with `CONFIRMAR`
   - delete inactive only
   - invalid input reprompt
4. Cover catalog flow scenarios.
    - list services
    - view service + plans
    - view plan
    - edit service name
    - edit plan name (no description, no price — by design)
5. Cover profile flow scenarios.
   - view profile
   - edit name
   - password change wrong current password
   - password change success
6. Cover zero-handling and contingency scenarios.
   - `0` cancels active flow
   - `0` exits at main menu
   - missing session after failover/reset returns deterministic recovery behavior
7. **Update `backend/tests/test_whatsapp_endpoint.py` to assert the new routing contract.**
    - Unknown phone: expect no-access reply, NOT Master login prompt.
    - Tenant phone: expect tenant menu, NOT Master login prompt.
    - Client phone: expect admin-only rejection.
    - Master behavior, JID normalization, response shape, and Redis-unavailable behavior remain covered.
    - **These assertions MUST be updated** — they will fail if left as-is.
8. Run targeted and full regression commands.
9. Record verification evidence and any deviations from the brainstorm field set in `SUMMARY.md`.

## Acceptance Criteria

- User-visible or system-observable result:
  - Automated tests prove the tenant-admin console behavior rather than relying on manual reasoning.
  - Existing endpoint expectations are updated to the new routing contract.
- Required changed files:
  - `backend/tests/test_tenant_console_service.py`
  - `backend/tests/test_whatsapp_endpoint.py`
- Required unchanged behavior:
  - Test suite remains independent of real Redis and external WhatsApp/Evolution infrastructure.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_tenant_console_service.py tests/test_whatsapp_endpoint.py -q`
  - `cd backend && uv run pytest tests/test_auth.py tests/test_clients.py tests/test_catalog.py tests/test_profile.py -q`
  - `cd backend && uv run pytest -q`
- Expected results:
  - Tenant-console focused tests pass.
  - Endpoint routing regressions pass.
  - Broader backend suite remains green.
- Evidence to record in `SUMMARY.md`:
  - pytest summary lines for targeted and full runs.
  - Any test-count note if the suite grows beyond the brainstorm's 18-scenario baseline.

## Idempotence and Recovery

- Safe to re-run:
  - All pytest commands are safe to rerun.
- Recovery if interrupted:
  - Land tests in layers: facade tests first, then service-flow tests, then endpoint regressions.
- Rollback notes:
  - If unstable tests appear, back out only the tenant-console-specific assertions rather than loosening existing unrelated regression coverage.

## Exit Criteria

- [ ] `test_tenant_console_service.py` exists and imports cleanly.
- [ ] Facade, client flow, catalog flow, profile flow, and zero-handling scenarios are covered.
- [ ] Endpoint tests assert the new role-routing behavior.
- [ ] No real Redis dependency exists in the tenant-console test path.
- [ ] Targeted pytest commands pass.
- [ ] Full backend pytest pass is recorded.
