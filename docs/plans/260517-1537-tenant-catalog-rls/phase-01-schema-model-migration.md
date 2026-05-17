# Phase 01: Schema and Model Migration

## Objective

Introduce the canonical tenant/catalog schema: `tenants`, `services`, and `plans`; migrate existing `tenant_profiles` data into `tenants`; update ORM model exports so later phases can move business logic away from `TenantProfile`.

## Scope

- Files/modules this phase may touch:
  - `backend/app/models/tenant.py` (new)
  - `backend/app/models/service.py` (new)
  - `backend/app/models/plan.py` (new)
  - `backend/app/models/user.py`
  - `backend/app/models/__init__.py`
  - `backend/app/models/tenant_profile.py` (remove only when all references are updated in later phases; otherwise leave temporarily)
  - `backend/alembic/versions/*.py` (new migration)
  - `backend/tests/conftest.py` only if model metadata fixtures break
- Files/modules this phase must not touch:
  - Frontend files
  - WhatsApp flow logic beyond compile/import fixes
  - Catalog API endpoints (later phase)

## Preconditions

- Current tests pass before changes, or existing failures are documented.
- Existing schema has `users`, `master_profiles`, `tenant_profiles`, and `refresh_sessions`.
- Existing tenant data follows `tenant_profiles.id = users.id`.

## Tasks

1. Context: inspect current model and migration patterns.
   - Read `backend/app/models/base.py`, `tenant_profile.py`, `user.py`, `__init__.py`.
   - Read latest migration under `backend/alembic/versions/`.
2. Implement: create `Tenant` ORM model.
   - Table name: `tenants`.
   - Fields: `id`, `owner_user_id`, `name`, `email`, `whatsapp_phone`, `evolution_instance_name`, `is_active`, timestamps.
   - Relationships: owner `User`; `services`; optionally backref on `User` as `owned_tenant`.
3. Implement: create `Service` ORM model.
   - Table name: `services`.
   - Fields: `id`, `tenant_id`, `name`, timestamps.
   - Relationships: `tenant`, `plans`.
   - Use cascade delete from tenant to services.
   - Add explicit `UniqueConstraint("tenant_id", "id")` in `__table_args__`; this is mandatory for the composite FK from `plans(tenant_id, service_id)` to `services(tenant_id, id)`.
4. Implement: create `Plan` ORM model.
   - Table name: `plans`.
   - Fields: `id`, `tenant_id`, `service_id`, `name`, timestamps.
   - Relationships: `tenant`, `service`.
   - Enforce cascade delete through service relationship/DB FK.
5. Implement: update `backend/app/models/__init__.py` exports.
6. Implement: update `User` relationships.
   - Keep existing `role` values.
   - Add relationship to owned tenant.
   - Do not remove `tenant_profile` relationship until all code references are migrated.
7. Implement: create Alembic migration.
   - Create `tenants` table.
   - Copy existing `tenant_profiles` rows into `tenants`:
     - `owner_user_id = tenant_profiles.id`
     - `name = tenant_profiles.full_name`
     - `email = tenant_profiles.email`
     - `whatsapp_phone = tenant_profiles.phone`
     - `evolution_instance_name = tenant_profiles.evolution_instance_name`
     - `is_active = tenant_profiles.is_active`
     - preserve timestamps when feasible.
   - Add uniqueness constraints/indexes:
     - `tenants.owner_user_id` unique
     - `tenants.whatsapp_phone` unique nullable
     - `tenants.evolution_instance_name` unique nullable
   - Create `services` table with tenant FK.
   - Add unique case-insensitive service name per tenant.
   - Add explicit `UNIQUE (tenant_id, id)` on `services` to support composite FK from `plans`. Do not omit this even though `id` is already primary key.
   - Create `plans` table with tenant FK and composite FK to `services(tenant_id, id)`.
   - Add unique case-insensitive plan name per tenant + service.
   - Add composite FK exactly from `plans(tenant_id, service_id)` to `services(tenant_id, id)`.
   - Consider leaving `tenant_profiles` in place for one transitional migration if many code paths still reference it; final removal can occur in Phase 6. If dropping now, update all code in same execution before tests.
8. Verify: run targeted model/import checks.
9. Confirm: record migration name and constraints in `SUMMARY.md` progress notes.

## Acceptance Criteria

- User-visible or system-observable result:
  - Database schema has canonical `tenants`, `services`, and `plans` tables.
  - Existing tenant rows can be migrated without losing tenant login linkage.
- Required changed files:
  - New model files for tenant/service/plan.
  - Updated model exports and relationships.
  - New Alembic migration.
- Required unchanged behavior:
  - Existing auth and tenant CRUD may still fail until Phase 2, but app imports should remain coherent after all phases in one execution.
  - Master/user role names remain unchanged.

## Verification

- Commands:
  - `cd backend && uv run python -c "from app.models import Tenant, Service, Plan; print(Tenant.__tablename__, Service.__tablename__, Plan.__tablename__)"`
  - `cd backend && uv run alembic upgrade head`
  - `cd backend && uv run pytest tests/conftest.py -q` (or skip if pytest collects no tests from conftest)
- Expected results:
  - Model import command prints `tenants services plans`.
  - Alembic upgrades without errors on dev DB.
  - No import errors from test collection.
- Evidence to record in `SUMMARY.md`:
  - Migration revision ID.
  - Output summary from model import and Alembic upgrade.

## Idempotence and Recovery

- Safe to re-run:
  - Model file writes are deterministic.
  - Tests recreate SQLite metadata.
- Recovery if interrupted:
  - If migration creation is interrupted, delete partial migration and regenerate manually.
  - If Alembic upgrade partially applies on dev DB, inspect `alembic_version` and use backup/reset according to environment safety.
- Rollback notes:
  - Data migration from `tenant_profiles` to `tenants` is recoverable only if old table remains or database backup exists.
  - Do not drop `tenant_profiles` in production without backup.

## Exit Criteria

- [ ] New ORM models exist and import.
- [ ] Alembic migration creates `tenants`, `services`, and `plans`.
- [ ] Existing tenant data migration path is explicit.
- [ ] Constraints cover owner uniqueness, phone/instance uniqueness, case-insensitive names, and plan/service tenant integrity.
- [ ] `services` has explicit `UNIQUE (tenant_id, id)` in model and migration.
- [ ] `plans` has composite FK to `services(tenant_id, id)` in model and migration.
- [ ] Phase progress noted in `SUMMARY.md`.
