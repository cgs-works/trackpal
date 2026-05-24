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