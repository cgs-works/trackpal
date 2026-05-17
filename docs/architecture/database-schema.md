# Database Schema

PostgreSQL database managed via SQLAlchemy ORM (async) with Alembic migrations.

## Models (in `app/models/`)

All models extend `Base` (SQLAlchemy `DeclarativeBase`). `TimestampMixin` adds `created_at` and `updated_at` columns with server defaults.

### `User` — `users` table

Primary identity for all system users, with a polymorphic role design.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key, auto-generated |
| username | VARCHAR(100) | Unique, used for login |
| password_hash | VARCHAR(255) | bcrypt hashed |
| role | VARCHAR(10) | `"master"` or `"tenant"` |
| created_at | TIMESTAMPTZ | Server default now() |
| updated_at | TIMESTAMPTZ | Server default now(), onupdate now() |

Relationships: `master_profile` (1:1), `tenant_profile` (1:1), `refresh_sessions` (1:N)

### `MasterProfile` — `master_profiles` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, FK → users.id CASCADE |
| name | VARCHAR(200) | Full name of master |
| phone | VARCHAR(50) | Unique, nullable, canonical digits-only |
| created_at/updated_at | TIMESTAMPTZ | From TimestampMixin |

### `TenantProfile` — `tenant_profiles` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, FK → users.id CASCADE |
| full_name | VARCHAR(200) | Display name |
| email | VARCHAR(255) | Nullable |
| phone | VARCHAR(50) | Unique, nullable, canonical digits-only |
| evolution_instance_name | VARCHAR(200) | Name of Evolution API instance |
| is_active | BOOLEAN | Default true |
| created_at/updated_at | TIMESTAMPTZ | From TimestampMixin |

### `RefreshSession` — `refresh_sessions` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, auto-generated |
| user_id | UUID | FK → users.id CASCADE |
| refresh_token_hash | VARCHAR(255) | SHA-256 hash of refresh token |
| expires_at | TIMESTAMPTZ | Token expiration |
| revoked | BOOLEAN | Default false |
| created_at/updated_at | TIMESTAMPTZ | From TimestampMixin |

## Migrations

Two Alembic migrations exist:
1. `cd1efe74cae4` — Initial schema creating all four tables
2. `cd2efe74cae5` — Normalize phone values to canonical digits-only format, with collision detection across both profile tables

## Key Constraints

- Username unique across all users
- Phone unique across each profile table (separate unique constraints)
- No cross-table unique constraint on phone (master and tenant can share phone numbers)
- `User` row is the parent; profile rows cascade on delete
- `RefreshSession` rows cascade delete when parent user is deleted
- Inactive tenants cannot log in or be identified by phone
