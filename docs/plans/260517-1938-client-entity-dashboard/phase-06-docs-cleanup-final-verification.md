# Phase 06: Docs, Cleanup, and Final Verification

## Objective

- Update documentation, inspect diff, and run final verification across backend and frontend.

## Scope

- Files/modules this phase may touch: `docs/SUMMARY.md`, architecture docs, codebase docs, PDR docs, plan `SUMMARY.md` progress/outcomes sections.
- Files/modules this phase must not touch: production code except small fixes required by final verification.

## Preconditions

- Phases 1-5 completed.
- Targeted backend and frontend checks pass.

## Tasks

1. Update docs for client role, client table, tenant prefix, `/clients` API, and `/client/dashboard`.
2. Inspect diff with `git status --short` and `git diff --stat`.
3. Search for accidental debug logs, hardcoded secrets, and temp artifacts.
4. Run final backend verification: Alembic upgrade and full pytest.
5. Run final frontend verification: Vite build.
6. Update plan `SUMMARY.md` progress, discoveries, decisions, and outcomes.
7. Report exact verification evidence.

## Acceptance Criteria

- Docs match implemented behavior.
- No unrelated docs rewrites.
- Backend tests and frontend build pass.
- Diff contains only planned files.

## Verification

- Commands:
  - `cd backend && uv run alembic upgrade head`
  - `cd backend && uv run pytest -q`
  - `cd frontend && npm run build`
  - `git status --short`
  - `git diff --stat`
- Expected results:
  - Alembic succeeds, backend tests pass, frontend build succeeds.
- Evidence to record in `SUMMARY.md`:
  - Command result summaries and deviations.

## Idempotence and Recovery

- Safe to re-run: all verification commands.
- Recovery if interrupted: rerun final verification after any fix.
- Rollback notes: docs can be reverted independently if code phases need rollback.

## Exit Criteria

- [ ] Docs updated.
- [ ] Full backend tests pass.
- [ ] Frontend build passes.
- [ ] Plan `SUMMARY.md` outcomes completed.
- [ ] Final report includes verification evidence and follow-ups.
