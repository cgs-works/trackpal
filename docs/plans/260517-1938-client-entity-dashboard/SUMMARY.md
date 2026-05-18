# Implementation Plan: Client Entity and Dashboard

> Created: 2026-05-17 19:38:28

## Purpose / Big Picture

- Add authenticated end-customer clients to Trackpal. Tenants manage client accounts; clients log in to a readonly dashboard and can change password.
- Source: [Brainstorm artifacts](../../brainstorms/260517-1930-client-entity-dashboard/SUMMARY.md)
- GitHub issue: https://github.com/neutrobox/trackpal/issues/10

## Objective

- Add `client` role using existing `users` auth plus new tenant-owned `clients` profile table.
- Add tenant `client_prefix`: random max 5 chars, generated on tenant creation, editable by master, globally unique.
- Client technical login username format: `<client_prefix>_<local_username>`.
- Oracle review incorporated: tenant deletion must remove client users, prefix edits need UX warning, local username length must prevent `users.username` overflow, and username sync must happen on both prefix and local username changes.

## Context and Orientation

- Docs loaded: `docs/SUMMARY.md`, API/database/frontend architecture docs, PDR goals/rules, brainstorm summary.
- Backend areas: models, auth/tenant/profile/catalog services, dependencies, auth/dashboard/me/tenants/catalog endpoints, API router, validation, Alembic.
- Frontend areas: router, auth store, Login/Master/Tenant dashboard views.
- Tests: auth, tenants, catalog, RLS SQL, new clients tests.
- Patterns: thin endpoints; service logic; async SQLAlchemy; Pydantic v2; JWT role + `active_tenant_id`; Vue 3 `<script setup>`; Spanish UI.

## Scope

### In scope

- Tenant `client_prefix` column, validation, generation, master create/edit UI.
- Client model/table/schemas/service/API.
- Client role auth, dashboard response, readonly profile, password change.
- Tenant dashboard client management UI.
- RLS policies and regression tests.
- Docs updates.

### Out of scope

- Client self-registration.
- Client profile self-editing.
- Client catalog management.
- WhatsApp console client management.
- Multi-tenant selector modal at login.
- New external packages/services.

## Architecture & Approach

- Add `tenants.client_prefix VARCHAR(5) NOT NULL UNIQUE`; random lowercase/digit if omitted; editable by master.
- Add `clients(id, tenant_id, owner_user_id, full_name, local_username, phone, is_active, timestamps)`.
- Constraints: `owner_user_id` unique; `(tenant_id, lower(local_username))` unique; `(tenant_id, phone)` unique.
- Validate `local_username` length so `<client_prefix>_<local_username>` never exceeds `users.username` max length 100.
- `ClientService` creates `User(role='client', username='<prefix>_<local_username>')` plus `Client` in one transaction.
- Prefix/local username changes update `users.username` transactionally and reject collisions.
- Tenant deletion explicitly deletes associated client `users` rows, because deleting tenant/client rows alone may leave orphaned auth users.
- Client login requires active client and active parent tenant; token includes `active_tenant_id`.
- `/clients` endpoints are tenant-scoped CRUD/lifecycle endpoints.
- `/dashboard` supports `client`; client dashboard is readonly profile + password change.
- RLS on `clients`: tenant owner manages tenant clients; client reads own active row; writes require owned active tenant context.

## Progress

- [x] Plan approved for execution.
- [x] Phase 1 complete.
- [x] Phase 2 complete.
- [x] Phase 3 complete.
- [x] Phase 4 complete.
- [x] Phase 5 complete.
- [x] Phase 6 complete.
- [x] Final verification complete.
- 2026-05-17 20:31:43 — Phase 1-3 backend changes landed: tenant `client_prefix`, client model/schema/service/API, auth/profile context, and client CRUD. Verified with `cd backend && uv run pytest tests/test_input_validation_policy.py tests/test_tenants.py tests/test_auth.py tests/test_profile.py tests/test_clients.py -q` → 227 passed.
- 2026-05-17 20:31:43 — Phase 4 frontend changes landed: client route/view, master tenant prefix UI, tenant client management UI. Verified with `cd frontend && npm run build` → pass.
- 2026-05-17 20:31:43 — Phase 5 backend hardening landed: clients RLS policy plus regression coverage. Verified with `cd backend && uv run pytest tests/test_auth.py tests/test_clients.py tests/test_catalog.py tests/test_rls_policy_sql.py -q` → 53 passed, 1 skipped; `cd backend && uv run pytest -q` → 673 passed, 1 skipped.
- 2026-05-17 20:31:43 — Phase 6 docs updated (`docs/architecture/*`, `docs/codebase/*`) and execution report created. Initial migration verification blocked because `alembic upgrade head` was run without explicitly loading `backend/.env`.
- 2026-05-17 20:37:33 — Final migration verification completed with explicit env loading: `cd backend && (set -a; source .env; set +a; uv run alembic upgrade head)` → migration `cd5efe74cae8 -> cd6efe74cae9` applied successfully.
- 2026-05-17 20:54:33 — Follow-up fix pass landed: internal RLS context now used for inactive-tenant client deletion and prefix sync, backend password policy enforced for client create/password change, and `/clients` endpoints restricted to tenant role. Verified with `cd backend && uv run pytest tests/test_clients.py tests/test_profile.py tests/test_input_validation_policy.py tests/test_rls_policy_sql.py -q` → 169 passed, 1 skipped; `cd backend && uv run pytest -q` → 677 passed, 1 skipped; `cd frontend && npm run build` → pass.
- 2026-05-17 20:57:11 — Reviewer-fix follow-up tightened client deletion/prefix/password/scope coverage: tenant delete now deletes client owner users under internal RLS context before parent delete; password policy enforced in client/profile backend paths; master support client management hidden/blocked in tenant dashboard; tests expanded for empty/weak passwords, tenant cleanup, prefix sync on inactive tenant, and master `/clients` denial. Verified with `cd backend && uv run pytest tests/test_clients.py tests/test_profile.py tests/test_input_validation_policy.py tests/test_rls_policy_sql.py -q` → 172 passed, 1 skipped; `cd backend && uv run pytest -q` → 680 passed, 1 skipped; `cd frontend && npm run build` → pass.

## Phases

- [x] **Phase 1 [M]: Schema, Models, and Tenant Prefix** — Add DB support for tenant prefixes and client profiles.
- [x] **Phase 2 [M]: Backend Auth and Client Context** — Make `client` role safe in tokens, dependencies, dashboard/profile behavior.
- [x] **Phase 3 [L]: Client Management API** — Add tenant-scoped CRUD/lifecycle endpoints and service logic.
- [x] **Phase 4 [M]: Frontend Dashboards** — Add master prefix UI, tenant client management UI, and client dashboard route/view.
- [x] **Phase 5 [M]: RLS and Regression Tests** — Harden SQL policies and add backend regression coverage.
- [x] **Phase 6 [S]: Docs, Cleanup, and Final Verification** — Sync docs and run final checks.

## Key Changes

- New likely files: `backend/app/models/client.py`, `backend/app/schemas/client.py`, `backend/app/services/client_service.py`, `backend/app/api/v1/endpoints/clients.py`, new Alembic revision, `backend/tests/test_clients.py`, `frontend/src/views/ClientDashboardView.vue`.
- Modified likely files: tenant/user models, tenant/auth/profile/dashboard/me services and endpoints, API router, schemas, validation, frontend router/store/login/master/tenant dashboards, docs.
- API impact: new `/clients` route; `/dashboard` supports `client`; auth can return `role='client'`.
- Schema impact: `tenants.client_prefix`; new `clients` table.

## Validation and Acceptance

- Backend: `cd backend && uv run alembic upgrade head`; targeted pytest; `cd backend && uv run pytest -q`.
- Frontend: `cd frontend && npm run build`.
- Acceptance: master creates/edits prefix; tenant manages clients; client logs in to readonly dashboard; password change works; inactive client/tenant cannot log in; cross-tenant access blocked; duplicate local username/phone per tenant returns 409.

## Idempotence and Recovery

- Tests/build safe to rerun.
- Migration must backfill unique prefixes before non-null/unique constraints.
- Prefix changes update client technical usernames in one transaction or fail cleanly.
- Prefix update collisions must be caught as `IntegrityError`, rolled back, mapped to HTTP 409, and surfaced as a clean Spanish error in Master UI.
- Tenant deletion must use FK-safe order: either delete associated client `users` rows so cascades remove `clients`, or manually delete child rows before parent rows. Do not leave orphan `client` role users.
- No production data deletion except intentional delete-inactive-client API behavior.

## Dependencies

- New packages/tools: none planned.

## Risks & Mitigations

- Prefix collision → DB uniqueness check with bounded retry; migration backfill handles collisions before constraint.
- Prefix edit breaks login → recompute client usernames transactionally and reject collisions.
- Prefix edit collision → catch DB `IntegrityError`, rollback, return 409, and display actionable Master UI error.
- Prefix edit surprises users → master UI warns that existing client login usernames will change.
- Tenant delete leaves orphaned client users → delete associated client owner users explicitly during tenant deletion.
- RLS leak → SQL policy tests plus API cross-tenant tests.
- Missing client tenant context causes 500 → mirror tenant auth hardening; map to 401/403.
- UI grows too large → keep client management section minimal.

## Surprises & Discoveries

- 2026-05-17 20:31:43 — Initial `alembic upgrade head` failed with `WinError 1225` / connection refused because environment variables from `backend/.env` were not explicitly loaded.
- 2026-05-17 20:37:33 — Explicit env loading resolved migration verification; Alembic reached Postgres and applied revision `cd6efe74cae9` successfully.
- 2026-05-17 20:31:43 — Client technical usernames need prefix start-with-letter constraint so `<client_prefix>_<local_username>` stays valid under existing `users.username` rules.
- 2026-05-17 20:45:00 — Reviewer found S1 PostgreSQL/RLS blockers not covered by SQLite tests: inactive tenant RLS hides client rows during tenant deletion and prefix sync, risking orphan `client` users and stale client login usernames.
- 2026-05-17 20:45:00 — Reviewer found S2 backend password validation gap for client create/password-change paths.
- 2026-05-17 20:45:00 — Reviewer found S3 scope drift: master support mode can manage clients although master client management is marked out of scope.
- 2026-05-17 21:03:22 — Reviewer findings resolved in follow-up: tenant-scoped internal master RLS context now handles inactive-tenant client cleanup/sync, `/clients` list enforces tenant role, client management UI is hidden in master support mode, and password validation paths are verified.

## Decision Log

- 2026-05-17 20:00:00 — GitHub issue created: https://github.com/neutrobox/trackpal/issues/10. Rationale: track complete plan execution in one issue before `/worker`.
- 2026-05-17 19:38:28 — Use `users` + `clients` with role `client`; reuses auth/session stack.
- 2026-05-17 19:38:28 — Client dashboard readonly profile plus password change; matches user scope.
- 2026-05-17 19:38:28 — Tenant controls client lifecycle; tenant owns customer relationship.
- 2026-05-17 19:38:28 — Random editable `client_prefix` max 5 chars; avoids tenant UUID exposure.
- 2026-05-17 19:38:28 — Technical username is `<client_prefix>_<local_username>`; preserves global uniqueness.
- 2026-05-17 19:45:00 — Oracle review accepted four fixes: orphan client user cleanup, prefix edit warning, local username max length, and username sync on local username edits.
- 2026-05-17 20:31:43 — Client prefix validation constrained to start with a lowercase letter. Rationale: keep generated technical usernames compatible with existing `users.username` validation and login flow.

## Outcomes & Retrospective

- Phases 1-6 implemented and initial verification completed, then reviewer findings were resolved in follow-up pass.
- Backend verification passed: targeted tests and full `cd backend && uv run pytest -q` → 680 passed, 1 skipped.
- Frontend verification passed: `cd frontend && npm run build`.
- Migration verification passed after explicitly loading `backend/.env`: `cd backend && (set -a; source .env; set +a; uv run alembic upgrade head)`.

## Reviewer Findings Pending Resolution

- [x] **S1: Tenant deletion can leave orphan client users on PostgreSQL.** Fixed by deleting inactive tenant client users through internal RLS context before deleting tenant owner user; FK-safe order preserved.
- [x] **S1: Prefix update on inactive tenant can fail to sync client login usernames.** Fixed by syncing client usernames through internal RLS context that can read inactive tenant clients.
- [x] **S2: Client password validation missing in backend schemas.** Fixed by enforcing password policy validator on `ClientCreate.password` and `PasswordChange.new_password`.
- [x] **S3: Master support client-management scope mismatch.** Fixed by restricting `/clients` endpoints to tenant role only; regression test added.

## Required Follow-up Verification

- Added/adjusted tests proving inactive-tenant delete removes client owner users on a PostgreSQL-relevant path.
- Added/adjusted tests proving prefix changes sync all affected client technical usernames on inactive tenants.
- Added tests for weak client passwords on create and password change.
- Added test proving master cannot manage `/clients` endpoints.
- Latest verification: `cd backend && uv run pytest tests/test_clients.py tests/test_auth.py tests/test_profile.py tests/test_tenants.py -q` → 121 passed; `cd backend && uv run pytest tests/test_clients.py tests/test_catalog.py tests/test_rls_policy_sql.py -q` → 31 passed, 1 skipped; `cd backend && uv run pytest -q` → 680 passed, 1 skipped; `cd frontend && npm run build` → pass.

## Open Questions

- Should tenant be able to reset client passwords after creation? Optional, not required.
- Should master support mode manage clients later? Out of scope for first release.
