# Phase 03: Catalog Backend API

## Objective

Add tenant-scoped CRUD APIs for services and plans, backed by service-layer logic that enforces tenant ownership, case-insensitive uniqueness, and cascade delete behavior.

## Scope

- Files/modules this phase may touch:
  - `backend/app/schemas/catalog.py` or `backend/app/schemas/service.py` + `backend/app/schemas/plan.py` (new)
  - `backend/app/services/catalog_service.py` (new)
  - `backend/app/api/v1/endpoints/catalog.py` or `services.py`/`plans.py` (new)
  - `backend/app/api/v1/router.py`
  - `backend/app/api/dependencies.py` if additional tenant-context dependency is needed
  - `backend/tests/test_catalog.py` (new)
- Files/modules this phase must not touch:
  - Frontend files
  - WhatsApp console flows
  - Customer/subscription models

## Preconditions

- Phase 2 provides a reliable tenant-scoped context dependency.
- `Service` and `Plan` ORM models exist.
- Tenant user and switched Master requests can resolve exactly one active tenant.

## Tasks

1. Context: inspect endpoint/service patterns.
   - Use `backend/app/api/v1/endpoints/tenants.py` and `backend/app/services/tenant_service.py` as patterns.
2. Implement: create Pydantic schemas.
   - `ServiceCreate`: `name`.
   - `ServiceUpdate`: optional `name`.
   - `ServiceResponse`: `id`, `tenant_id`, `name`, `created_at`, maybe `updated_at`.
   - `PlanCreate`: `name`.
   - `PlanUpdate`: optional `name`.
   - `PlanResponse`: `id`, `tenant_id`, `service_id`, `name`, timestamps.
   - Optionally `ServiceWithPlansResponse` if UI needs nested display.
3. Implement: create catalog service.
   - `list_services(db, tenant_id)`.
   - `create_service(db, tenant_id, payload)`.
   - `get_service(db, tenant_id, service_id)`.
   - `update_service(db, tenant_id, service_id, payload)`.
   - `delete_service(db, tenant_id, service_id)`.
   - `list_plans(db, tenant_id, service_id)`.
   - `create_plan(db, tenant_id, service_id, payload)`.
   - `get_plan(db, tenant_id, service_id, plan_id)`.
   - `update_plan(db, tenant_id, service_id, plan_id, payload)`.
   - `delete_plan(db, tenant_id, service_id, plan_id)`.
4. Implement: enforce validation in service layer.
   - Trim and reject blank names.
   - Enforce max length matching DB column.
   - Check case-insensitive duplicates before commit for clear 409 errors.
   - Ensure every query filters by `tenant_id`.
5. Implement: create endpoints.
   - Recommended route shape:
     - `GET /api/v1/catalog/services`
     - `POST /api/v1/catalog/services`
     - `GET /api/v1/catalog/services/{service_id}`
     - `PUT /api/v1/catalog/services/{service_id}`
     - `DELETE /api/v1/catalog/services/{service_id}`
     - `GET /api/v1/catalog/services/{service_id}/plans`
     - `POST /api/v1/catalog/services/{service_id}/plans`
     - `PUT /api/v1/catalog/services/{service_id}/plans/{plan_id}`
     - `DELETE /api/v1/catalog/services/{service_id}/plans/{plan_id}`
   - Every endpoint uses tenant-scoped dependency from Phase 2.
   - Return 404 for resources outside active tenant; never reveal cross-tenant existence.
   - Return 409 for duplicate names.
6. Implement: register router in `backend/app/api/v1/router.py`.
7. Implement: tests.
   - Tenant creates/lists/updates/deletes own service.
   - Tenant creates/lists/updates/deletes plan under own service.
   - Duplicate service name with different case returns 409.
   - Duplicate plan name with different case under same service returns 409.
   - Same plan name in different services allowed.
   - Same service/plan names across different tenants allowed.
   - Delete service cascades plans.
   - Cross-tenant access returns 404/403 according endpoint policy, preferably 404.
   - Master switched to tenant can operate catalog.
   - Master without active tenant cannot operate catalog.
8. Verify: run catalog tests and targeted auth/tenant tests.
9. Confirm: record endpoint shape in `SUMMARY.md`.

## Acceptance Criteria

- User-visible or system-observable result:
  - API clients can manage services and plans for active tenant only.
- Required changed files:
  - New schemas, service, endpoint, router registration, tests.
- Required unchanged behavior:
  - Tenant CRUD endpoints still manage tenant accounts, not catalog.
  - No customer/subscription endpoints exist yet.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_catalog.py -v`
  - `cd backend && uv run pytest tests/test_auth.py tests/test_tenants.py -v`
- Expected results:
  - All catalog CRUD tests pass.
  - Existing auth/tenant tests still pass.
- Evidence to record in `SUMMARY.md`:
  - Endpoint list and test pass summary.

## Idempotence and Recovery

- Safe to re-run:
  - CRUD tests use isolated database fixtures.
  - Duplicate-name tests should generate deterministic cases.
- Recovery if interrupted:
  - If endpoint route shape conflicts with existing routes, rename router prefix before frontend phase and update this phase notes.
- Rollback notes:
  - Removing catalog API is safe before frontend depends on it; DB schema rollback handled by Phase 1 migration.

## Exit Criteria

- [ ] Catalog schemas exist.
- [ ] Catalog service filters every query by tenant id.
- [ ] Catalog endpoints registered under `/api/v1`.
- [ ] CRUD, uniqueness, cascade, and cross-tenant tests pass.
- [ ] Phase progress noted in `SUMMARY.md`.
