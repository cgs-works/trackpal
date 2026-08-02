# Task 9 Implementation Report

## Implemented

- Added pure least-loaded executor selection with stable timestamp and UUID tie-breaking.
- Added `LookupExecutionCoordinator` with:
  - idempotent queue scheduling;
  - one active short-lived pump per coordinator;
  - per-job dispatch locks;
  - executor cooldown and capacity filtering;
  - Redis lease reservation and release;
  - encrypted mailbox-envelope construction;
  - accepted and same-lease duplicate handoff handling;
  - busy, transport, protocol, and security outcome handling;
  - degraded/unreachable health transitions and three-failure cooldown;
  - immediate security reverification quarantine;
  - durable pending-job requeueing without local execution fallback.
- Added runtime configuration and FastAPI lifespan wiring for one Redis-backed coordinator using the HTTP transport.
- Removed the permanent in-process mailbox lookup worker loop from FastAPI startup; cleanup and export background tasks remain active.
- Updated mailbox ingestion architecture documentation for external dispatch and failure behavior.
- Added focused coordinator tests covering selection, duplicate scheduling, no-capacity requeueing, handoff outcomes, accepted transitions, and transport-failure cooldowns.

## TDD Evidence

- RED observed with `ModuleNotFoundError` for the missing selector and coordinator modules.
- GREEN achieved after implementing the selector and coordinator.

## Tests and Results

- `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py tests/test_main.py -q`: **10 passed**.
- `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py tests/test_main.py tests/test_lookup_coordination_store.py tests/test_lookup_executor_api.py tests/test_lookup_executor_transport.py -q`: **71 passed**.
- `cd backend && uv run pytest`: **1885 passed, 2 skipped, 1 failed**.
  - The failure is the pre-existing unrelated `tests/test_profile.py::test_client_dashboard_subscription_includes_service_icon`, caused by an unconfigured `AsyncMock` currency query passed to `CurrencyMeta`.
- Ruff check: passed for all affected application and test files.
- Ruff format check: passed for all affected application and test files.
- `git diff --check`: passed.

## Files Changed

- `backend/app/services/lookup_execution_coordinator/selector.py`
- `backend/app/services/lookup_execution_coordinator/coordinator.py`
- `backend/app/services/lookup_execution_coordinator/runtime.py`
- `backend/app/services/lookup_execution_coordinator/__init__.py`
- `backend/app/main.py`
- `backend/tests/test_lookup_execution_coordinator.py`
- `docs/architecture/mailbox-ingestion.md`

## Self-Review Findings

- Requeued jobs stop the current pump batch, preventing a busy or failed job from being retried repeatedly in one scheduling call.
- The worker command envelope contains only fields accepted by the worker's strict Pydantic command model; no protocol-only extra field is sent.
- Accepted leases remain reserved for asynchronous callback completion, while rejected handoffs release capacity before requeueing.
- The coordinator preserves the durable PostgreSQL pending state and never falls back to local mailbox processing.
- Existing coordination-store exports were preserved while adding coordinator exports.

## Concerns

- The full backend suite retains the unrelated profile dashboard failure described above.
- The callback URL base is read from `TRACKPAL_PUBLIC_URL` and defaults to `http://localhost:8000`; production deployments must set `TRACKPAL_PUBLIC_URL` to the externally reachable backend URL before Task 11 enables live executor scheduling.

## Commit

`1c7032e feat(backend): dispatch lookup jobs externally`


## Task 9 Review Fix Report

### Implemented

- Added queue-presence checks to the Redis and in-memory coordination stores. A pump now starts a follow-on pump after completing its configured batch when queued jobs remain, while requeue-triggered stops do not spin indefinitely.
- Updated `last_selected_at` immediately after executor selection, before lease reservation and handoff, so busy, transport, security, and protocol outcomes participate in fair tie-breaking.
- Added defense-in-depth filtering for disabled and reverification-required registry entries in integrated coordinator selection.
- Added coordinator tests for UUID tie-breaking, batch continuation, selection timestamp updates on rejected outcomes, disabled/reverification/cooldown exclusion, and `DUPLICATE_SAME_LEASE`.
- Updated mailbox-ingestion architecture documentation to describe batch continuation.

### Tests and Results

- RED: `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py -q` failed with 5 expected failures for the unimplemented batch continuation, selection timestamp, and integrated exclusion behavior.
- GREEN: `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py -q`: **13 passed**.
- Related suites: `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py tests/test_lookup_coordination_store.py tests/test_lookup_queue_atomicity.py tests/test_main.py -q`: **33 passed**.
- Full backend suite: **1889 passed, 2 skipped, 1 failed, 39 warnings**. The failure is the pre-existing unrelated `tests/test_profile.py::test_client_dashboard_subscription_includes_service_icon` caused by an unconfigured `AsyncMock` currency query passed to `CurrencyMeta`.
- Ruff check and format check passed for all affected backend files. `git diff --check` passed.

### Files Changed

- `backend/app/services/lookup_execution_coordinator/coordinator.py`
- `backend/app/services/lookup_execution_coordinator/fake_store.py`
- `backend/app/services/lookup_execution_coordinator/redis_store.py`
- `backend/tests/test_lookup_execution_coordinator.py`
- `docs/architecture/mailbox-ingestion.md`

### Self-Review Findings

- Queue continuation is atomic with pump ownership under `_pump_guard`; scheduling that races with pump completion cannot strand a queued job.
- A pump that requeues due to no executor, capacity, or handoff failure intentionally stops without immediate retry, avoiding a hot loop while preserving the pending job for later scheduling.
- Existing duplicate scheduling remains limited to one active pump, and accepted leases remain reserved for callback completion.

### Concerns

- Finding 3 remains a known design limitation: `_consecutive_failures` is process-local, so failures distributed across multiple application processes do not share the three-failure cooldown threshold. Redis-backed failure counting is out of scope for this fix.
- The unrelated full-suite profile failure remains as described above.


## Task 9 Review Fix Report (Round 2)

### Implemented

- Changed the coordinator pump to inspect queued work after a dispatch returns `False`, excluding the just-requeued job from the check. It starts a follow-on pump when other jobs remain, while avoiding a hot retry loop when the sole remaining item is the failed/busy job.
- Extended the Redis and in-memory coordination stores with exclusion-aware queue-presence checks.
- Added a regression test proving a requeued dispatch cannot strand another queued job.
- Replaced random executor IDs in the integrated exclusion test with deterministic IDs (`1`, `2`, `3`, and `4`), ensuring an excluded executor would win the selector tie-break if filtering were broken.
- Updated mailbox-ingestion documentation to describe continuation after requeued dispatches and the sole-requeue behavior.

### TDD Evidence

- RED: `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py -q` produced **1 failure, 13 passed** in the new requeue-with-remaining-work regression test; the failure showed only one pump was spawned.
- GREEN: `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py -q`: **14 passed**.

### Tests and Results

- Related suites: `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py tests/test_lookup_coordination_store.py tests/test_lookup_queue_atomicity.py tests/test_main.py -q`: **34 passed**.
- Full backend suite: **1890 passed, 2 skipped, 1 failed, 39 warnings**. The failure remains the unrelated `tests/test_profile.py::test_client_dashboard_subscription_includes_service_icon`, caused by an unconfigured `AsyncMock` currency query passed to `CurrencyMeta`.
- `cd backend && uv run ruff check app/services/lookup_execution_coordinator tests/test_lookup_execution_coordinator.py`: passed.
- `cd backend && uv run ruff format --check app/services/lookup_execution_coordinator tests/test_lookup_execution_coordinator.py`: passed.
- `git diff --check`: passed.

### Files Changed

- `backend/app/services/lookup_execution_coordinator/coordinator.py`
- `backend/app/services/lookup_execution_coordinator/fake_store.py`
- `backend/app/services/lookup_execution_coordinator/redis_store.py`
- `backend/tests/test_lookup_execution_coordinator.py`
- `docs/architecture/mailbox-ingestion.md`

### Self-Review Findings

- A requeued job is excluded only for the failure-triggered continuation decision, preserving the prior no-hot-loop behavior for a sole pending job.
- Redis and fake-store queue checks use the same exclusion semantics, keeping production and test coordination behavior aligned.
- Deterministic IDs make the exclusion regression test fail reliably if lifecycle, reverification, or cooldown filtering is removed.

### Concerns

- The full backend suite still has the unrelated profile dashboard failure described above.
- The Redis exclusion-aware queue check reads the queue list to distinguish the requeued job from other work; this is appropriate for the bounded dispatch queue but is less constant-time than the normal queue-length check.


## Task 9 Review Fix Report (Round 3)

### Implemented

- Kept the pump task registered while checking for queued work under `_pump_guard`.
- Only clears `_pump_task` when no continuation is required; queued work discovered during completion starts a follow-on pump before the guard is released.
- Added a deterministic regression test that enqueues work from the completion check and verifies the pump remains active and processes the new job.

### TDD Evidence

- RED: `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py::test_pump_restarts_when_work_is_enqueued_during_completion -q` failed with `assert [False] == [True]`, proving the pre-fix completion check observed a cleared pump task.
- GREEN: The same focused test passed after moving pump-task clearing after the guarded continuation check.

### Tests and Results

- Focused coordinator and related suites: `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py tests/test_lookup_coordination_store.py tests/test_lookup_queue_atomicity.py tests/test_main.py -q`: **35 passed**.
- Full backend suite: `cd backend && uv run pytest`: **1891 passed, 2 skipped, 1 failed, 39 warnings**. The failure is the pre-existing unrelated `tests/test_profile.py::test_client_dashboard_subscription_includes_service_icon`, caused by an unconfigured `AsyncMock` currency query passed to `CurrencyMeta`.
- Ruff check and format check passed for the affected coordinator and test files.
- `git diff --check` passed.

### Files Changed

- `backend/app/services/lookup_execution_coordinator/coordinator.py`
- `backend/tests/test_lookup_execution_coordinator.py`

### Self-Review Findings

- The continuation decision and pump ownership transition now occur atomically with respect to `schedule()`, so a job enqueued during completion cannot observe a prematurely cleared pump and become stranded.
- Existing behavior for cancellation, dispatch failures, and an empty queue remains unchanged: those paths clear the pump task without spawning a continuation.
- The existing architecture documentation already describes follow-on pump behavior, so no documentation update was needed.

### Concerns

- The full backend suite retains the unrelated profile dashboard failure described above; it is outside this change.

### Commit

`bac4c9d fix(backend): close lookup pump restart race`
