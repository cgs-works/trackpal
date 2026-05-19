# Phase 02: Protocols

## Objective

- Define protocol classes for tenant-console dependency injection so the new facade/service can depend on stable async contracts instead of concrete implementations.

## Complexity / Risk

- Complexity: S
- Risk: Low

## Scope

- Files/modules this phase may touch:
  - `backend/app/services/tenant_console_protocols.py` (new)
  - imports inside `backend/app/services/whatsapp_tenant_console_facade.py`
  - imports inside `backend/app/services/whatsapp_tenant_console_service.py`
- Files/modules this phase must not touch:
  - endpoint routing logic beyond imports
  - Master Console service/facade code

## Preconditions

- Phase 01 branching structure is planned.
- Current `ClientService` and `CatalogService` method signatures have been inspected.
- `TenantServiceProtocol` in `whatsapp_master_console_facade.py` has been reviewed as the house style reference.

## Tasks

1. Mirror the existing protocol style used by `TenantServiceProtocol`.
   - Prefer `Protocol` plus `@runtime_checkable`.
   - Keep async method signatures explicit.
2. Create `backend/app/services/tenant_console_protocols.py`.
   - Add `ClientServiceProtocol` with: `list_clients`, `get_client`, `create_client`, `update_client`, `deactivate_client`, `activate_client`, `delete_client`.
   - Add `CatalogServiceProtocol` with: `list_services`, `get_service`, `update_service`, `list_plans`, `get_plan`, `update_plan`.
3. Match current concrete service signatures closely enough that `ClientService` and `CatalogService` satisfy the protocols without adapter glue.
   - Use `AsyncSession` + `UUID` parameters.
   - Reference current schema/model payloads where practical.
4. Keep `ProfileService` concrete for now.
   - Do not add a third protocol unless execution finds a concrete testing need.
5. Account for the current schema gaps surfaced during planning.
   - If Phase 04 adds `Client.email` or catalog `description` support, update protocol imports/signatures in the same change set so contracts do not drift.
6. Validate the new protocol module.
   - At minimum, ensure imports are valid and the tenant console files type-import it cleanly.
   - Note in execution records that the repo currently lacks a configured `mypy` dependency.

## Acceptance Criteria

- User-visible or system-observable result:
  - None directly; this is an internal correctness/maintainability phase.
- Required changed files:
  - `backend/app/services/tenant_console_protocols.py`
- Required unchanged behavior:
  - Concrete `ClientService` and `CatalogService` behavior remains unchanged.
  - No endpoint behavior changes are introduced by this phase alone.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_tenant_console_service.py -q` (after Phase 06 lands)
  - `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -q` (sanity import check after protocol wiring)
- Expected results:
  - Tenant console modules import the protocol file cleanly.
  - No circular-import breakage.
- Evidence to record in `SUMMARY.md`:
  - Import/test command summary.
  - Chosen protocol file path and final symbol names.

## Idempotence and Recovery

- Safe to re-run:
  - Import and pytest checks are safe to rerun.
- Recovery if interrupted:
  - Keep protocol definitions isolated in one file so executor can back out cleanly before wiring them broadly.
- Rollback notes:
  - Remove the protocol file and revert imports if tenant-console work is abandoned.

## Exit Criteria

- [ ] `ClientServiceProtocol` exists with the planned async methods.
- [ ] `CatalogServiceProtocol` exists with the planned async methods.
- [ ] Protocol definitions follow the established service-protocol style.
- [ ] New tenant-console files can import the protocol module cleanly.
- [ ] Any Phase 04 payload-shape changes are reflected in protocol signatures.
