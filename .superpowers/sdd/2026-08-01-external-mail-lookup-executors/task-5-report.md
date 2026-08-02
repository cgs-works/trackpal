# Task 5 Implementation Report

## Implemented

- Added the `LookupExecutor` SQLAlchemy model with lifecycle/health metadata, encrypted protocol and hosting credentials, rotation fields, capacity, timing, and safe error fields.
- Added safe Pydantic executor schemas. Ordinary responses expose `has_hosting_password` and never expose encrypted credential values.
- Added executor repository CRUD, dispatchable filtering, encrypted credential persistence, health/lifecycle updates, secret rotation helpers, and deletion.
- Added Alembic revision `e023fe74cac3` with:
  - `lookup_executors` table and lifecycle/health indexes;
  - nullable `mail_lookup_jobs.executor_id` foreign key with `ON DELETE SET NULL`;
  - `execution_attempts` and `last_dispatch_error_safe`;
  - removal of `result_value_encrypted`;
  - forced Master-only RLS policy;
  - reversible downgrade restoring the removed result column.
- Updated `MailLookupJob` relationships and executor metadata.
- Added row-lock support to `mailbox_lookup_repository.get_job()` and `processing -> pending` recovery that clears executor assignment and processing timestamps.
- Updated persistence, migration, RLS, and worker tests for the new persistence contract.
- Updated database schema and mailbox-ingestion documentation.

## Tests and Results

- TDD RED verified: initial focused collection failed because `LookupExecutor` and the migration were missing.
- Focused task suite: `86 passed, 1 skipped`.
  - `tests/test_lookup_executor_persistence.py`
  - `tests/test_lookup_executor_migration.py`
  - `tests/test_rls_policy_sql.py`
  - `tests/test_mailbox_persistence.py`
  - `tests/test_mailbox_lookup_worker.py`
- Ruff check: passed for all affected Python files.
- Ruff format check: passed for all affected Python files.
- Full backend suite: `1802 passed, 2 skipped, 1 failed`.
  - The single failure is the pre-existing unrelated `tests/test_profile.py::test_client_dashboard_subscription_includes_service_icon`, caused by an `AsyncMock` currency query returning a coroutine to `CurrencyMeta`; it does not touch the Task 5 code.

## Files Changed

- `backend/app/models/lookup_executor.py`
- `backend/app/models/mail_lookup_job.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/lookup_executors.py`
- `backend/app/repositories/lookup_executors_repository.py`
- `backend/app/repositories/mailbox_lookup_repository.py`
- `backend/alembic/versions/e023fe74cac3_add_lookup_executors.py`
- `backend/tests/test_lookup_executor_persistence.py`
- `backend/tests/test_lookup_executor_migration.py`
- `backend/tests/test_mailbox_lookup_worker.py`
- `backend/tests/test_mailbox_persistence.py`
- `backend/tests/test_rls_policy_sql.py`
- `docs/architecture/database-schema.md`
- `docs/architecture/mailbox-ingestion.md`

## Self-review Findings

- The migration SQL was rendered through PostgreSQL offline `MigrationContext` tests, including upgrade and downgrade paths.
- Encrypted fields are encrypted before repository persistence; response serialization contains no encrypted field names.
- RLS is both enabled and forced, with the required exact Master-only `USING` and `WITH CHECK` expressions.
- The working tree is clean after commit.

## Concerns

- PostgreSQL RLS runtime behavior remains covered by the repository's existing skipped manual gate because the normal test database is SQLite.
- The full suite has one unrelated baseline failure described above.

## Commit

`8b6a6ff feat(backend): persist lookup executor registry`

## Task 5 Review Fix Report

### Fixes implemented

- Added a correlated SQL subquery counting jobs whose status is `pending` or `processing` to `get`, `list_all`, and `list_dispatchable` in `backend/app/repositories/lookup_executors_repository.py`. The computed value is attached as `active_jobs`, so `LookupExecutorResponse` exposes the real count instead of its zero fallback.
- Changed `LookupExecutor.hosting_account_password_encrypted` and its migration column from `VARCHAR(500)` to unbounded SQLAlchemy/Alembic `Text`, allowing Fernet ciphertext generated from the schema's 500-character password limit.

### Tests added and verification

- Added persistence coverage for a 500-character hosting password and for active, processing, and terminal job counts.
- Added migration SQL coverage asserting the hosting password ciphertext column is `TEXT`.
- TDD RED was observed: the new tests initially failed for the `VARCHAR(500)` type, missing `active_jobs`, and old migration SQL.
- Focused persistence and migration tests: `10 passed`.
- Required review suite (`test_lookup_executor_persistence.py`, `test_lookup_executor_migration.py`, `test_rls_policy_sql.py`, `test_mailbox_persistence.py`): `55 passed, 1 skipped`.
- Ruff check and format check for affected files: passed.
- Full backend suite: `1804 passed, 2 skipped, 1 failed`; the failure is the unrelated existing `tests/test_profile.py::test_client_dashboard_subscription_includes_service_icon` AsyncMock/currency validation failure.

### Files changed for this fix

- `backend/app/models/lookup_executor.py`
- `backend/app/repositories/lookup_executors_repository.py`
- `backend/alembic/versions/e023fe74cac3_add_lookup_executors.py`
- `backend/tests/test_lookup_executor_persistence.py`
- `backend/tests/test_lookup_executor_migration.py`

### Self-review and concerns

- The active-job count is computed in one correlated query per repository operation, avoiding an N+1 query pattern and excluding terminal jobs.
- No encrypted values are included in the response; only the computed count and password-presence flag are exposed.
- The full-suite failure is unrelated to these changes and was present in `tests/test_profile.py` during verification.

### Commit

`cb21ae1 fix(backend): count active lookup executor jobs`
