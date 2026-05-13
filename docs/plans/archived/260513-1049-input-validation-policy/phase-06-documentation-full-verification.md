# Phase 6: Documentation and Full Verification

**Complexity:** S  
**Dependencies:** Phase 5

## Objective

Update minimal project documentation/context to reflect the new central validation policy and complete final verification without adding scope.

## Preconditions

- Phase 5 full backend test suite passes locally or has only documented environment-specific failures.
- No code changes unrelated to validation policy are pending in the worker branch.

## Tasks

1. Update `CONTEXT.md` only if implementation details differ from the current Input Validation Policy bullets already present.
2. Update `CONTEXT-MAP.md` to add `backend/app/core/input_validation.py` under the relevant API/service/domain mapping.
3. Update `docs/codebase/backend.md` if it lists core modules or validation patterns and would otherwise be stale.
4. Add a short note to `docs/architecture/api-routes.md` only if API error status behavior changed in a way route docs should mention.
5. Do not create a new ADR unless implementation changes an accepted architectural decision; the PRD and existing ADR-0003/0004 already establish backend-owned WhatsApp and phone canonicalization constraints.
6. Run dependency verification with `cd backend && uv sync --locked` if lockfile was updated; if `--locked` fails because lock changed intentionally, run `uv sync` and confirm lock is committed.
7. Run focused validation suites one final time.
8. Run the full backend suite.
9. Inspect `git diff --stat` and ensure modified files match the plan scope.
10. Record any known limitations or environment-only failures in the implementation handoff, not in code comments unless directly useful.

## Verification

- Commands:
  - `cd backend && uv sync`
  - `cd backend && uv run pytest tests/test_input_validation_policy.py -v`
  - `cd backend && uv run pytest tests/test_auth.py tests/test_tenants.py tests/test_profile.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_create_flow.py tests/test_whatsapp_edit_flow.py tests/test_whatsapp_endpoint.py -v`
  - `cd backend && uv run pytest -v`
  - `git diff --stat`
- Expected results:
  - Documentation points to the central backend policy module.
  - All focused and full backend tests pass.
  - Diff does not include frontend/n8n business-rule rewrites or unrelated feature work.

## Exit Criteria

- Docs/context are consistent with the implementation.
- Full verification has passed or any environment-only exception is explicitly documented.
- Plan scope remains limited to centralized backend validation policy and regression coverage.
