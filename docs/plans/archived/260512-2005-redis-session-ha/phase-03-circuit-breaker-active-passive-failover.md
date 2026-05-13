# Phase 3: Circuit Breaker and Traffic-Based Active-Passive Failover

**Complexity:** L  
**Dependencies:** Phase 2

## Objective

Implement active-passive failover for WhatsApp session Redis operations: use primary under normal traffic, open a breaker after consecutive primary failures, use backup while open, and retry primary only through real traffic after the open window.

## Preconditions

- Redis connection manager owns primary and backup process-lifetime pools.
- Phone keys passed to session operations are canonical digits-only.
- No double-write/replication behavior has been introduced.

## Tasks

1. Add a small `FailoverPolicy` class, preferably in `backend/app/core/redis_client.py` or `backend/app/services/redis_failover_policy.py`, with states closed/open/half-open.
2. Configure the policy from settings: consecutive failure threshold default `3`, breaker open window default between `30` and `60` seconds.
3. Implement policy behavior: closed uses primary; primary success resets failure count; primary failure increments count; threshold opens breaker.
4. Implement open behavior: operations use backup when configured; no primary background health checks are scheduled.
5. Implement traffic-based recovery: after open window elapses, the next real operation attempts primary in half-open state.
6. Implement half-open success: close breaker and return to primary.
7. Implement half-open failure: reopen breaker and continue using backup for subsequent operations.
8. Expose a manager method such as `execute(operation_name, callable)` or `with_active_client()` so session service operations run against the selected Redis client and report success/failure to the policy.
9. Ensure Redis operation exceptions/timeouts from primary are caught by the manager, recorded as failures, and retried on backup only when the policy allows/backup is configured.
10. Ensure backup operation failures are surfaced to callers as Redis unavailable; do not mask both-store failure as success.
11. Update `backend/app/services/whatsapp_session_service.py` to use the manager abstraction for `get`, `set`, and `delete` instead of holding a raw Redis client directly, while keeping tests able to inject fakes.
12. Preserve active-passive semantics: writes during failover go only to backup, and normal writes go only to primary.
13. Add `backend/tests/test_redis_failover_policy.py` for closed/open/half-open transitions, threshold behavior, open window behavior, success reset, and no flapping before threshold.
14. Extend `backend/tests/test_redis_connection_manager.py` with fake clients that fail primary operations and verify backup is used only after configured consecutive failures.
15. Extend `backend/tests/test_whatsapp_session_service.py` to prove session `get`, `save`, and `clear` use the manager/fake active store and surface both-store failures.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_redis_failover_policy.py -v`
  - `cd backend && uv run pytest tests/test_redis_connection_manager.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_session_service.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -v`
  - `cd backend && uv run pytest -v`
- Expected results:
  - Primary remains active during normal successful operations.
  - A single intermittent primary failure below threshold does not fail over permanently.
  - Breaker opens only after configured consecutive primary failures.
  - Backup is used while breaker is open.
  - Primary is retried only by real traffic after the open window.
  - Successful half-open primary operation closes the breaker.
  - No test observes double-write to primary and backup.

## Exit Criteria

- Failover policy is deterministic, configurable, and covered by behavior tests.
- Session operations route through the active Redis selected by the policy.
- Both Redis unavailable results in a clear failure signal for endpoint handling in Phase 5.
- No background health check loop or active-active behavior exists.
