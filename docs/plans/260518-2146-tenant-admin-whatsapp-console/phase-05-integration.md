# Phase 05: Integration Wiring

## Objective

- Connect the routing layer, new facade, new service, and real concrete dependencies so the tenant-admin console works end-to-end through the existing `/n8n/console` endpoint.

## Complexity / Risk

- Complexity: S
- Risk: Low

## Scope

- Files/modules this phase may touch:
  - `backend/app/api/v1/endpoints/integrations.py`
  - `backend/app/services/__init__.py`
  - `backend/tests/test_whatsapp_endpoint.py`
- Files/modules this phase must not touch:
  - frontend code
  - n8n workflow and Evolution API configuration
  - Master Console implementation logic

## Preconditions

- Phase 01 routing helper structure exists.
- Phase 03 facade imports cleanly.
- Phase 04 tenant console service imports cleanly and has passing unit tests.

## Tasks

1. Export the new tenant-console symbols.
   - Update `backend/app/services/__init__.py` to expose `WhatsAppTenantConsoleFacade` and `WhatsAppTenantConsoleService`.
   - Export protocol symbols too if they improve discoverability without creating circular imports.
2. Wire `_handle_tenant_console()` with real services.
   - Instantiate `ClientService`, `CatalogService`, and `ProfileService`.
   - Reuse `TenantService` for tenant lookup.
   - Reuse `WhatsAppSessionService` with the existing Redis manager.
3. Preserve Redis contingency behavior.
   - Missing manager still returns `TEMPORARY_UNAVAILABLE`.
   - Runtime Redis failures still return `TEMPORARY_UNAVAILABLE`.
   - Do not silently fall back to a stateless tenant flow.
4. Keep endpoint contract stable.
   - Response model remains `WhatsAppConsoleResponse` with only `reply`.
   - API key auth remains unchanged.
   - JID-style phone normalization remains intact.
5. If Phase 04 added client/catalog schema support, ensure the real concrete services imported here are the updated ones and that no circular imports are introduced.
6. Add or update integration tests that exercise the live FastAPI endpoint with fake Redis manager injection.

## Acceptance Criteria

- User-visible or system-observable result:
  - The tenant-admin console works end-to-end through the existing endpoint.
  - Endpoint reply shape and API-key transport contract remain unchanged.
  - Redis outages still surface as a reply, not an HTTP 500.
- Required changed files:
  - `backend/app/api/v1/endpoints/integrations.py`
  - `backend/app/services/__init__.py`
  - `backend/tests/test_whatsapp_endpoint.py`
- Required unchanged behavior:
  - Master Console endpoint contract remains stable.
  - No external workflow/config changes are needed.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_whatsapp_endpoint.py tests/test_tenant_console_service.py -q`
- Expected results:
  - Endpoint-level tenant and master routing tests pass.
  - Tenant-console imports are exercised through the real endpoint stack.
- Evidence to record in `SUMMARY.md`:
  - pytest summary line.
  - Final list of real services wired into `_handle_tenant_console()`.

## Idempotence and Recovery

- Safe to re-run:
  - Endpoint tests with fake Redis manager are safe to rerun.
- Recovery if interrupted:
  - Keep tenant service/facade wiring behind `_handle_tenant_console()` so the rest of the file remains easy to revert.
- Rollback notes:
  - Remove tenant-specific exports and endpoint branch wiring to restore the previous endpoint topology.

## Exit Criteria

- [ ] New tenant-console symbols are exported cleanly.
- [ ] `_handle_tenant_console()` uses real `ClientService`, `CatalogService`, `ProfileService`, and `TenantService`.
- [ ] Redis contingency behavior matches the Master path.
- [ ] Endpoint response shape remains unchanged.
- [ ] Endpoint integration tests pass.
