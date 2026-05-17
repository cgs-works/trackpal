# Implementation Plan: Tenant Catalog with Supabase/Postgres RLS

> Created: 2026-05-17 15:37:42

## Purpose / Big Picture

Trackpal needs tenant-owned catalog management so each tenant can create services and plans isolated from every other tenant. This plan replaces the current `tenant_profiles`-as-tenant model with a real `tenants` entity owned by a login `user`, adds `services` and `plans`, and enforces tenant isolation through both application checks and Supabase/Postgres RLS.

Brainstorm artifact: [Tenant Catalog with Supabase/Postgres RLS](../../brainstorms/260517-1543-tenant-catalog-rls/SUMMARY.md).

GitHub issue: [#8 — Tenant catalog with Supabase/Postgres RLS](https://github.com/neutrobox/trackpal/issues/8).

## Objective

Build an execution-ready path to:

- migrate existing tenant accounts from `tenant_profiles` to `tenants`;
- keep tenant login via existing `users` records;
- let Master switch into a tenant support context;
- add tenant-scoped `services` and `plans` with strict constraints;
- enforce isolation with Postgres RLS designed for the current custom FastAPI JWT stack;
- expose backend APIs and frontend UI for tenant catalog management.

## Context and Orientation

- Relevant docs loaded:
  - `docs/SUMMARY.md`
  - `docs/architecture/database-schema.md`
  - `docs/architecture/api-layer.md`
  - `docs/codebase/backend-structure.md`
  - `docs/architecture/frontend-architecture.md`
  - `docs/code-standard/backend-conventions.md`
  - `docs/code-standard/frontend-conventions.md`
- Relevant files/modules:
  - `backend/app/models/tenant_profile.py` — current tenant profile table coupled 1:1 to `users.id`.
  - `backend/app/models/user.py` — current identity model with `role` = `master` or `tenant`.
  - `backend/app/core/database.py` — async SQLAlchemy session creation; no request DB context today.
  - `backend/app/core/security.py` — JWT creation currently includes `sub`, `role`, `type`, `exp` only.
  - `backend/app/api/dependencies.py` — current user loading and tenant active check use `TenantProfile.id == user.id`.
  - `backend/app/services/auth_service.py` — login/refresh tokens and phone identity use `TenantProfile`.
  - `backend/app/services/tenant_service.py` — Master tenant CRUD creates `User` + `TenantProfile` and Evolution instance.
  - `backend/app/api/v1/endpoints/tenants.py` — Master tenant CRUD API.
  - `backend/app/api/v1/endpoints/me.py` and `backend/app/services/profile_service.py` — tenant self-profile reads/writes.
  - `backend/app/api/v1/endpoints/dashboard.py` — dashboard counts currently use `TenantProfile`.
  - `backend/app/api/v1/endpoints/integrations.py` — WhatsApp Master Console adapter wraps `TenantProfile`.
  - `frontend/src/views/MasterDashboardView.vue` — Master tenant list/create/edit UI.
  - `frontend/src/views/TenantDashboardView.vue` — tenant dashboard/profile UI, no catalog yet.
  - `frontend/src/stores/auth.js` and `frontend/src/services/api.js` — token storage and Axios auth header.
  - `backend/tests/conftest.py`, `backend/tests/test_tenants.py`, `backend/tests/test_auth.py`, `backend/tests/test_profile.py`, `backend/tests/test_whatsapp_endpoint.py` — high-impact test areas.
- Existing patterns to follow:
  - FastAPI endpoints stay thin; business logic belongs in `app/services/`.
  - SQLAlchemy async models under `app/models/`; Pydantic v2 schemas under `app/schemas/`.
  - Alembic migrations under `backend/alembic/versions/`.
  - Tests use pytest-asyncio, SQLite in-memory, and mocked Evolution/Redis.
  - Frontend uses Vue 3 `<script setup>`, Pinia, Axios singleton.
- Constraints, dependencies, and compatibility notes:
  - Current auth is custom FastAPI JWT, not Supabase Auth; RLS cannot rely on `auth.uid()`.
  - SQLite test DB cannot enforce Postgres RLS. Add app-level isolation tests and migration SQL checks; run Postgres/Supabase validation separately when available.
  - No production code should be changed during plan creation. Execute only with `/worker` after approval.

## Scope

### In scope

- New `Tenant` model/table replacing `TenantProfile` as canonical tenant entity.
- Data migration from `tenant_profiles` to `tenants`.
- `tenants.owner_user_id` as the login user for the tenant account.
- Owner transfer support in backend model/service, not necessarily full UI unless needed by current tenant update flow.
- New `Service` and `Plan` models/tables.
- Case-insensitive uniqueness:
  - services: unique per tenant by name;
  - plans: unique per tenant + service by name.
- Physical deletes and service-to-plan cascade.
- Master support context via switch tenant endpoint and reissued tokens with `active_tenant_id`.
- Tenant login resolves implicit tenant from `tenants.owner_user_id`.
- Postgres/Supabase RLS structure for `tenants`, `services`, and `plans` using session-local context settings.
- Backend catalog APIs.
- Tenant dashboard catalog UI.
- Test and docs updates needed to keep repo coherent.

### Out of scope

- Customer/client entities.
- Subscriptions purchased by clients.
- Plan price, currency, billing cadence, payments, invoices.
- WhatsApp tenant self-service catalog management.
- Full migration to Supabase Auth.
- Audit log for Master support actions.
- Direct browser-to-Supabase data access.

## Architecture & Approach

- Keep `users` as identity/auth table.
- Add `tenants` as business account table:
  - `id uuid pk`
  - `owner_user_id uuid not null unique references users(id)`
  - `name varchar(200) not null`
  - `email varchar(255)`
  - `whatsapp_phone varchar(50) unique`
  - `evolution_instance_name varchar(200) unique`
  - `is_active boolean not null default true`
  - timestamps
- Add `services`:
  - `id uuid pk`
  - `tenant_id uuid not null references tenants(id) on delete cascade`
  - `name varchar(200) not null`
  - timestamps
- Add `plans`:
  - `id uuid pk`
  - `tenant_id uuid not null`
  - `service_id uuid not null`
  - `name varchar(200) not null`
  - timestamps
  - `foreign key (tenant_id, service_id) references services(tenant_id, id) on delete cascade`
- RLS context settings per request:
  - `app.current_user_id`
  - `app.current_role`
  - `app.active_tenant_id`
  - Use only dotted custom GUC names (`app.*`). PostgreSQL custom settings without a dot are invalid/unsafe for this design.
- RLS context must be set inside the same real PostgreSQL transaction that executes tenant-scoped SQL. Do not set `set_config(..., true)` in an earlier dependency transaction and then run catalog queries in a later transaction. Use a single request transaction boundary or a SQLAlchemy transaction-begin hook/context helper that guarantees settings are applied after every real `BEGIN`.
- Tenant user access:
  - allowed only when `tenants.owner_user_id = current_user.id` and tenant active.
- Master access:
  - Master must switch into a tenant context; tenant-scoped catalog operations require `active_tenant_id`.
- Master refresh behavior:
  - Refresh must preserve `active_tenant_id` when the old access token/session had one and the target tenant remains active.
  - Frontend must persist `active_tenant_id` with token state and expose a clear "Salir de tenant" action for Master support context.
- WhatsApp tenant resolution future-ready:
  - tenant resolution uses both `whatsapp_phone` and `evolution_instance_name`; both must match.

## Progress

- [x] Plan approved for execution.
- [x] Phase 1 completed - 2026-05-17 16:22:26 model import printed `tenants services plans`; Alembic upgraded through `cd4efe74cae7`; `alembic current` returned `cd4efe74cae7 (head)`.
- [!] 2026-05-17 16:12:56 blocked during Phase 1 verification: `cd backend && uv run alembic upgrade head` failed before migration execution because configured PostgreSQL database refused connection (`ConnectionRefusedError: [WinError 1225] El equipo remoto rechazó la conexión de red`).
- [!] 2026-05-17 16:18:54 blocked again during Phase 1 verification: model import passed (`tenants services plans`), but Alembic still failed connecting to Supabase pooler. Parent supplied working `DATABASE_URL` export from `backend/.env`; execution resumed.
- [x] Phase 2 completed - 2026-05-17 16:25:00 auth/profile/dashboard/tenant CRUD use canonical `Tenant`; switch endpoint implemented; targeted auth/tenant/profile/WhatsApp tests passed (`109 passed`).
- [x] Phase 3 completed - 2026-05-17 16:25:00 catalog schemas/service/endpoints registered under `/api/v1/catalog`; catalog tests passed.
- [x] Phase 4 completed - 2026-05-17 16:25:00 RLS context helper and policies added; `tests/test_rls_policy_sql.py` passed; Alembic head verified.
- [x] Phase 5 completed - 2026-05-17 16:25:00 auth store persists `active_tenant_id`; tenant catalog UI and Master support switch/exit UI added; `npm run build` passed.
- [x] Phase 6 completed - 2026-05-17 16:26:28 docs updated; stale references documented as legacy compatibility; full backend tests passed.
- [x] Final verification completed - backend `623 passed, 1 skipped`, frontend Vite build succeeded, Alembic current is `cd4efe74cae7 (head)`. Manual Supabase cross-tenant RLS check remains pending for parent/environment.

## Phases

- [x] **Phase 1 [L]: Schema and model migration** — Introduce `tenants`, `services`, and `plans`; migrate from `tenant_profiles`; add constraints and model exports.
- [x] **Phase 2 [L]: Auth, tenant context, and existing tenant flows** — Adapt auth/profile/dashboard/tenant CRUD to canonical `Tenant`; implement Master switch tenant token flow.
- [x] **Phase 3 [M]: Catalog backend API** — Add service/plan schemas, service layer, endpoints, and routing with tenant-scoped dependencies.
- [x] **Phase 4 [L]: RLS hardening and isolation validation** — Add Postgres RLS SQL, request context setting, RLS-aware tests/checks, and Supabase validation notes.
- [x] **Phase 5 [M]: Frontend catalog UI** — Extend tenant dashboard and Master support flow to manage catalog.
- [x] **Phase 6 [M]: Regression, documentation, and cleanup** — Update docs/tests, remove obsolete references, run full verification.

## Key Changes

- Likely backend files:
  - `backend/app/models/tenant.py` (new)
  - `backend/app/models/service.py` (new)
  - `backend/app/models/plan.py` (new)
  - `backend/app/models/__init__.py`
  - `backend/app/models/user.py`
  - `backend/app/models/tenant_profile.py` (remove or leave only during migration compatibility if executor proves needed)
  - `backend/alembic/versions/*.py` (new migration)
  - `backend/app/core/security.py`
  - `backend/app/core/database.py`
  - `backend/app/api/dependencies.py`
  - `backend/app/schemas/auth.py`
  - `backend/app/schemas/tenant.py`
  - `backend/app/schemas/catalog.py` or separate `service.py` / `plan.py` (new)
  - `backend/app/services/auth_service.py`
  - `backend/app/services/tenant_service.py`
  - `backend/app/services/profile_service.py`
  - `backend/app/services/catalog_service.py` (new)
  - `backend/app/api/v1/endpoints/auth.py`
  - `backend/app/api/v1/endpoints/tenants.py`
  - `backend/app/api/v1/endpoints/catalog.py` (new)
  - `backend/app/api/v1/endpoints/dashboard.py`
  - `backend/app/api/v1/endpoints/integrations.py`
  - `backend/app/api/v1/router.py`
- Likely frontend files:
  - `frontend/src/stores/auth.js`
  - `frontend/src/services/api.js`
  - `frontend/src/views/TenantDashboardView.vue`
  - `frontend/src/views/MasterDashboardView.vue`
- Likely tests:
  - `backend/tests/conftest.py`
  - `backend/tests/test_auth.py`
  - `backend/tests/test_tenants.py`
  - `backend/tests/test_profile.py`
  - `backend/tests/test_catalog.py` (new)
  - `backend/tests/test_rls_policy_sql.py` or equivalent (new)
  - WhatsApp tests using tenant adapter may need update.
- Data/API/schema impacts:
  - New canonical tenant table replaces `tenant_profiles`.
  - Tenant IDs may no longer equal owner user IDs. Existing API responses must keep stable external meaning: tenant `id` should be `tenants.id` after migration.
  - Token response may include `active_tenant_id` for tenant users and switched Master sessions.
  - New endpoint for Master tenant switch.
  - New `/api/v1/catalog` or `/api/v1/services` endpoints.

## Validation and Acceptance

- Commands:
  - `cd backend && uv run pytest -v`
  - `cd backend && uv run pytest tests/test_auth.py tests/test_tenants.py tests/test_profile.py tests/test_catalog.py -v`
  - `cd backend && uv run alembic upgrade head`
  - `cd frontend && npm run build`
- Manual/Supabase checks when a Postgres/Supabase database is available:
  - run Alembic migration against Postgres;
  - inspect RLS policies exist on `tenants`, `services`, `plans`;
  - verify tenant A cannot read/write tenant B catalog using an app role with context settings.
- Observable acceptance criteria:
  - Master can create a tenant account and existing tenant login still works.
  - Tenant dashboard uses the tenant associated with `tenants.owner_user_id`.
  - Master can switch into a tenant and operate tenant-scoped catalog.
  - Tenant can create/list/update/delete services and plans only in own tenant.
  - Service names duplicate only across tenants, never within same tenant ignoring case.
  - Plan names duplicate only across services or tenants, never within same service ignoring case.
  - Deleting a service deletes its plans.
  - Cross-tenant plan/service references are impossible.

## Idempotence and Recovery

- Safe re-run notes:
  - Tests should recreate SQLite metadata from models.
  - Alembic migration must be deterministic and use collision checks before moving data.
  - Service/plan creation tests should use unique names or clean fixtures.
- Rollback/recovery notes:
  - The migration replacing `tenant_profiles` is schema-destructive if it drops the old table. Executor should include downgrade only if feasible and document limitations.
  - Before production execution, back up database.
  - If collisions exist in `whatsapp_phone`, `evolution_instance_name`, or owner mappings, migration must fail with clear error rather than guessing.
- Irreversible operations or destructive steps:
  - Dropping `tenant_profiles` after migration.
  - Physical deletes for services/plans.

## Dependencies

- No new application packages required.
- Existing `sqlalchemy`, `alembic`, `fastapi`, `pydantic`, `pytest`, and Vue/Vite stack are sufficient.
- Postgres/Supabase features used: RLS, policies, `current_setting`, expression indexes or generated normalized columns depending implementation choice.
- `services` must define explicit `UNIQUE (tenant_id, id)` in ORM and migration so `plans(tenant_id, service_id)` can use a composite FK to `services(tenant_id, id)`.

## Risks & Mitigations

- Risk: Current code assumes `tenant_profile.id == user.id`.
  - Mitigation: replace with explicit `Tenant.owner_user_id`; add tests where tenant id differs from user id.
- Risk: RLS bypass if app connects as owner/service role.
  - Mitigation: document and test app DB role; use `FORCE ROW LEVEL SECURITY` or non-owner role for tenant-facing DB operations when applicable.
- Risk: SQLite tests do not enforce RLS.
  - Mitigation: add app-level isolation tests and SQL policy tests; run Postgres validation separately.
- Risk: RLS context lost across SQLAlchemy transactions because `set_config(..., true)` is transaction-local.
  - Mitigation: set context inside the same transaction as tenant-scoped queries, or use a SQLAlchemy transaction-begin hook/context helper; test/document this explicitly.
- Risk: using non-dotted Postgres GUC names breaks RLS context.
  - Mitigation: all settings must use `app.*` names exactly, e.g. `app.current_user_id`, `app.current_role`, `app.active_tenant_id`.
- Risk: missing `UNIQUE (tenant_id, id)` on `services` weakens or blocks composite FK from `plans`.
  - Mitigation: make `UNIQUE (tenant_id, id)` mandatory in SQLAlchemy model and Alembic migration; verify migration creates FK `plans(tenant_id, service_id) -> services(tenant_id, id)`.
- Risk: Master support context disappears after token refresh or page reload.
  - Mitigation: preserve valid `active_tenant_id` during refresh; persist it in frontend token state; add explicit "Salir de tenant" UI action.
- Risk: Token shape changes break frontend login/router.
  - Mitigation: keep `user.role` and `user.username`; add `active_tenant_id` as additive field.
- Risk: WhatsApp Master Console adapter depends on `TenantProfile` attributes.
  - Mitigation: update adapter wrapper to map `Tenant` fields to same console interface.
- Risk: Case-insensitive uniqueness differs between SQLite and Postgres.
  - Mitigation: enforce normalized comparison in service layer and add DB constraint/index for Postgres.

## Surprises & Discoveries

- 2026-05-17 16:25:00 - Alembic env requires shell `DATABASE_URL` export from `backend/.env`; parent-supplied export unblocked migration.
- 2026-05-17 16:25:00 - `tenant_profiles` table initially remained as transitional mirror. It was later removed by `cd5efe74cae8` after active code stopped using it.
- 2026-05-17 16:25:00 - Tenant ID and owner user ID now differ in tests; stale tests were updated to assert canonical `Tenant` rows.

## Decision Log

- 2026-05-17 15:37:42 — Decision: use `tenants.owner_user_id`, not `tenant_memberships`. Rationale: user clarified each tenant is a company account with one login owner/admin.
- 2026-05-17 15:37:42 — Decision: no plan price in this phase. Rationale: user corrected original requirement to name-only plans for now.
- 2026-05-17 15:37:42 — Decision: Master uses switch tenant before catalog operations. Rationale: clearer authorization context and compatible with RLS.
- 2026-05-17 15:37:42 — Decision: physical deletes with cascade from service to plans. Rationale: user selected simple deletion for catalog phase.
- 2026-05-17 15:37:42 — Decision: WhatsApp tenant routing requires both phone and Evolution instance to match. Rationale: user selected strict matching.
- 2026-05-17 15:43:24 — Decision: apply oracle review fixes before execution. Rationale: RLS transaction context, Master refresh persistence, and frontend support-context UX must be explicit for safe execution.
- 2026-05-17 15:43:24 — Issue: Created GitHub issue #8 for this implementation plan. URL: https://github.com/neutrobox/trackpal/issues/8.
- 2026-05-17 16:25:00 — Decision superseded: `tenant_profiles` was initially retained as a legacy mirror for transition, then removed by `cd5efe74cae8` after user approval. Rationale: `Tenant` is now the sole active tenant model.
- 2026-05-17 17:35:00 — Decision: drop obsolete `tenant_profiles` from DB and codebase. Rationale: user confirmed destructive cleanup after data was migrated to canonical `tenants`.
- 2026-05-17 16:25:00 — Decision: tenant support context uses `POST /api/v1/auth/switch-tenant`; passing `tenant_id: null` clears the context. Rationale: auth token context belongs in auth layer without adding a second clear endpoint.
- 2026-05-17 17:05:00 — Review fix: added Alembic revision `cd4efe74cae7` to allow Master tenant-management reads under forced RLS without active tenant context. Rationale: catalog remains tenant-scoped, while Master must list/switch tenants before catalog context exists.
- 2026-05-17 17:05:00 — Review fix: Master support dashboard now loads selected tenant details from `/tenants/{id}` and hides `/me` profile/password forms. Rationale: prevents editing the Master account while operating in tenant support mode.

## Outcomes & Retrospective

- 2026-05-17 16:26:28 - Execution completed with pending manual Supabase RLS QA.
- Implemented canonical `Tenant`, `Service`, and `Plan` models plus Alembic revisions `cd3efe74cae6` and `cd4efe74cae7` with data copy, constraints, composite FK, RLS enable/force, and corrected Master tenant-management policy.
- Updated auth/profile/dashboard/tenant CRUD and WhatsApp adapter to use canonical `Tenant`; refresh/switch token flow preserves `active_tenant_id`.
- Added `/api/v1/catalog` service/plan CRUD with tenant-scoped dependency and duplicate/cross-tenant protections.
- Added frontend catalog management and Master support context UI with persisted `active_tenant_id` and `Salir de tenant`.
- Updated docs and AGENTS notes for tenant/catalog/RLS architecture.
- Verification passed: `uv run pytest -q` (`623 passed, 1 skipped`), targeted backend suites (`92 passed, 1 skipped`), Alembic current `cd4efe74cae7 (head)`, and `npm run build`.
- Pending: manual Supabase/app-role check that RLS denies tenant A access to tenant B catalog using transaction-local `app.*` settings.

## Open Questions

- None blocking. Execution should validate whether the production Supabase app uses a non-owner DB role or needs `FORCE ROW LEVEL SECURITY` to prevent owner bypass.
