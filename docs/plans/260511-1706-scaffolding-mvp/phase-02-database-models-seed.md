# Phase 2: Database Models + Seed

**Complexity:** M
**Dependencies:** Phase 1

## Objective

Define SQLAlchemy async models, create Alembic migrations, and implement the Master seed script.

## Preconditions

- Backend project scaffolded with UV (pyproject.toml with dependencies).
- Database connection configured in `.env` (Supabase PostgreSQL URL).

## Tasks

1. **Models**: Create `backend/app/models/` with:
   - `__init__.py` — re-export all models, import Base
   - `user.py` — User model (id UUID, username unique, password_hash, role enum)
   - `master_profile.py` — MasterProfile model (id UUID FK→users, name, phone nullable)
   - `tenant_profile.py` — TenantProfile model (id UUID FK→users, full_name, email, phone, evolution_instance_name, is_active default True)
   - `refresh_session.py` — RefreshSession model (id UUID PK, user_id FK→users, refresh_token_hash, expires_at, revoked default False)
   - `base.py` — Shared Base with UUID PK mixin, created_at, updated_at

2. **Constraints**:
   - Phone: unique per table (master_profiles.phone unique, tenant_profiles.phone unique). Cross-table uniqueness validated in service layer.
   - Master unique: no database-level constraint; validated in service layer + seed idempotency.

3. **Migrations**: Configure Alembic with async support:
   - `alembic init -t async`
   - Configure `env.py` for async SQLAlchemy
   - Generate initial migration: `alembic revision --autogenerate -m "initial schema"`
   - Apply: `alembic upgrade head`

4. **Seed script**: Create `backend/scripts/seed.py`:
   - Reads: `MASTER_USERNAME`, `MASTER_PASSWORD`, `MASTER_NAME`, `MASTER_PHONE` from env
   - Checks if Master already exists (by username or role='master')
   - If not, creates User + MasterProfile in a transaction
   - Idempotent: safe to run multiple times
   - Runnable with: `uv run python -m scripts.seed`

## Verification

- Commands:
  - `alembic upgrade head` — applies migrations without errors
  - `alembic current` — shows head revision
  - `uv run python -m scripts.seed` — creates Master, second run does nothing
  - `pytest` — model tests pass (create user, profile, unique phone, cascade delete)

## Exit Criteria

- [ ] All models defined with UUID PKs, relationships, and timestamps
- [ ] Alembic migrations create all 4 tables
- [ ] Seed script creates Master idempotently from env vars
- [ ] Tests verify: model creation, cascade delete, unique phone
