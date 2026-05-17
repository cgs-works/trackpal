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

Relationships: `master_profile` (1:1), `owned_tenant` (1:1 canonical tenant account), `refresh_sessions` (1:N)

### `MasterProfile` — `master_profiles` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, FK → users.id CASCADE |
| name | VARCHAR(200) | Full name of master |
| phone | VARCHAR(50) | Unique, nullable, canonical digits-only |
| created_at/updated_at | TIMESTAMPTZ | From TimestampMixin |

### `Tenant` — `tenants` table

Canonical tenant business account. Tenant login remains owned by a `users` row through `owner_user_id`; tenant IDs no longer need to equal user IDs.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, canonical tenant id |
| owner_user_id | UUID | Unique FK → users.id CASCADE |
| name | VARCHAR(200) | Display name |
| email | VARCHAR(255) | Nullable |
| whatsapp_phone | VARCHAR(50) | Unique, nullable, canonical digits-only |
| evolution_instance_name | VARCHAR(200) | Unique, nullable |
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

### `Service` — `services` table

Tenant-owned catalog service.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | FK → tenants.id CASCADE |
| name | VARCHAR(200) | Required; case-insensitive unique per tenant |
| created_at/updated_at | TIMESTAMPTZ | From TimestampMixin |

Constraints: `UNIQUE (tenant_id, id)` for composite plan FK; unique index on `(tenant_id, lower(name))`.

### `Plan` — `plans` table

Service-owned catalog plan.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | FK → tenants.id CASCADE |
| service_id | UUID | Part of composite FK → services(tenant_id, id) CASCADE |
| name | VARCHAR(200) | Required; case-insensitive unique per tenant + service |
| created_at/updated_at | TIMESTAMPTZ | From TimestampMixin |

Constraints: composite FK `(tenant_id, service_id)` prevents cross-tenant service/plan links; unique index on `(tenant_id, service_id, lower(name))`.

## RLS

Postgres RLS is enabled and forced on `tenants`, `services`, and `plans`. Policies use transaction-local custom settings set by the API before tenant-scoped queries:

- `app.current_user_id`
- `app.current_role`
- `app.active_tenant_id`

Tenant users access only their active owned tenant. Master users must switch into a tenant context before tenant-scoped catalog access.

## Migrations

Alembic migrations:
1. `cd1efe74cae4` — Initial schema creating all four tables
2. `cd2efe74cae5` — Normalize phone values to canonical digits-only format, with collision detection across both profile tables
3. `cd3efe74cae6` — Add canonical tenants, catalog tables, constraints, data copy from tenant_profiles, and RLS policies
4. `cd4efe74cae7` — Adjust tenant RLS policy so Master can manage tenants before switching into catalog context
5. `cd5efe74cae8` — Drop obsolete `tenant_profiles` table after data migration to `tenants`

## Key Constraints

- Username unique across all users
- Master phone is unique in `master_profiles`; tenant WhatsApp phone is unique in `tenants.whatsapp_phone`
- `User` row is the parent for identity; canonical tenant rows cascade on owner delete
- `RefreshSession` rows cascade delete when parent user is deleted
- Inactive tenants cannot log in or be identified by phone
- Catalog queries must filter by tenant and set RLS context for Postgres/Supabase
