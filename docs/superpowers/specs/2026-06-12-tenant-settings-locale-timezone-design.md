# Tenant settings for locale and timezone

Date: 2026-06-12
Status: Proposed
Linear: TPL-17

## Goal

Move tenant-global preferences out of feature-specific tables and into a dedicated `tenant_settings` table.

The first two settings in that table are:

- `locale`, currently stored on `tenants.locale`;
- `timezone`, currently stored on `subscription_reminder_settings.timezone`.

After this change, `tenant_settings` is the single source of truth for tenant-global preferences. Reminder settings remain responsible only for reminder behavior, and tenant identity remains responsible only for tenant account metadata.

## Decisions captured

1. Create a new one-to-one `tenant_settings` table keyed by `tenant_id`.
2. Move `locale` from `tenants` into `tenant_settings.locale`.
3. Move `timezone` from `subscription_reminder_settings` into `tenant_settings.timezone`.
4. Do not add `timezone` directly to `tenants`.
5. Keep `subscription_reminder_settings.reminder_time` as a tenant-local time, but resolve its timezone through `tenant_settings.timezone`.
6. Use a clean API boundary: tenant-global settings are read and updated through `/api/v1/tenant-settings`.
7. Keep `/api/v1/me` focused on profile identity data. It may expose `locale` and `timezone` as read-only convenience projections, but it must not own writes for those fields.
8. Keep the backend as the source of truth for reminder scheduling, tenant-local expiry logic, and WhatsApp locale resolution.
9. Keep n8n as transport only; no n8n workflow logic change is required for this refactor.

## Current codebase findings

### Backend data model

Current `Tenant` contains tenant identity fields and `locale`. It does not contain `timezone`.

Current `SubscriptionReminderSettings` contains `timezone` alongside reminder-specific fields such as `warning_days`, `reminder_time`, `recipient_mode`, `reminders_enabled`, and custom reminder messages.

There is no existing `tenant_settings` table, model, repository, service, or endpoint.

### Backend consumers of `locale`

The codebase resolves locale from `Tenant.locale` in several paths:

- REST API error localization helpers through `tenants_repository.resolve_locale*`;
- `/api/v1/i18n/catalog` for frontend catalog selection;
- `/api/v1/me` profile response;
- `ProfileService.update_profile()` through `ProfileUpdate.locale`;
- WhatsApp tenant console facade, which resolves the locale once per message;
- WhatsApp tenant profile flow, which currently updates `Tenant.locale` directly with a SQL update.

All of these consumers must read or write `TenantSettings.locale` after the refactor.

### Backend consumers of `timezone`

The codebase resolves timezone from `SubscriptionReminderSettings.timezone` in reminder scheduling and cleanup paths:

- `SubscriptionReminderSettingsUpdate` validates `timezone`;
- `SubscriptionReminderSettingsResponse` returns `timezone`;
- `subscription_service/reminder_settings.py` creates and updates `timezone`;
- `subscription_job_service/reminder_payloads.py` uses `settings.timezone` for reminder eligibility, `days_until_expiry`, and `sent_for_date`;
- `subscription_job_service/cleanup.py` loads a tenant timezone map from reminder settings.

All of these consumers must read `TenantSettings.timezone` after the refactor.

### Frontend settings area

The current settings area uses React/TSX and Zustand. The older architecture docs still mention Vue/Pinia in places, so implementation must follow the current code, not the historical docs.

Current frontend state:

- `settings-api.ts` owns profile API types and functions;
- `reminder-api.ts` includes `timezone` in reminder settings types and update payloads;
- `store/settings.ts` caches reminder settings and timezone options together;
- `reminder-settings-modal.tsx` renders `TimezonePicker` inside the reminder modal;
- `profile-section.tsx` edits profile identity and `locale`, but not `timezone`.

The new design moves `locale` and `timezone` editing into tenant settings, not reminder settings.

## Approach options considered

### Option A: add `timezone` to `tenants`

This is the smallest schema change for TPL-17, but it leaves `locale` on `tenants` and makes tenant identity carry more mutable preferences over time. It solves the immediate timezone problem but does not create a future-proof settings boundary.

### Option B: create `tenant_settings` for timezone only

This separates timezone from reminder settings, but leaves locale in `tenants`. That creates two sources for tenant-global preferences: some in `tenants`, some in `tenant_settings`.

### Option C: create `tenant_settings` for both locale and timezone

This creates a clean boundary now: tenant identity remains in `tenants`, global tenant preferences move to `tenant_settings`, and feature-specific settings remain in their feature tables.

Chosen approach: **Option C**.

## Scope

### In scope

- create `tenant_settings` table;
- create `TenantSettings` ORM model;
- migrate existing `tenants.locale` values into `tenant_settings.locale`;
- migrate existing `subscription_reminder_settings.timezone` values into `tenant_settings.timezone`;
- remove `locale` column from `tenants`;
- remove `timezone` column from `subscription_reminder_settings`;
- create tenant settings schemas, repository, service, and API endpoint;
- update locale resolution paths to use tenant settings;
- update timezone resolution paths to use tenant settings;
- update frontend profile/settings UI to edit locale and timezone through tenant settings;
- update tests and architecture docs.

### Out of scope

- generic key/value settings storage;
- adding new tenant settings beyond `locale` and `timezone`;
- changing supported locales beyond the existing `en` and `es` set;
- changing reminder recipient-mode semantics;
- changing n8n workflow structure;
- redesigning the full settings page UI beyond moving locale/timezone ownership;
- adding audit logs for settings changes.

## Data model design

### New table: `tenant_settings`

One row per tenant.

Columns:

- `tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE`
- `locale VARCHAR(10) NOT NULL DEFAULT 'en'`
- `timezone VARCHAR(100) NOT NULL DEFAULT 'UTC'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

No separate `id` column is needed. `tenant_id` is the stable identity and enforces the one-to-one relationship.

### ORM model

Add `backend/app/models/tenant_settings.py`:

```python
class TenantSettings(Base, TimestampMixin):
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    locale: Mapped[str] = mapped_column(
        String(10), default="en", server_default="en", nullable=False
    )
    timezone: Mapped[str] = mapped_column(
        String(100), default="UTC", server_default="UTC", nullable=False
    )

    tenant = relationship("Tenant", back_populates="settings")
```

Update `Tenant`:

```python
settings = relationship(
    "TenantSettings",
    back_populates="tenant",
    cascade="all, delete-orphan",
    uselist=False,
)
```

Update `backend/app/models/__init__.py` to import and export `TenantSettings` so Alembic/model metadata and tests see the table.

### Removed model fields

Remove:

- `Tenant.locale`
- `SubscriptionReminderSettings.timezone`

Do not add compatibility properties on `Tenant` that lazily access settings. Async SQLAlchemy lazy loading can hide N+1 queries and create runtime errors outside a greenlet context. Code should explicitly load or resolve tenant settings where needed.

## Migration design

Create a new Alembic revision after current head `07fa809c3ab3`.

### Upgrade

1. Create `tenant_settings`.
2. Insert one settings row per existing tenant:

```sql
INSERT INTO tenant_settings (tenant_id, locale, timezone)
SELECT
    t.id,
    COALESCE(t.locale, 'en'),
    COALESCE(srs.timezone, 'UTC')
FROM tenants t
LEFT JOIN subscription_reminder_settings srs
    ON srs.tenant_id = t.id;
```

3. Drop `subscription_reminder_settings.timezone`.
4. Drop `tenants.locale`.
5. Enable and force RLS on `tenant_settings`.
6. Create RLS policies for `tenant_settings`.

### Downgrade

1. Re-add `tenants.locale` as nullable, then backfill from `tenant_settings.locale`, defaulting to `en`.
2. Make `tenants.locale` non-null with server default `en`.
3. Re-add `subscription_reminder_settings.timezone` with server default `UTC`.
4. Backfill existing reminder settings rows from `tenant_settings.timezone`, defaulting to `UTC`.
5. Drop `tenant_settings` RLS policies.
6. Disable/no-force RLS on `tenant_settings`.
7. Drop `tenant_settings`.

### RLS policy requirements

`tenant_settings` contains preferences, not secrets, but it is still tenant-scoped data. Add explicit RLS coverage.

Required behavior:

- master role can manage tenant settings as part of tenant management;
- tenant role can read its own settings even if the tenant is inactive, so inactive-account messages can still be localized;
- tenant role can write its own settings only when the tenant is active;
- client role has no direct write access;
- background/internal jobs using master context can read settings needed for reminders and cleanup.

Recommended policy shape:

- a SELECT policy allowing:
  - `current_role = 'master'`; or
  - `current_role = 'tenant'` and the setting row belongs to the current owner user;
- an INSERT/UPDATE/DELETE policy allowing:
  - `current_role = 'master'`; or
  - `current_role = 'tenant'`, row belongs to the current owner user, and tenant is active.

Update RLS SQL tests so they assert `tenant_settings` has `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and named policy coverage.

## Backend API design

### New endpoint group: `/api/v1/tenant-settings`

Create `backend/app/api/v1/endpoints/tenant_settings.py` and include it from `backend/app/api/v1/router.py`.

Auth:

- tenant: resolved via `ActiveTenantId`;
- master: requires active tenant context through existing `ActiveTenantId` dependency;
- client: forbidden.

#### `GET /api/v1/tenant-settings`

Returns the current active tenant's global settings.

Response:

```json
{
  "tenant_id": "uuid",
  "locale": "es",
  "timezone": "America/Santo_Domingo",
  "created_at": "...",
  "updated_at": "..."
}
```

If the row is missing, the service should create a default row and return it. This protects existing test fixtures and any future data drift.

#### `PUT /api/v1/tenant-settings`

Partial update.

Request:

```json
{
  "locale": "es",
  "timezone": "America/Santo_Domingo"
}
```

Validation:

- `locale` must be one of `VALID_LOCALES`;
- `timezone` must be a valid IANA timezone identifier, using the same validation currently used for reminder settings;
- omitted fields keep existing values.

#### `GET /api/v1/tenant-settings/timezones`

Move the timezone catalog endpoint here because timezone is no longer a subscription setting.

Response remains the current list of timezone options:

```json
[
  { "value": "UTC", "label": "UTC (UTC+00:00)", "group": "..." }
]
```

The current timezone catalog implementation can be moved to a neutral module or re-exported from its current implementation during the first pass. The endpoint path should be tenant settings owned.

### `/api/v1/me` behavior

`GET /api/v1/me` may keep returning `locale` and should add `timezone` as read-only projections from `tenant_settings`, because the frontend profile page and client context can benefit from a single profile payload.

`PUT /api/v1/me` should no longer own writes to `locale`, and must not accept `timezone`. Profile writes should remain identity fields only:

- tenant: `full_name`, `email`, `phone`;
- master: `name`, `phone`;
- client: read-only.

Frontend code must use `/tenant-settings` to save `locale` and `timezone`.

### Subscription settings API behavior

`GET /api/v1/subscription-settings` response removes `timezone`.

Response fields after refactor:

- `id`
- `tenant_id`
- `warning_days`
- `reminder_time`
- `recipient_mode`
- `reminders_enabled`
- `custom_message_tenant`
- `custom_message_client`
- `created_at`
- `updated_at`

`PUT /api/v1/subscription-settings` request removes `timezone`.

Accepted fields after refactor:

- `warning_days`
- `reminder_time`
- `recipient_mode`
- `reminders_enabled`
- `custom_message_tenant`
- `custom_message_client`

Do not silently continue persisting timezone through reminder settings. There should be one write owner for timezone: `/tenant-settings`.

## Backend services and repositories

### New repository

Add `backend/app/repositories/tenant_settings_repository.py`.

Required functions:

- `get_by_tenant_id(db, tenant_id)`;
- `get_or_create_by_tenant_id(db, tenant_id)`;
- `update_settings(db, tenant_id, payload)`;
- `resolve_locale(db, tenant_id)`;
- `resolve_locale_by_owner(db, owner_user_id)`;
- `resolve_locale_by_client(db, client_owner_user_id)`;
- `resolve_timezone(db, tenant_id)`;
- `get_settings_for_tenant_ids(db, tenant_ids)` for batched reminder/cleanup paths.

Repository functions should not hide commits unless matching existing service patterns require it. Mutating service methods should control transaction boundaries.

### New service

Add `backend/app/services/tenant_settings_service/` or `backend/app/services/tenant_settings_service.py`.

Required behavior:

- create default row when missing;
- validate locale and timezone defensively at service level;
- commit and restore RLS context after successful mutation;
- provide a small API-facing surface for endpoint handlers.

### Tenant creation

Update `tenant_service.create_tenant()` so every new tenant receives a default settings row in the same logical creation flow:

- `locale = 'en'`;
- `timezone = 'UTC'`.

This is still backed by the service/repository fallback, but new data should be complete at creation time.

### Locale resolution

Move locale resolution responsibility out of `tenants_repository` and into either:

- `tenant_settings_repository`, with `tenants_repository` delegating for backwards import stability; or
- directly update all call sites to import `tenant_settings_repository`.

Required updated call sites:

- `app/api/dependencies.py::resolve_locale`;
- `app/api/v1/endpoints/i18n.py`;
- `app/api/v1/endpoints/me.py::_resolve_profile_locale`;
- WhatsApp tenant console facade locale resolution;
- WhatsApp tenant profile locale update flow;
- any tests that directly assert `Tenant.locale` behavior.

### Timezone resolution

Move timezone resolution responsibility out of subscription reminder settings.

Required updated call sites:

- `subscription_service/reminder_settings.py` no longer creates or updates timezone;
- `subscription_job_service/reminder_schedule.py` batch-loads tenant settings;
- `subscription_job_service/reminder_payloads.py` uses `tenant_settings.timezone` and `tenant_settings.locale`;
- `subscription_job_service/cleanup.py` uses `tenant_settings.timezone`.

## Reminder scheduling behavior

Reminder behavior must not change except for the source of timezone.

Current semantics retained:

- `reminder_time` means "send starting at this tenant-local time";
- `warning_days` is evaluated against the tenant-local expiry date;
- dedupe uses local `sent_for_date`;
- invalid timezone skips that tenant's reminder generation without failing the full batch;
- n8n does not perform timezone calculations.

New source of truth:

```text
tenant_settings.timezone
```

The reminder generator should batch-load:

1. candidate subscriptions;
2. subscription reminder settings;
3. tenants;
4. tenant settings.

Build maps:

- `tenant_id -> SubscriptionReminderSettings | None`;
- `tenant_id -> Tenant | None`;
- `tenant_id -> TenantSettings | None`.

Skip a subscription when tenant settings are missing only if default creation is unsafe in that path. Preferred behavior is to use the service/repository default fallback, then proceed with `locale='en'` and `timezone='UTC'`.

## Cleanup behavior

`cleanup.py` currently claims tenant-local end-of-day semantics but does not fully apply timezone to the end-of-day calculation. This refactor should fix that while moving the source of timezone.

Required behavior:

1. Load `tenant_settings.timezone` for each relevant tenant.
2. Compute tenant-local end of day in that timezone.
3. Convert that end-of-day instant back to UTC.
4. Compare `expires_at` against that UTC boundary.
5. Fallback to `UTC` only if settings are missing; skip/log if timezone is invalid.

This keeps subscription expiration aligned with the tenant's local calendar day.

## WhatsApp behavior

### Tenant console locale

The WhatsApp tenant console facade currently resolves locale from the tenant record and passes it into the console service once per message. After the refactor, it should resolve locale from tenant settings.

Inactive tenant behavior matters: if a tenant is inactive, the facade still needs locale to render the inactive-account response. Tenant settings RLS must allow owner read for inactive tenants, or the facade must resolve locale before applying active-state restrictions through a safe repository path.

### Profile locale flow

The WhatsApp tenant profile flow currently changes locale by directly updating `Tenant.locale`. Replace that direct SQL update with a tenant settings service/repository update.

The locale change confirmation should still switch the per-message ContextVar to the new locale before rendering the success response.

### Timezone in WhatsApp

No WhatsApp flow is required to edit timezone in this spec. The timezone is managed in the web settings UI. WhatsApp flows should only consume timezone indirectly where subscription date formatting or expiration logic already depends on backend services.

## Frontend design

### API types

Add tenant settings API types and functions, preferably in `frontend/src/features/admin/services/settings-api.ts` unless the implementation chooses a small separate `tenant-settings-api.ts` for clarity.

Required types:

```ts
export interface TenantSettings {
  tenant_id: string;
  locale: string;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface TenantSettingsUpdate {
  locale?: string;
  timezone?: string;
}
```

Required functions:

- `getTenantSettings()` -> `GET /tenant-settings`;
- `updateTenantSettings(payload)` -> `PUT /tenant-settings`;
- `getTimezones()` -> `GET /tenant-settings/timezones`.

Remove `timezone` from `ReminderSettings` and `ReminderSettingsUpdate`.

### Store

Update `frontend/src/store/settings.ts` so it separates:

- reminder settings cache;
- tenant settings cache;
- timezone options cache.

`loadTenantSettings()` currently loads reminder settings and timezone options. Rename or split to avoid ambiguity. Recommended shape:

- `loadReminderSettings()`;
- `loadTenantSettings()`;
- `loadTimezoneOptions()`;
- `updateReminderSettings()`;
- `updateTenantSettings()`;
- `clearSettingsCache()` clears all three caches.

### Reminder modal

Remove `TimezonePicker` from `reminder-settings-modal.tsx`.

The modal should continue to edit:

- enable/disable reminders;
- warning days;
- reminder time;
- recipient mode;
- custom tenant/client messages.

When reminders are enabled, show a small read-only note using current tenant settings if available:

```text
Los recordatorios usan la zona horaria configurada en tu perfil: America/Santo_Domingo.
```

If tenant settings are not loaded, omit the note or show `UTC` as defensive fallback.

### Profile/settings section

Move locale and timezone editing into the profile/settings area.

`profile-section.tsx` should edit identity fields and tenant-global settings together in the UI, but persist them through separate API calls:

1. save profile identity fields through `PUT /me`;
2. save locale/timezone through `PUT /tenant-settings`.

If locale changes successfully, reload the i18n catalog so the UI switches language immediately. The existing frontend already loads the catalog after login and on initial authenticated render, so the profile save path should explicitly call `loadCatalog()` after a locale update.

### Timezone picker

Reuse existing `TimezonePicker` in the profile/settings area.

Timezone options should come from `GET /tenant-settings/timezones`, not `/subscription-settings/timezones`.

## Documentation updates

Update these docs during implementation:

- `docs/architecture/database-schema.md`
  - add `TenantSettings`;
  - remove `Tenant.locale`;
  - remove `SubscriptionReminderSettings.timezone`.
- `docs/architecture/i18n-system.md`
  - replace `Tenant.locale` with `TenantSettings.locale`;
  - update locale resolution flow.
- `docs/architecture/subscriptions.md`
  - explain that reminder timezone comes from `tenant_settings.timezone`;
  - remove timezone from reminder settings table docs.
- `docs/architecture/api-layer.md`
  - add `/tenant-settings` endpoint group;
  - update `/subscription-settings` contract.
- `docs/architecture/frontend-architecture.md` or relevant frontend docs
  - update settings UI ownership if it is documented there.

## Testing requirements

### Backend tests

Update or add tests for:

1. `TenantSettings` model defaults and persistence.
2. Alembic/RLS SQL coverage for `tenant_settings`.
3. `GET /api/v1/tenant-settings` returns defaults.
4. `PUT /api/v1/tenant-settings` updates valid `locale` and `timezone`.
5. `PUT /api/v1/tenant-settings` rejects invalid locale.
6. `PUT /api/v1/tenant-settings` rejects invalid timezone.
7. `GET /api/v1/me` reads projected locale/timezone from tenant settings.
8. `PUT /api/v1/me` no longer owns locale writes.
9. `/api/v1/i18n/catalog` resolves locale from tenant settings for tenant users.
10. `/api/v1/i18n/catalog` resolves locale from tenant settings for client users.
11. WhatsApp tenant console locale resolution uses tenant settings.
12. WhatsApp profile locale flow updates tenant settings, not `tenants`.
13. `GET /api/v1/subscription-settings` no longer includes timezone.
14. `PUT /api/v1/subscription-settings` no longer persists timezone.
15. Reminder payload generation uses `tenant_settings.timezone` for eligibility and local dates.
16. Reminder payload generation uses `tenant_settings.locale` for rendered message language.
17. Cleanup uses `tenant_settings.timezone` for tenant-local end-of-day boundaries.
18. Tenant creation creates a default `TenantSettings` row.

Existing tests that currently use `PUT /api/v1/me` to change locale must move to `PUT /api/v1/tenant-settings`.

Existing subscription settings tests that assert timezone in reminder settings must move to tenant settings tests.

### Frontend tests

If frontend tests exist or are added for this area, cover:

1. reminder settings payload no longer includes timezone;
2. profile/settings section saves locale/timezone through tenant settings API;
3. locale change triggers catalog reload;
4. timezone picker renders in profile/settings section, not reminder modal.

### Manual checks

Run before merging:

```bash
cd backend && uv run pytest
cd backend && uv run ruff check .
cd backend && uv run ruff format .
cd frontend && npm test
```

If implementation changes frontend formatting/lint tooling beyond existing scripts, use the repo's current frontend verification command.

## Acceptance criteria

- `tenant_settings` exists and has one row per tenant after migration.
- Existing `tenants.locale` values are preserved in `tenant_settings.locale`.
- Existing `subscription_reminder_settings.timezone` values are preserved in `tenant_settings.timezone`.
- `tenants.locale` no longer exists.
- `subscription_reminder_settings.timezone` no longer exists.
- New tenants receive default settings: `locale='en'`, `timezone='UTC'`.
- Locale resolution for REST, frontend i18n, WhatsApp tenant console, and client users reads tenant settings.
- Timezone resolution for reminders and cleanup reads tenant settings.
- Reminder settings API no longer accepts or returns timezone.
- Tenant settings API owns locale/timezone writes.
- Reminder settings UI no longer contains timezone picker.
- Profile/settings UI contains both locale and timezone controls.
- Tests pass.
- Relevant architecture docs are updated.

## Risks and mitigations

### Risk: missing settings row causes runtime failures

Mitigation: migration inserts a row for every tenant, tenant creation creates a row, and service read paths have get-or-create default fallback.

### Risk: async lazy loading from `Tenant.settings`

Mitigation: do not rely on implicit lazy relationship access. Use explicit repository functions or eager loading when settings are needed.

### Risk: locale resolution after failed transactions

Mitigation: keep the existing pattern of resolving locale before mutating service calls when translated errors are needed. Where that is not possible, restore RLS context before resolving locale.

### Risk: invalid historical timezone value

Mitigation: migrate values as-is to preserve data, validate future writes, and keep reminder generation defensive: invalid timezone skips that tenant and logs a warning.

### Risk: API contract break for reminder settings

Mitigation: update frontend in the same change. No external reminder settings clients are documented. The new owner endpoint is `/tenant-settings`.

### Risk: docs and code disagree about frontend stack

Mitigation: follow current code (`React/TSX`, Zustand) for implementation, and update architecture docs if they still refer to older Vue/Pinia patterns in touched areas.

## Implementation notes for the next phase

Suggested order:

1. Add model and migration.
2. Add repository/service/schemas/endpoint for tenant settings.
3. Update tenant creation and test fixtures.
4. Move locale resolution paths.
5. Move timezone resolution paths.
6. Update subscription settings schemas/services/API.
7. Update frontend API/store/components.
8. Update tests.
9. Update docs.
10. Run backend/frontend verification.

Do not implement broad generic settings, audit logging, or unrelated refactors in this issue.
