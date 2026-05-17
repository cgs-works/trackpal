# Phase 06: Regression, Documentation, and Cleanup

## Objective

Finish the tenant catalog/RLS change by removing obsolete `TenantProfile` assumptions, updating documentation, running broad verification, and recording final outcomes in the living plan.

## Scope

- Files/modules this phase may touch:
  - `backend/app/models/tenant_profile.py` if final removal is safe
  - Any remaining backend references found by search
  - `docs/SUMMARY.md`
  - `docs/architecture/database-schema.md`
  - `docs/architecture/api-layer.md`
  - `docs/codebase/backend-structure.md`
  - `docs/code-standard/backend-conventions.md`
  - `docs/architecture/frontend-architecture.md`
  - `docs/codebase/frontend-structure.md`
  - `AGENTS.md` if commands/architecture notes are stale
  - Test files touched by prior phases
- Files/modules this phase must not touch:
  - New features outside catalog/RLS scope.
  - Customer/subscription implementation.

## Preconditions

- Phases 1-5 are complete.
- Backend and frontend targeted tests/build pass or failures are documented.
- RLS design and switch endpoint path are final.

## Tasks

1. Context: search obsolete references.
   - `rg "TenantProfile|tenant_profile|tenant_profiles" backend frontend docs AGENTS.md`.
   - `rg "full_name" backend/app frontend/src docs` and classify whether field is compatibility alias or stale tenant-name reference.
2. Implement: cleanup obsolete production references.
   - Remove `TenantProfile` model/export only if no production code needs it and migration dropped the table.
   - If retained for historical migration compatibility, document why and avoid active use.
   - Remove stale imports and comments.
3. Implement: update docs.
   - `docs/architecture/database-schema.md`: add `tenants`, `services`, `plans`, RLS notes, and migration notes.
   - `docs/architecture/api-layer.md`: add switch tenant and catalog endpoints.
   - `docs/codebase/backend-structure.md`: add new model/schema/service/endpoint files.
   - `docs/architecture/frontend-architecture.md` and/or `docs/codebase/frontend-structure.md`: add catalog UI and Master switch behavior.
   - `docs/code-standard/backend-conventions.md`: add tenant-scoped query/RLS context convention.
   - `docs/SUMMARY.md`: update file descriptions only if docs changed.
   - `AGENTS.md`: update short architecture notes only if they contradict implementation.
4. Implement: update or add tests for migration compatibility.
   - Ensure tests cover tenant id differs from owner user id.
   - Ensure no active code path assumes `tenant.id == user.id` unless intentionally true in a specific fixture.
5. Verify: run broad backend tests.
6. Verify: run frontend build.
7. Confirm: inspect git diff for production/doc/test changes and remove accidental artifacts.
8. Update plan outcome sections.
   - Fill `SUMMARY.md` Progress checkboxes.
   - Record surprises/discoveries, decisions, and final verification outputs.

## Acceptance Criteria

- User-visible or system-observable result:
  - Codebase consistently treats `Tenant` as canonical tenant entity.
  - Documentation matches implementation.
  - Full verification is run and evidence recorded.
- Required changed files:
  - Docs and any cleanup files identified by search.
- Required unchanged behavior:
  - No implementation of clients/subscriptions/price/WhatsApp tenant catalog self-service.
  - No secret values committed.

## Verification

- Commands:
  - `cd backend && uv run pytest -v`
  - `cd frontend && npm run build`
  - `rg "TenantProfile|tenant_profile|tenant_profiles" backend/app frontend/src docs AGENTS.md`
  - `git diff --stat`
- Expected results:
  - Backend tests pass.
  - Frontend build passes.
  - Any remaining `TenantProfile` references are limited to migrations/history or documented compatibility.
  - Diff contains only intended implementation/docs/test changes.
- Evidence to record in `SUMMARY.md`:
  - Test/build command outputs.
  - Search result summary.
  - Final changed-file summary.

## Idempotence and Recovery

- Safe to re-run:
  - Documentation updates can be reapplied if based on current files.
  - Test/build commands are safe.
- Recovery if interrupted:
  - Re-run searches to find stale references before final verification.
  - Revert accidental docs or generated outputs not intended for commit.
- Rollback notes:
  - If full test suite reveals broad WhatsApp regressions, isolate changes to adapter/service layer and restore console-facing interface.

## Exit Criteria

- [ ] Stale active `TenantProfile` references removed or documented.
- [ ] Docs reflect new tenant/catalog/RLS architecture.
- [ ] Full backend tests pass or failures are documented with blockers.
- [ ] Frontend build passes.
- [ ] Final outcomes recorded in plan `SUMMARY.md`.
