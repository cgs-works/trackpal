# Phase 01: Schema, Models, and Tenant Prefix

## Objective

- Add database foundation for tenant client prefixes and client profiles.

## Scope

- Files/modules this phase may touch:
  - `backend/app/models/tenant.py`
  - `backend/app/models/user.py`
  - `backend/app/models/client.py`
  - `backend/app/models/__init__.py`
  - `backend/app/schemas/tenant.py`
  - `backend/app/core/input_validation.py`
  - `backend/app/services/tenant_service.py`
  - `backend/app/api/v1/endpoints/tenants.py`
  - `backend/alembic/versions/*.py`
  - `backend/tests/test_tenants.py`
  - `backend/tests/test_rls_policy_sql.py`
- Files/modules this phase must not touch:
  - Frontend views except later phases.
  - Client CRUD endpoints except stubs needed for imports.

## Preconditions

- Working tree contains this plan and brainstorm artifacts.
- Existing tests pass before implementation or failures are understood.
- Executor has read latest Alembic revision chain.

## Tasks

1. Context: inspect `backend/app/models/tenant.py`, `backend/app/models/user.py`, `backend/app/services/tenant_service.py`, `backend/app/schemas/tenant.py`, latest Alembic revision, and tenant tests.
2. Implement validation:
   - Add `validate_client_prefix(value: str) -> str` in `backend/app/core/input_validation.py`.
   - Rules: required when supplied, trim/lowercase, 1-5 chars, lowercase letters/digits only.
   - Add/confirm client local username validation with max length low enough that `<client_prefix>_<local_username>` fits `users.username` `String(100)`.
3. Implement prefix generation:
   - Add service helper in `TenantService` to generate random 5-character lowercase/digit prefix.
   - Check DB uniqueness before use and retry with bounded attempts.
4. Add model fields:
   - Add `Tenant.client_prefix` mapped column `String(5)`, unique, non-null.
   - Add `Tenant.clients` relationship.
   - Add `User.client_profile` relationship.
5. Add `backend/app/models/client.py`:
   - Define `Client` model with fields from `SUMMARY.md`.
   - Add relationships to `Tenant` and `User`.
6. Add migration:
   - Add nullable `client_prefix`.
   - Backfill every existing tenant with a unique random/deterministic prefix before applying constraints.
   - Only after successful backfill, alter `client_prefix` to non-null and add unique constraint/index.
   - Create `clients` table.
   - Add unique indexes for `(tenant_id, lower(local_username))` and `(tenant_id, phone)`.
   - Add FK and cascade behavior.
7. Update tenant schemas/responses:
   - `TenantResponse` includes `client_prefix`.
   - `TenantCreate` accepts optional `client_prefix`; if omitted, service generates.
   - `TenantUpdate` accepts optional `client_prefix`.
8. Update tenant service create/update:
   - On create, use supplied valid prefix or generated prefix.
   - On update, validate prefix uniqueness and prepare for future client username updates in Phase 3.
9. Add/adjust tests:
   - Tenant creation without prefix returns generated prefix.
   - Tenant creation/update rejects duplicate/invalid prefix.
   - Tenant response includes prefix.
   - Migration/RLS SQL test recognizes clients table and tenant prefix constraints if string-based.
10. Verify and record results in `SUMMARY.md`.

## Acceptance Criteria

- User-visible or system-observable result:
  - Master tenant API can create/update tenants with `client_prefix`.
  - Existing tenants get unique prefixes through migration.
- Required changed files:
  - New migration and `backend/app/models/client.py`.
  - Tenant model/schema/service/API/tests updated.
- Required unchanged behavior:
  - Existing master/tenant auth and tenant CRUD still pass.
  - Existing catalog behavior unchanged.

## Verification

- Commands:
  - `cd backend && uv run alembic upgrade head`
  - `cd backend && uv run pytest tests/test_tenants.py tests/test_rls_policy_sql.py -q`
- Expected results:
  - Migration succeeds.
  - Tenant and SQL policy tests pass.
- Evidence to record in `SUMMARY.md`:
  - Alembic output summary and pytest result line.

## Idempotence and Recovery

- Safe to re-run:
  - Tests and migration in fresh test DB.
- Recovery if interrupted:
  - If migration fails during prefix backfill or constraint application, fix revision and rerun before moving phases. Do not apply `NOT NULL` before all rows have valid unique prefixes.
- Rollback notes:
  - Alembic downgrade should drop `clients`, indexes, and `client_prefix` if project migration style includes downgrade.

## Exit Criteria

- [ ] `client_prefix` exists in model/schema/API.
- [ ] Client local username length validation prevents technical username overflow.
- [ ] `clients` model/table migration exists.
- [ ] Existing tenant tests updated and passing.
- [ ] No frontend work done in this phase.
