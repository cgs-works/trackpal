# Phase 6: Documentation, ADR Alignment, and Full Verification

**Complexity:** M  
**Dependencies:** Phase 5

## Objective

Update project documentation and ADRs to reflect Redis active-passive HA, canonical phone storage without `+`, session lifecycle changes, and deployment configuration; then run full verification.

## Preconditions

- Implementation phases 1–5 are complete.
- All focused tests from prior phases are green.
- No scope beyond the PRD has been added.

## Tasks

1. Update `docs/adr/0004-sesion-whatsapp-redis.md` to record the new accepted decisions: active-passive Redis, no double-write, failover reset behavior, 15-minute TTL, explicit delete, and canonical digits-only phone keys.
2. Update `docs/adr/0003-integracion-n8n-y-evolution-api.md` only where necessary to remove or correct stale phone/session statements, keeping n8n as transport-only for console state.
3. If project convention prefers a new ADR for HA instead of editing ADR-0004, add the next sequential ADR under `docs/adr/` and update `docs/adr/CANDIDATES.md` if needed.
4. Update `docs/architecture/n8n-workflow.md` to state n8n sends canonical phone-compatible input and relays contingency replies; do not add new n8n behavior.
5. Update `docs/codebase/backend.md` with the new phone normalizer, Redis connection manager, failover policy, and session lifecycle modules.
6. Update `CONTEXT-MAP.md` file mappings for any new files such as `backend/app/core/phone.py`, failover policy module, Redis manager tests, and phone normalizer tests.
7. Update `docs/deployment.md` with environment variable examples for primary URL, backup URL (`redis://` or `rediss://`), pool size, timeouts, breaker threshold/window, and `WHATSAPP_SESSION_TTL_MINUTES=15`.
8. Update `README.md` only if it currently documents old Redis/session/phone configuration.
9. Review `render.yaml` for required environment variable placeholders; add only the minimal Redis HA config placeholders required by project deployment conventions.
10. Run formatting/linting commands if the project has them configured; if not, skip and note that pytest is the verification command.
11. Run all focused Redis/WhatsApp/phone tests.
12. Run the full backend test suite.
13. Run Alembic upgrade on the test/dev database configuration.
14. Review git diff to confirm no frontend or non-PRD feature scope was changed.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_phone_normalizer.py -v`
  - `cd backend && uv run pytest tests/test_redis_connection_manager.py tests/test_redis_failover_policy.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_session_service.py tests/test_whatsapp_endpoint.py -v`
  - `cd backend && uv run pytest tests/test_auth.py tests/test_tenants.py tests/test_profile.py -v`
  - `cd backend && uv run alembic upgrade head`
  - `cd backend && uv run pytest -v`
  - `git diff -- docs/adr docs/architecture docs/codebase docs/deployment.md CONTEXT-MAP.md README.md render.yaml backend/app backend/tests backend/alembic`
- Expected results:
  - Documentation accurately describes implemented Redis HA and phone normalization behavior.
  - ADRs no longer conflict with the PRD: TTL is 15 minutes, phone keys are digits-only, Redis is active-passive, and backup-missing-session reset is intentional.
  - Full backend test suite passes.
  - Alembic migration applies.
  - Diff contains no frontend work or out-of-scope feature additions.

## Exit Criteria

- Required docs/ADR updates are complete and consistent.
- Deployment docs include TLS-ready backup Redis configuration.
- All focused and full backend tests pass.
- Migration path for canonical phone storage is documented and executable.
- The implementation is ready for review without hidden context or scope creep.
