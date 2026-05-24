# Database Guidelines

> SQLAlchemy async + Alembic conventions used in Trackpal.

## Overview

- ORM: SQLAlchemy 2.x async (`AsyncSession`).
- Migrations: Alembic (`uv run alembic upgrade head`).
- PostgreSQL in prod, SQLite in tests.
- Repository layer is preferred home for query logic.

## Query Patterns

- Use `select()`, `update()`, joins, `scalar()/scalars()` with `AsyncSession`.
- Group reusable queries in `app/repositories/*`.
- Services orchestrate transactions and business validation.
- Resolve locale before mutating operations when endpoint may translate errors.

Examples:
- `backend/app/repositories/users_repository.py`
- `backend/app/repositories/tenants_repository.py`
- `backend/app/repositories/catalog_repository.py`

## Transactions

- Commit in service layer after successful mutation.
- On exception: rollback, re-raise mapped error.
- Avoid hidden commits inside lower helpers unless explicit contract.

## Migrations

- Create with Alembic revision (autogen/manual).
- Apply locally before tests:
  - `uv run alembic upgrade head`
- Keep model/schema/repository changes synchronized in same change set.

## Naming Conventions

- Tables/columns: snake_case.
- FK/index/constraints follow Alembic defaults or explicit clear names.
- Repository functions named by intent: `get_*`, `list_*`, `create_*`, `update_*`, `delete_*`, `resolve_*`.

## Common Mistakes

- Direct SQL in endpoint handlers.
- Mixing query code and HTTP status logic.
- Post-rollback locale reads in i18n flows.
- Keeping stale `crud`-style access after repository migration.

## Scenario: Clients username canonical storage migration

### 1. Scope / Trigger
- Trigger: DB schema change + cross-layer contract change for client login identifier.

### 2. Signatures
- Migration: `clients.local_username` -> `clients.username`.
- Canonical format: `<tenant_prefix>_<client_username_local>`.
- Sync rule: `clients.username` must match `users.username` for client owner user.

### 3. Contracts
- DB contract:
  - `clients.username` non-null canonical value.
  - tenant-scoped case-insensitive uniqueness index moved to `username` field.
- Service contract:
  - create/update operations compute canonical username from tenant prefix + local part input.
  - tenant prefix changes must resync both client and user usernames.
- API contract:
  - responses expose `username` (canonical), not `local_username`.

### 4. Validation & Error Matrix
- Duplicate canonical username in tenant scope -> validation error (409/400 mapped by endpoint policy).
- Legacy row mismatch (`clients.username != users.username`) -> migration backfill aligns from `users.username`.
- Invalid local part input -> service validation error before persistence.

### 5. Good/Base/Bad Cases
- Good: tenant `eq3wn`, local `rafael` -> store `eq3wn_rafael` in both tables.
- Base: unchanged username update path keeps canonical value stable.
- Bad: storing only `rafael` in `clients.username`.

### 6. Tests Required
- Migration test assertions:
  - old column removed/new exists.
  - migrated rows contain canonical prefixed values.
- Service tests:
  - create client stores canonical username in `clients` and `users`.
  - update local part recomputes canonical both sides.
  - tenant prefix change resyncs all tenant clients.
- Endpoint tests:
  - payload/response use `username` contract.

### 7. Wrong vs Correct
#### Wrong
```python
client.local_username = local_username
```
#### Correct
```python
client.username = build_client_username(tenant.prefix, local_username)
user.username = client.username
```