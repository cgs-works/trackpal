# Task 16 Report: Deployment Guides, Architecture Documentation, and Final Verification

## Implementation

- Added the independently deployable `worker/` release artifacts:
  - Python 3.12 slim, uv-managed, non-root `worker/Dockerfile`.
  - Render Free Web Service Blueprint with `rootDir: worker`, manual executor ID/secret, and capacity `1`.
  - `worker/.env.example`, `worker/README.md`, and `worker/CONTEXT.md`.
- Added deployment runbooks:
  - Render Free setup, one-time credentials, cold start, 750-hour workspace budget, manual challenge, activation, rotation, and rollback.
  - Docker/VPS commands, firewall rules, Caddy/domain and `sslip.io`, direct-IP certificate caveat, explicit `http_encrypted` plus Master step-up and `ALLOW HTTP`, rotation, upgrades, and rollback.
- Updated architecture, codebase, context-map, and PDR documentation to describe:
  - The `worker/` Lookup Executor boundary.
  - PostgreSQL durability and reconciliation after Redis loss.
  - Redis leases, capacity, replay nonces, cooldowns, and encrypted ephemeral result cache.
  - Master registry, signed encrypted callback route, no local fallback, and hosting-password controls.
- Updated stale codebase references that still described the removed backend lookup worker/extractor.
- Updated a stale backend dashboard test fixture so the required Ruff verification is clean; no production behavior was changed for that test.
- Applied Ruff formatting to pre-existing files required by the mandated repository-wide format check.

## Tests and verification

All mandated verification commands completed with exit code `0`:

- Backend: `1800 passed, 2 skipped`; Ruff check passed; Ruff format check passed.
- Worker: `145 passed`; Ruff check passed; Ruff format check passed.
- Frontend: `408 passed`; ESLint passed; production build passed.
- `git diff --check`: passed.

The frontend build emitted Vite's existing chunk-size warning. Backend pytest emitted existing warnings for duplicate OpenAPI operation IDs, incorrectly marked async tests, and unawaited `AsyncMock` paths; these did not cause failures and are unrelated to this task.

Secret/dead-reference checks were run. Remaining lookup-related hits are historical Superpowers specs/plans, plus the unrelated export worker's generic `_process_job`/`export_worker_loop` names. Secret hits are declarations, test placeholders, or explicit safe handling paths; no literal deployment credentials or secret logging statements were found.

Docker CLI was installed, but the Docker Desktop Linux daemon was unavailable (`dockerDesktopLinuxEngine` pipe missing), so `docker build` could not be executed locally. Docker build and external Render/VPS deployment, DNS, certificate, cold-start, firewall, and Master challenge checks remain manual release steps and are not claimed as locally verified.

## Acceptance criteria evidence

1. Master executor lifecycle and multiple-enrollment behavior: existing backend/frontend registry implementation, tests, and updated docs.
2. Independent `worker/` deployment: Dockerfile, Render Blueprint, README, and worker context; no backend import/deployment.
3. No FastAPI lookup pipeline: existing removal implementation, tests, dead-reference check, and architecture docs.
4. Redis coordination plus PostgreSQL recovery: coordinator tests and updated mailbox, Redis, database, and backend context docs.
5. No fallback: coordinator tests and explicit runbook/architecture statements.
6. Render and Docker/VPS same protocol: both runbooks and shared worker configuration.
7. HTTPS and explicit encrypted HTTP exception: both runbooks plus frontend/backend controls and tests.
8. Secret-safe boundaries: worker context/README, existing protocol tests, and secret scan.
9. Hosting password controls: existing registry/frontend tests and updated context/API docs.
10. Callback idempotency: existing callback tests and callback documentation.
11. Capacity enforcement: existing backend/worker tests and deployment capacity documentation.
12. Obsolete code removal: source/reference scans and updated codebase documentation.
13. Backend, worker, frontend, contract, style, and build verification: final matrix above.

## Files changed

- `worker/Dockerfile`
- `worker/render.yaml`
- `worker/.env.example`
- `worker/README.md`
- `worker/CONTEXT.md`
- `docs/how-to/deploy-lookup-executor-render.md`
- `docs/how-to/deploy-lookup-executor-vps.md`
- `CONTEXT-MAP.md`
- `docs/SUMMARY.md`
- `docs/architecture/{system-overview,mailbox-ingestion,api-layer,database-schema,redis-ha,frontend-architecture}.md`
- `docs/codebase/{backend-structure,frontend-structure}.md`
- `docs/project-pdr/business-rules.md`
- `backend/CONTEXT.md`
- `frontend/CONTEXT.md`
- Required Ruff cleanup in backend tests/catalog/help files and worker protocol test.

## Commit

- `fb85afc docs(mail): document external lookup executors`

## Self-review and concerns

The deployment documentation consistently distinguishes the Lookup Executor
runtime from its hosting provider and explicitly labels external deployment
checks as manual. The only unresolved verification limitation is the unavailable
local Docker daemon; the Dockerfile itself was reviewed against the requested
Python 3.12, uv, non-root, port 8000, and uvicorn requirements.

## Review-finding fix report

### Implemented

- Updated `docs/how-to/deploy-lookup-executor-vps.md` with an explicit
  `-p 0.0.0.0:8000:8000` Docker command for direct public-IP
  `http_encrypted` deployments and the matching `sudo ufw allow 8000/tcp`
  rule. The guide now explains why the loopback binding cannot be made public
  by a firewall rule and keeps port `8000` closed for the Caddy deployment.
- Updated `docs/architecture/system-overview.md` so the diagram shows the
  Backend bidirectionally connected to the Lookup Executor; the frontend no
  longer appears connected directly to the worker.
- Updated `docs/how-to/deploy-lookup-executor-render.md` and `worker/README.md`
  to require retaining the current active secret during a code rollback. The
  old secret may only be restored after explicitly confirming that TrackPal
  still accepts it. The VPS rollback wording was aligned with the same rule.

### Verification

- `git diff --check`: passed.
- Targeted content consistency checks confirmed the public Docker binding and
  UFW rule are present, the architecture diagram uses Backend ⇄ Lookup
  Executor, and no standalone instruction remains to restore a previously
  verified secret.
- No automated test suite was rerun because these are documentation-only
  changes; the full verification matrix remains recorded above from the
  original Task 16 implementation.

### Files changed for this fix

- `docs/how-to/deploy-lookup-executor-vps.md`
- `docs/how-to/deploy-lookup-executor-render.md`
- `docs/architecture/system-overview.md`
- `worker/README.md`

### Commit

- `fix(docs): clarify lookup executor deployment rollback` (final short SHA is
  reported in the implementer handoff)

### Concerns

- No new concerns. External Docker, Render, firewall, DNS, certificate, and
  Master challenge verification remains a manual release responsibility as
  documented above.

## Re-review round 2 verification

Re-ran the required verification commands after the documentation changes:

```text
$ cd backend && uv run pytest tests/test_executor_i18n_catalog.py tests/test_lookup_executor_contract.py -q
..                                                                       [100%]
2 passed in 2.99s

$ cd worker && uv run pytest -q
........................................................................ [ 49%]
........................................................................ [ 99%]
.                                                                        [100%]
145 passed in 3.64s

$ cd frontend && npm test -- --reporter=dot 2>&1 | tail -5
 Test Files  65 passed (65)
      Tests  408 passed (408)
   Start at  17:34:13
   Duration  17.97s (transform 4.43s, setup 7.88s, import 31.81s, tests 59.12s, environment 76.49s)

$ git diff --check
(no output; exit code 0)
```

All required verification commands completed successfully with exit code `0`.
