# Phase 04: RLS Hardening and Isolation Validation

## Objective

Make Supabase/Postgres RLS real for tenant-scoped data by setting per-request database context and adding policies that isolate `tenants`, `services`, and `plans` for tenant users and switched Master sessions.

## Scope

- Files/modules this phase may touch:
  - `backend/app/core/database.py`
  - `backend/app/api/dependencies.py`
  - `backend/alembic/versions/*.py` (new or same migration as Phase 1 if executor chooses)
  - `backend/tests/test_catalog.py`
  - `backend/tests/test_rls_policy_sql.py` or equivalent (new)
  - `docs/architecture/database-schema.md` if docs updated during Phase 6 instead, defer there
- Files/modules this phase must not touch:
  - Frontend files
  - Supabase Auth migration

## Preconditions

- Phase 2 provides resolved current user and active tenant context.
- Phase 3 catalog queries are tenant-scoped at application level.
- Alembic migration framework works.

## Tasks

1. Context: inspect database session lifecycle.
   - `backend/app/core/database.py` currently yields bare `AsyncSession`.
   - `backend/app/api/dependencies.py` decodes JWT and loads user.
2. Design: decide exact request context setter and transaction boundary.
   - `set_config('...', true)` is transaction-local. It must run inside the same real PostgreSQL transaction that performs tenant-scoped queries.
   - Do not set context in one dependency transaction and then run endpoint SQL in a separate later transaction.
   - If service code commits before ORM refresh/readback, reapply the same RLS context immediately before the post-commit SELECT/refresh in the new transaction.
   - Implementation note: `backend/app/core/database.py` centralizes this in `restore_rls_context(session)`. Any service method that commits and then calls `refresh()` or performs another tenant-scoped `SELECT` must call this helper first so Postgres receives transaction-local `app.*` settings in the new real transaction.
   - Recommended safe designs:
     - use a single request transaction context that sets RLS context after `BEGIN` and before tenant-scoped SQL; or
     - attach a SQLAlchemy transaction-begin hook/helper that reapplies context after every real `BEGIN` for the request session.
   - Use transaction-local `is_local = true` behavior so context does not leak across pooled connections.
   - Use only dotted custom GUC names. Required names: `app.current_user_id`, `app.current_role`, `app.active_tenant_id`. Do not use undotted names such as `tenant_id` or `current_user_id`.
   - Ensure tenant-scoped dependencies call this before catalog queries and verify it remains active for those queries.
   - API-key and auth pre-JWT flows that query `tenants` must set internal RLS context before the query. Use `set_internal_rls_context(session)`, which sets role `master`, a fixed system `user_id`, and empty `active_tenant_id`; this allows tenant-management reads while catalog RLS still requires an explicit active tenant.
   - `tenants` tenant-role `USING` must allow the owner to read its tenant row even when inactive. App code needs to see inactive rows to return 401; `services` and `plans` policies retain `t.is_active` so inactive tenants cannot access catalog data.
3. Implement: DB context helper.
   - Add helper such as `set_rls_context(db, user_id, role, active_tenant_id)` plus request/transaction wiring that guarantees same-transaction execution.
   - Helper must set exactly `app.current_user_id`, `app.current_role`, and `app.active_tenant_id`.
   - Skip or no-op safely for non-PostgreSQL dialects by checking `db.bind.dialect.name` / session bind dialect before executing `set_config`.
   - Fail closed for Postgres if tenant-scoped operation lacks `active_tenant_id`.
4. Implement: RLS migration SQL.
   - Enable RLS on `tenants`, `services`, `plans`.
   - Consider `FORCE ROW LEVEL SECURITY` if app DB role owns tables or Supabase setup would bypass policies.
   - Add policies using `current_setting(..., true)` and `NULLIF` casts.
   - Policies must read exactly `current_setting('app.current_user_id', true)`, `current_setting('app.current_role', true)`, and `current_setting('app.active_tenant_id', true)`.
   - Suggested policy concept for `services`:
     - master: `current_role = 'master'` and `tenant_id = active_tenant_id`;
     - tenant: owning tenant has `owner_user_id = current_user_id` and `is_active`.
   - `plans` mirrors `services` using `plans.tenant_id`.
   - `tenants` policy allows:
     - master switched context sees target tenant;
     - tenant owner sees own tenant.
   - Add role-aware `WITH CHECK` for INSERT/UPDATE on `services` and `plans`:
     - master writes require `tenant_id = app.active_tenant_id`;
     - tenant writes require an active owned tenant row via `owner_user_id = app.current_user_id`.
5. Implement: grants if relevant.
   - Ensure application DB role has table privileges needed for API operations.
   - Revoke overly broad public/anonymous access when applicable in Supabase.
   - Do not use service-role bypass for tenant-facing API operations.
6. Implement: tests/checks.
   - SQLite unit tests: assert tenant-scoped dependency calls context helper or no-op path and does not execute PostgreSQL-only `set_config`.
   - SQL text tests: inspect migration file contains `ENABLE ROW LEVEL SECURITY`, policies, and `WITH CHECK`.
   - App-level isolation tests from Phase 3 remain the primary automated cross-tenant check.
   - Add a focused test or documented Postgres manual check proving RLS context exists during the same transaction as a tenant-scoped query.
   - Optional Postgres integration test if environment supplies DATABASE_URL/Postgres.
7. Verify: run targeted tests and Alembic upgrade.
8. Confirm: record RLS implementation notes and any Supabase-specific manual check in `SUMMARY.md`.

## Acceptance Criteria

- User-visible or system-observable result:
  - Tenant-scoped catalog operations carry DB context and are guarded by RLS on Postgres/Supabase.
- Required changed files:
  - DB context helper/dependency.
  - Alembic migration SQL for RLS policies.
  - RLS validation tests/checks.
- Required unchanged behavior:
  - SQLite test suite remains runnable without Postgres RLS support.
  - Custom JWT auth remains; no Supabase Auth dependency introduced.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_catalog.py -v`
  - `cd backend && uv run pytest tests/test_rls_policy_sql.py -v`
  - `cd backend && uv run alembic upgrade head`
- Optional Postgres/Supabase manual commands:
  - Connect with application DB role.
  - Set context values with `select set_config(...)`.
  - Attempt tenant A read/write of tenant B service/plan and confirm denial/empty result.
- Expected results:
  - Migration contains/enables RLS policies.
  - App-level isolation tests pass.
  - Postgres manual check confirms RLS isolation when environment available.
- Evidence to record in `SUMMARY.md`:
  - Policy names.
  - Test output summary.
  - Whether `FORCE ROW LEVEL SECURITY` was used and why.

## Idempotence and Recovery

- Safe to re-run:
  - RLS context helper sets transaction-local variables each request.
  - Policy creation in Alembic should use deterministic names.
- Recovery if interrupted:
  - If policy SQL fails in migration, inspect exact DB error and adjust SQL before rerunning on disposable dev DB.
- Rollback notes:
  - Dropping policies should be part of Alembic downgrade if downgrade is supported.
  - Disabling RLS is security-sensitive; do not do it as recovery on production without explicit approval.

## Exit Criteria

- [ ] Tenant-scoped backend operations set DB RLS context.
- [ ] RLS context is set in the same PostgreSQL transaction as tenant-scoped queries.
- [ ] RLS context uses dotted Postgres custom GUC names under `app.*` only.
- [ ] Non-PostgreSQL test dialects do not execute `set_config`.
- [ ] RLS policies exist for `tenants`, `services`, and `plans`.
- [ ] `WITH CHECK` policies prevent cross-tenant writes.
- [ ] Tests/checks validate policy SQL and app-level isolation.
- [ ] Phase progress noted in `SUMMARY.md`.
