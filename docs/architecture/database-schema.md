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
| role | VARCHAR(10) | `"master"`, `"tenant"`, or `"client"` |
| created_at | TIMESTAMPTZ | Server default now() |
| updated_at | TIMESTAMPTZ | Server default now(), onupdate now() |

Relationships: `master_profile` (1:1), `owned_tenant` (1:1 canonical tenant account), `refresh_sessions` (1:N)

### `MasterProfile` — `master_profiles` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, FK → users.id CASCADE |
| name | VARCHAR(200) | Full name of master |
| phone | VARCHAR(50) | Unique, nullable, canonical digits-only |
| whatsapp_lid | VARCHAR(100) | Unique, nullable, `@lid` fallback identity |
| created_at/updated_at | TIMESTAMPTZ | From TimestampMixin |

### `Tenant` — `tenants` table

Canonical tenant business account. Tenant login remains owned by a `users` row through `owner_user_id`; tenant IDs no longer need to equal user IDs.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, canonical tenant id |
| owner_user_id | UUID | Unique FK → users.id CASCADE |
| client_prefix | VARCHAR(5) | Unique, not null, lowercase technical prefix for client logins |
| name | VARCHAR(200) | Display name |
| email | VARCHAR(255) | Nullable |
| whatsapp_phone | VARCHAR(50) | Unique, nullable, canonical digits-only |
| whatsapp_lid | VARCHAR(100) | Unique, nullable, `@lid` fallback identity |
| evolution_instance_name | VARCHAR(200) | Unique, nullable |
| evolution_instance_token | VARCHAR(500) | Nullable, encrypted via app-layer Fernet |
| plan | VARCHAR(20) | Package source of truth. Allowed: `starter`, `pro`. Existing tenants are backfilled to `pro`; new tenants must choose explicitly. |
| is_active | BOOLEAN | Default true |
| created_at/updated_at | TIMESTAMPTZ | From TimestampMixin |

### `Client` — `clients` table

Tenant-owned end-customer profile linked to a `users` login row.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | FK → tenants.id CASCADE |
| owner_user_id | UUID | Unique FK → users.id CASCADE |
| full_name | VARCHAR(200) | Required |
| username | VARCHAR(100) | Canonical client login username (`<tenant_prefix>_<local_username>`), tenant-scoped case-insensitive unique |
| phone | VARCHAR(50) | Nullable, canonical digits-only, unique per tenant |
| whatsapp_lid | VARCHAR(100) | Nullable, indexed, `@lid` fallback identity |
| is_active | BOOLEAN | Default true |
| created_at/updated_at | TIMESTAMPTZ | From TimestampMixin |

Client canonical login username is stored in both `clients.username` and `users.username` as `<client_prefix>_<local_username>`.

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


### `Subscription` -- `subscriptions`

Tenant-scoped streaming account subscription for a client.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | FK -> tenants.id CASCADE |
| client_id | UUID | FK -> clients.id CASCADE |
| service_id | UUID | FK -> services.id CASCADE |
| plan_id | UUID | FK -> plans.id CASCADE |
| streaming_email | VARCHAR(255) | Plain text, required |
| streaming_password_encrypted | VARCHAR(500) | Fernet-encrypted, nullable |
| profile_name | VARCHAR(100) | Nullable |
| profile_pin_encrypted | VARCHAR(500) | Fernet-encrypted, nullable, requires profile_name |
| duration_type | VARCHAR(50) | 1_month, 3_months, 6_months, 9_months, 1_year, custom |
| starts_at | TIMESTAMPTZ | Subscription start |
| expires_at | TIMESTAMPTZ | Computed from duration or custom expires_at |
| cancelled_at | TIMESTAMPTZ | Nullable, set on cancel |
| status | VARCHAR(50) | active, expired, cancelled |

Relationships: events, reminder_logs (1:N, delete-orphan).

### `SubscriptionEvent` -- `subscription_events`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | FK -> tenants.id CASCADE |
| subscription_id | UUID | FK -> subscriptions.id CASCADE |
| event_type | VARCHAR(100) | created, updated, renewed, cancelled, reactivated, expired, auto_cancelled, auto_deleted |
| notes | TEXT | Nullable |
| event_metadata | JSON | Nullable |

### `SubscriptionReminderLog` -- `subscription_reminder_logs`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | FK -> tenants.id CASCADE |
| subscription_id | UUID | FK -> subscriptions.id CASCADE |
| recipient_type | VARCHAR(20) | tenant or client |
| recipient_phone | VARCHAR(50) | Nullable |
| days_before_expiry | INT | Days before expiry when reminder sent |
| sent_for_date | DATE | The day this reminder covers |
| status | VARCHAR(20) | pending, sent, failed |
| attempt_count | INT | Default 0, max 3 before permanent failure |
| last_error | TEXT | Nullable |
| sent_at | TIMESTAMPTZ | Set on mark-sent |

Unique index: (subscription_id, recipient_type, days_before_expiry, sent_for_date).

### `SubscriptionReminderSettings` -- `subscription_reminder_settings`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | Unique FK -> tenants.id CASCADE |
| warning_days | JSON | Default [7, 3, 1] |
| reminder_time | VARCHAR(5) | Default 09:00 (HH:MM) |
| recipient_mode | VARCHAR(20) | tenant_only, client_only, tenant_client, tenant_and_client |
| reminders_enabled | BOOLEAN | Default false; master toggle to opt in/out of automated reminders |
| custom_message_tenant | VARCHAR(2000) | Nullable, custom reminder message for tenant |
| custom_message_client | VARCHAR(2000) | Nullable, custom reminder message for client |

Note: Timezone is no longer stored here. It is managed centrally in `TenantSettings.timezone`.

### `TenantSettings` — `tenant_settings` table

Single-row-per-tenant settings for locale and timezone. The `tenant_id` column is the primary key and foreign key to `tenants.id`.

| Column | Type | Notes |
|--------|------|-------|
| tenant_id | UUID | PK, FK → tenants.id CASCADE |
| locale | VARCHAR(10) | Default `en` (server default `en`); one of `"en"`, `"es"` |
| timezone | VARCHAR(100) | IANA timezone identifier, default `UTC` (server default `UTC`) |
| created_at | TIMESTAMPTZ | Server default now() |
| updated_at | TIMESTAMPTZ | Server default now(), onupdate now() |

Managed via `GET/PUT /api/v1/tenant-settings`. Locale and timezone are exposed as read-only projections on `GET /api/v1/me`.

RLS policies restrict access to the owning tenant and master role.

### `TenantMailbox` -- `tenant_mailboxes`

Tenant-scoped technical mailbox used for centralized code ingestion.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | Unique FK -> tenants.id CASCADE |
| mailbox_email | VARCHAR(255) | Required |
| provider | VARCHAR(50) | `google`, `microsoft`, `imap_custom` |
| auth_method | VARCHAR(50) | `oauth`, `imap_app_password` |
| status | VARCHAR(50) | `disconnected`, `connected`, `error`, `revoked` |
| oauth_access_token_encrypted | VARCHAR(500) | Nullable, encrypted |
| oauth_refresh_token_encrypted | VARCHAR(500) | Nullable, encrypted |
| oauth_token_expires_at | TIMESTAMPTZ | Nullable |
| imap_host / imap_port / imap_ssl | mixed | IMAP fallback config |
| imap_password_encrypted | VARCHAR(500) | Nullable, encrypted |
| last_connection_test_at | TIMESTAMPTZ | Nullable |
| last_connection_error | TEXT | Nullable, safe error string |

### `MailLookupJob` -- `mail_lookup_jobs`

Asynchronous mailbox lookup jobs created by n8n.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | FK -> tenants.id CASCADE |
| mailbox_id | UUID | FK -> tenant_mailboxes.id CASCADE |
| service_key | VARCHAR(64) | Streaming service key |
| target_email | VARCHAR(255) | Required content filter |
| status | VARCHAR(50) | `pending`, `processing`, `completed`, `failed`, `timeout` |
| result_type | VARCHAR(50) | Nullable: `code`, `url`, `not_found`, `duplicate_suppressed` |
| result_value_encrypted | VARCHAR(500) | Nullable; kept null in v1 (ephemeral response) |
| error_code / error_detail_safe | VARCHAR/TEXT | Safe failure payload for polling |
| expires_at | TIMESTAMPTZ | TTL boundary |

### `MailCodeDeliveryLog` -- `mail_code_delivery_log`

Dedupe tracking per tenant mailbox/service.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | FK -> tenants.id CASCADE |
| mailbox_id | UUID | FK -> tenant_mailboxes.id CASCADE |
| service_key | VARCHAR(64) | Service key |
| message_id | VARCHAR(500) | Nullable mail Message-ID |
| fingerprint | VARCHAR(128) | Required fallback dedupe hash |
| delivered_at | TIMESTAMPTZ | Delivery timestamp |

Unique constraints/indexes:
- Partial unique index when `message_id IS NOT NULL`: (`tenant_id`, `mailbox_id`, `service_key`, `message_id`, `fingerprint`)
- Partial unique index when `message_id IS NULL`: (`tenant_id`, `mailbox_id`, `service_key`, `fingerprint`)

### `BlockedClient` — `blocked_clients` table

Tenant-scoped block for unregistered WhatsApp identities that should not receive console replies. A row represents an active block; unblocking deletes the row.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, auto-generated |
| tenant_id | UUID | FK → tenants.id CASCADE, not null |
| phone | VARCHAR(50) | Nullable, canonical digits-only |
| whatsapp_lid | VARCHAR(100) | Nullable, `@lid` identity |
| created_at | TIMESTAMPTZ | From TimestampMixin |
| updated_at | TIMESTAMPTZ | From TimestampMixin |

Constraints: at least one identity field required (phone or whatsapp_lid) enforced at the repository layer. Indexes: `(tenant_id, phone)` and `(tenant_id, whatsapp_lid)`.

### `CodeServiceGlobalStatus` -- `code_service_global_status`

Global governance table for code-extraction services.

| Column | Type | Notes |
|--------|------|-------|
| service_key | VARCHAR(64) | PK, canonical service key |
| is_active | BOOLEAN | Global enable/disable toggle |
| created_at | TIMESTAMPTZ | Server default now() |
| updated_at | TIMESTAMPTZ | Server default now(), onupdate now() |

### `TenantCodeServiceSelection` -- `tenant_code_service_selections`

Per-tenant code-service selection list (separate from tenant commercial catalog).

| Column | Type | Notes |
|--------|------|-------|
| tenant_id | UUID | FK -> tenants.id CASCADE |
| service_key | VARCHAR(64) | FK -> code_service_global_status.service_key CASCADE |
| created_at | TIMESTAMPTZ | Server default now() |

Primary key: (`tenant_id`, `service_key`).

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
6. `cd6efe74cae9` — Add tenant `client_prefix`, create `clients`, and enable client RLS policies
7. `cd7efe74caa0` — Add `subscriptions`, `subscription_events`, `subscription_reminder_logs`, and `subscription_reminder_settings` tables with RLS policies
8. `cd8efe74caa1` — Add `locale` column to `tenants` for per-tenant language preference (en/es)
9. `cd9efe74caa2` — Rename `clients.local_username` to `clients.username`, rename related tenant+lower index, and backfill canonical values from `users.username`
10. `cdaefe74caa3` — Add `evolution_instance_token` column to tenants for encrypted instance token storage
11. `cdaefe74caa4` — Add `whatsapp_lid` columns + indexes to `master_profiles`, `tenants`, and `clients` for LID fallback identity resolution
12. `cdbfefe74caa5` — Add `tenant_mailboxes`, `mail_lookup_jobs`, and `mail_code_delivery_log` for tenant mailbox ingestion
13. `cdbfefe74caa6` — Add `mail_lookup_jobs.target_email` and replace dedupe uniqueness with partial indexes for nullable `message_id`
14. `cdbfefe74caa7` — Enable/force RLS on core auth and mailbox tables (`users`, `refresh_sessions`, `master_profiles`, `mail_lookup_jobs`, `mail_code_delivery_log`, `alembic_version`)
15. `cdc0fe74caa8` — Add `code_service_global_status` and `tenant_code_service_selections` with RLS policies and seeded default service keys
16. `ce10fe74caa9` — Add `reminders_enabled` column to `subscription_reminder_settings`
17. `ce10fe74caa10` — Add `client_messaging_blocks` table with tenant-scoped indexes
18. `cf10fe74caa0` — Add `custom_message_tenant` and `custom_message_client` columns to `subscription_reminder_settings`
19. `ce10fe74caa11` — Rename `client_messaging_blocks` to `blocked_clients`, update indexes and constraints
20. `07fa809c3ab3` — Merge branch heads (`ce10fe74caa11` + `cf10fe74caa0`)
21. `d011fe74cab0` — Create `tenant_settings` table, backfill locale/timezone from `tenants` and `subscription_reminder_settings`, drop `tenants.locale` and `subscription_reminder_settings.timezone`, enable RLS
22. `e011fe74cab1` — Add `plan` column to `tenants` with default `pro`, backfill existing tenants
23. `e013fe74cab3` — Delete inactive `blocked_clients` rows and drop `blocked_clients.is_active`; row existence now represents an active block

## Key Constraints

- Username unique across all users; client canonical usernames use tenant prefix + local username and are stored in both `users` and `clients`
- Master phone is unique in `master_profiles`; tenant WhatsApp phone is unique in `tenants.whatsapp_phone`
- `whatsapp_lid` is unique in `master_profiles` and `tenants`; indexed (non-unique) in `clients` for tenant-scoped resolution
- Tenant `client_prefix` is unique and required for client login generation
- `User` row is the parent for identity; canonical tenant rows cascade on owner delete
- `RefreshSession` rows cascade delete when parent user is deleted
- Inactive tenants cannot log in or be identified by phone
- Catalog queries must filter by tenant and set RLS context for Postgres/Supabase
