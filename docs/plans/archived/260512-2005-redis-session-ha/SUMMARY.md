# Implementation Plan: Redis Session HA for WhatsApp Master Console

## Objective

- Implement Redis active-passive high availability for WhatsApp Master Console session state.
- Canonicalize all phone values as digits-only strings without `+` for Master/Tenant identification, database storage, and Redis session keys.
- Add pooled Redis lifecycle management, traffic-driven circuit-breaker failover, explicit session cleanup, degraded-state replies, and TLS-ready backup configuration.
- Link to PRD: `docs/prds/260512-2005-redis-session-ha/PRD.md`

## Scope

### In scope

- Phone canonicalization helper that removes `+`, non-digits, and WhatsApp/JID suffixes before identity lookup, persistence, and Redis keying.
- Backend model/schema/service updates so `master_profiles.phone` and `tenant_profiles.phone` store canonical digits-only phone values.
- Alembic migration/backfill strategy for existing `+` phone values and duplicate detection before enforcing normalized storage behavior.
- Redis active-passive connection manager with one primary pool and one backup pool per backend process.
- Configurable Redis primary/backup URLs, pool sizes, short timeouts, breaker threshold/window, and 15-minute session TTL.
- Backup URL support for both `redis://` and `rediss://` without architecture changes.
- Circuit breaker and traffic-based half-open recovery policy: primary under normal operation, backup only after consecutive primary failures, no double-write.
- WhatsApp session lifecycle policy: minimal session payload, TTL refresh only on valid flow progress, explicit delete on completion/cancel/terminal close.
- Endpoint/UX behavior when backup lacks active session or both Redis stores are unavailable.
- Tests for normalization, storage impact, pooling/lifecycle behavior through fakes, failover, cleanup, TTL, and degraded states.
- Documentation/ADR updates required by existing project conventions.

### Out of scope

- Redis replication between primary and backup.
- Double-writing session state to both Redis stores.
- Active-active Redis load balancing.
- Persisting WhatsApp conversational state in PostgreSQL.
- New WhatsApp business flows beyond existing Tenant CRUD console flows.
- Frontend/dashboard changes.
- Advanced observability dashboards, alerts, or metrics pipelines.
- Customer, Subscription, or Service features.

## Architecture & Approach

- Preserve backend-owned WhatsApp console logic from ADR-0004 and the existing `POST /api/v1/integrations/n8n/console` contract.
- Replace the current single Redis client lifecycle in `backend/app/core/redis_client.py` with a `RedisConnectionManager` that owns primary and backup clients/pools for the process lifetime.
- Keep Redis active-passive: every operation targets the active store selected by the failover policy; do not write through to backup.
- Encapsulate failover decisions in a small policy object that tracks consecutive primary failures, opens the breaker after the configured threshold, sends operations to backup while open, and retries primary after the configured window only when real traffic arrives.
- Treat missing backup session during failover as a safe reset: delete/avoid stale state and return a clear contingency reply asking the Master to restart from menu.
- Treat both Redis stores unavailable as a safe hard degraded state: return a relayable “console temporarily unavailable” reply and do not run a stateless flow.
- Make phone canonicalization a shared backend utility used by schemas/services/endpoints/seed/migrations so persisted phones, identity lookup, and Redis keys match.

## Phases

- [x] **Phase 1 [M]: Phone canonicalization and database normalization** — Add shared phone normalization, update schemas/services/identity/seed behavior, and add migration/backfill safeguards for canonical DB storage without `+`.
- [x] **Phase 2 [M]: Redis connection manager, pools, and lifecycle** — Introduce primary/backup Redis settings, process-lifetime pools, startup/shutdown handling, timeouts, and TLS-ready backup URL support.
- [x] **Phase 3 [L]: Circuit breaker and traffic-based active-passive failover** — Implement failover policy, route session operations through the manager, and prove primary/backup behavior with tests.
- [x] **Phase 4 [M]: Session lifecycle policy and cleanup** — Change session TTL to 15 minutes, refresh TTL only on valid progress, keep payload minimal, and explicitly delete sessions on terminal flow outcomes.
- [x] **Phase 5 [M]: Contingency endpoint behavior and UX replies** — Add deterministic replies for backup-missing-session resets and total Redis outage; ensure endpoint never degrades to stateless flow.
- [x] **Phase 6 [M]: Documentation, ADR alignment, and full verification** — Update ADR/docs/deployment examples and run the complete focused and regression test suite.

## Key Changes

- `backend/app/core/config.py` — Redis HA, pool, timeout, breaker, and 15-minute TTL settings.
- `backend/app/core/redis_client.py` — Replace/supersede single client helper with active-passive connection manager lifecycle.
- `backend/app/core/phone.py` or equivalent — Shared `PhoneNormalizer` utility.
- `backend/app/models/master_profile.py` and `backend/app/models/tenant_profile.py` — Keep phone fields as strings but document/use canonical digits-only values.
- `backend/app/schemas/tenant.py`, `backend/app/schemas/me.py`, and any profile/tenant schemas accepting phone input — Normalize phone before service persistence.
- `backend/app/services/auth_service.py`, `backend/app/crud/users.py`, `backend/app/api/v1/endpoints/integrations.py` — Normalize identity lookup and WhatsApp console phone keys.
- `backend/app/services/whatsapp_session_service.py` — Minimal session shape, HA-backed operations, TTL refresh semantics, explicit delete behavior.
- `backend/app/services/whatsapp_console_service.py` — Ensure only valid flow progress refreshes TTL and terminal flows clear sessions.
- `backend/alembic/versions/*.py` — Migration/backfill to normalize existing phone values and fail clearly on collisions.
- `backend/tests/` — Focused tests for phone normalization, migration/storage effects, Redis manager/failover, session lifecycle, and degraded endpoint states.
- `docs/adr/0004-sesion-whatsapp-redis.md` and possibly `docs/adr/0003-integracion-n8n-y-evolution-api.md` — Update decisions to reflect HA and canonical phone rules.
- `docs/deployment.md`, `docs/architecture/n8n-workflow.md`, `docs/codebase/backend.md`, `CONTEXT-MAP.md` — Update only where necessary for changed config and module map.

## Verification Strategy

Run focused tests after each phase and the full backend suite when shared services or endpoint behavior changes.

Core commands:

- `cd backend && uv run pytest -v`
- `cd backend && uv run pytest tests/test_phone_normalizer.py -v`
- `cd backend && uv run pytest tests/test_auth.py tests/test_tenants.py tests/test_profile.py -v`
- `cd backend && uv run pytest tests/test_redis_connection_manager.py -v`
- `cd backend && uv run pytest tests/test_redis_failover_policy.py -v`
- `cd backend && uv run pytest tests/test_whatsapp_session_service.py -v`
- `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -v`
- `cd backend && uv run alembic upgrade head`

## Dependencies

- Existing async Redis dependency in `backend/pyproject.toml` (`redis>=5.0.0`).
- Existing FastAPI lifespan in `backend/app/main.py` for Redis startup/shutdown.
- Existing WhatsApp Master Console service and tests.
- Existing Alembic async migration setup.
- Fake Redis/test doubles for deterministic tests; no Redis cloud dependency in automated tests.

## Risks & Mitigations

- Existing stored phones may collide after normalization (for example `+123` and `123`) → migration must detect duplicates and fail with an actionable error before data loss.
- Phone normalization could break identity lookup if not applied consistently → centralize normalization and add tests for schemas, identify endpoint, console endpoint, and Redis key generation.
- Redis failover flapping → configurable consecutive failure threshold and open window; recovery only through half-open traffic attempts.
- Backup lacks active session because there is no replication/double-write → explicit reset reply is expected behavior and covered by tests.
- Connection leaks under errors/timeouts → process-lifetime pools, no per-request clients, explicit shutdown close, and tests for lifecycle calls through fakes.
- TTL refresh on invalid/noise messages could preserve abandoned sessions → refresh only when session is created, advanced to a valid next step, or updated with valid flow data.

## Open Questions

- Exact production values for pool size and timeout should be set operationally; implementation defaults must follow PRD recommendations and be configurable.
- Exact Spanish wording may be adjusted minimally while preserving required meanings: backup session reset and total console unavailability.

## Handoff

Plan artifacts are ready under `docs/plans/260512-2005-redis-session-ha/`.
