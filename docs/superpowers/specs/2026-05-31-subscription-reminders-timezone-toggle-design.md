# Subscription reminders timezone-aware scheduling and tenant toggle

Date: 2026-05-31
Status: Proposed

## Goal

Update the subscription reminder system so reminder dispatch respects each tenant's configured IANA timezone and chosen reminder hour, while adding a tenant-controlled toggle to enable or disable the reminder system entirely.

The intended business behavior is:

- reminders are sent **starting at** the tenant's configured local time, never before it;
- if the system detects the reminder later than that time, it should still send it as soon as possible that same day;
- reminder scheduling must remain controlled by the backend, with n8n acting as transport only;
- tenants must be able to opt in explicitly because the new toggle defaults to off.

## Decisions captured

1. **Scheduling model**: backend-driven eligibility with n8n polling every 30 minutes.
2. **Reminder semantics**: `reminder_time` means "send reminders starting at this tenant-local time", not "send exactly at this minute".
3. **Timezone format**: exact IANA timezone identifiers such as `America/Bogota` and `Europe/Madrid`.
4. **Toggle**: a new reminder enable/disable flag per tenant.
5. **Default toggle state**: off for existing tenants and new tenants.
6. **Disabled behavior**: when off, the backend generates no pending reminder logs and returns no reminder payloads for that tenant.
7. **Delay tolerance**: if the configured time has already passed, the reminder should be sent on the next eligible polling cycle.
8. **Frontend behavior when disabled**: reminder configuration fields remain hidden until the toggle is enabled.
9. **Timezone catalog sourcing**: use a backend-served timezone list that may fetch from an external API, but must always have a safe local fallback.

## Current problems

1. The current reminder workflow runs once per day at 09:00 and does not support tenant-specific send windows.
2. The backend stores `timezone` and `reminder_time`, but current reminder generation treats reminder time as UTC and ignores tenant-local scheduling.
3. The current reminder generation path uses an N+1 access pattern that is not appropriate for a polling model.
4. The frontend exposes timezone and reminder time, but the current UX suggests a fixed send time rather than a "starting at" window.
5. There is no tenant-level switch to opt in or opt out of reminder generation.

## Scope

### In scope

- make reminder generation tenant-timezone aware;
- make reminder eligibility depend on tenant-local time;
- add a tenant-level reminder toggle;
- update reminder settings API and frontend UX;
- update the n8n reminder workflow from once-daily to every 30 minutes;
- optimize backend reminder generation to avoid per-subscription N+1 queries;
- provide a safe timezone catalog endpoint for the frontend.

### Out of scope

- redesigning recipient mode semantics beyond compatibility with the current feature;
- redesigning the full subscriptions screen;
- moving reminder delivery out of n8n;
- tenant-specific cron schedules in n8n;
- audit logging for toggle changes.

## Proposed architecture

### High-level flow

1. n8n triggers the subscription reminder workflow every 30 minutes.
2. n8n calls the backend pending-reminders endpoint.
3. The backend loads candidate subscriptions, tenant reminder settings, and tenant records in batches.
4. For each subscription, the backend computes the tenant-local current time and tenant-local expiry date.
5. The backend generates reminder logs and payloads only when the tenant:
   - has reminders enabled;
   - has reached or passed the configured local reminder time;
   - matches one of the configured warning days;
   - has not already generated a reminder for that subscription / recipient / warning day / local reminder date.
6. n8n sends returned reminders through Evolution.
7. n8n marks reminders as sent or failed using the existing backend endpoints.

n8n remains a transport workflow. The backend remains the source of truth for scheduling, eligibility, deduplication, and timezone handling.

## Data model changes

### Existing table reused

`subscription_reminder_settings`

Current fields retained:

- `tenant_id`
- `timezone`
- `warning_days`
- `reminder_time`
- `recipient_mode`

### New field

Add:

- `reminders_enabled: bool not null default false`

### Field semantics

#### `timezone`

- continues to be stored as a string;
- must now be validated as an IANA timezone identifier;
- examples: `America/Bogota`, `Europe/Madrid`, `UTC`.

#### `reminder_time`

- remains stored as `HH:MM`;
- semantic meaning becomes:
  - **do not send reminders before this tenant-local time**;
  - **send reminders at the first eligible poll after this tenant-local time**.

#### `reminders_enabled`

- when `false`, the reminder engine must skip the tenant completely;
- no pending logs should be created;
- no reminder payloads should be returned to n8n.

### Defaults and migration behavior

- existing tenants: `reminders_enabled = false`
- new tenants: `reminders_enabled = false`
- auto-created reminder settings rows: `reminders_enabled = false`

This is an intentional behavioral reset. Tenants must explicitly activate reminder automation.

## API changes

### Existing endpoint: `GET /api/v1/subscription-settings`

Response adds:

- `reminders_enabled: boolean`

Response contract after change:

- `reminders_enabled`
- `timezone`
- `warning_days`
- `reminder_time`
- `recipient_mode`

### Existing endpoint: `PUT /api/v1/subscription-settings`

Request adds:

- `reminders_enabled: boolean`

Validation rules:

- `timezone` must be a valid supported IANA identifier;
- `reminder_time` must remain valid `HH:MM`;
- `warning_days` remains list-based;
- `recipient_mode` remains validated against existing supported values.

### New endpoint: `GET /api/v1/subscription-settings/timezones`

Purpose:

- provide the frontend with a safe timezone catalog from the backend;
- prevent direct frontend dependency on a third-party timezone service.

Response item shape:

- `value`: IANA timezone id
- `label`: display label, e.g. `America/Bogota (UTC-05:00)`

Backend sourcing strategy:

1. try external provider if configured/available;
2. otherwise use cached backend copy if available;
3. otherwise return bundled local fallback data.

Failure of the external timezone provider must not break this endpoint.

## Backend scheduling logic

### Eligibility rule

A reminder is eligible only when all these conditions are true:

1. subscription status is `active`;
2. subscription expires in one of the configured warning-day offsets for that tenant;
3. tenant reminder settings exist or are auto-created;
4. `reminders_enabled == true`;
5. tenant timezone is valid;
6. tenant-local current time is at or after `reminder_time`;
7. no duplicate reminder log already exists for the same:
   - `subscription_id`
   - `recipient_type`
   - `days_before_expiry`
   - `sent_for_date`

### Time calculations

All reminder timing decisions must be evaluated in the tenant's local timezone.

The backend should compute:

- `tenant_now`
- `tenant_today`
- `tenant_expiry_date`
- `days_until_expiry = tenant_expiry_date - tenant_today`

This ensures warning-day logic matches the tenant's local calendar day instead of UTC.

### Delay handling

The system must support delayed execution:

- if configured local time is 09:00 and polling occurs at 09:30, reminder generation is still allowed;
- reminders must never be generated before 09:00 local time;
- reminders may be generated any time after 09:00 local time, once, subject to deduplication.

### Invalid timezone handling

If a persisted timezone becomes invalid:

- skip that tenant for reminder generation;
- record an operational warning/log entry;
- do not fail the whole reminder generation job.

## Backend performance requirements

The current implementation pattern in `generate_reminder_payloads()` must be replaced with a batch-loading strategy.

### Required loading strategy

1. load candidate subscriptions in one query;
2. collect tenant ids from those subscriptions;
3. load all matching `SubscriptionReminderSettings` in one query;
4. load all matching `Tenant` records in one query;
5. build in-memory lookup maps:
   - `tenant_id -> settings`
   - `tenant_id -> tenant`
6. perform eligibility checks in memory without per-subscription settings/tenant queries;
7. create reminder logs only for truly eligible items.

### Expected cost profile for ~100 active subscriptions

Target query profile:

- 1 query: subscriptions
- 1 query: reminder settings
- 1 query: tenants
- N inserts only for reminders actually generated

This makes 30-minute polling acceptable without excessive backend load.

## n8n workflow changes

### Workflow file

`n8n/TrackPal Subscription Reminders.json`

### Trigger behavior

Replace the once-daily schedule with a polling schedule every 30 minutes.

n8n must not implement per-tenant timezone logic.

### n8n responsibilities after change

- trigger every 30 minutes;
- call pending-reminders endpoint;
- send returned messages;
- mark sent or failed;
- keep retry/failure behavior already present in the workflow.

### Backend ↔ n8n contract

The endpoint `POST /api/v1/subscriptions/reminders/pending` changes in effective meaning:

- before: fetch items for a once-daily reminder job;
- after: fetch items eligible in the current polling window.

The payload shape can remain compatible with the current workflow. The scheduling meaning changes, not the basic transport flow.

### Operational characteristics

- normal send latency after configured tenant-local reminder time: 0 to 30 minutes;
- if one polling cycle fails, the next cycle can recover;
- backend deduplication prevents duplicate reminder generation under normal reruns.

## Frontend and UX changes

### Reminder toggle

Add a visible toggle to the reminder settings UI:

- ES: `Activar recordatorios automáticos`
- EN: `Enable automatic reminders`

### Hidden configuration when disabled

When the toggle is off:

- hide timezone, warning days, reminder time, and recipient mode configuration fields.

When the toggle is on:

- show the configuration form.

This avoids suggesting that reminder automation is already active when it is not.

### Label changes

Change the reminder-time copy from a fixed-time interpretation to a threshold interpretation.

Recommended label:

- ES: `Enviar recordatorios a partir de las`
- EN: `Send reminders starting at`

Recommended helper text:

- ES: `Los recordatorios nunca se enviarán antes de esta hora en tu zona horaria. Si el sistema se retrasa, se enviarán después, tan pronto como sea posible.`
- EN: `Reminders will never be sent before this time in your time zone. If the system is delayed, they will be sent afterward as soon as possible.`

### Timezone selector

The frontend should stop relying on a hardcoded limited list.

Instead it should:

1. request timezones from `GET /api/v1/subscription-settings/timezones`;
2. render the returned `value`/`label` options;
3. gracefully handle fallback data exactly the same as primary data.

The frontend must not depend directly on a third-party timezone API.

## Error handling

### Timezone catalog provider failure

If the external timezone provider fails:

- backend serves cached or bundled fallback timezones;
- frontend remains functional;
- tenants can still configure reminder settings.

### Reminder generation failure for one tenant

If one tenant has broken or invalid timezone data:

- only that tenant is skipped;
- the overall job continues.

### n8n send failures

Existing mark-failed behavior remains:

- n8n marks send failures using the existing `mark-failed` endpoint;
- backend retry semantics remain unchanged unless implementation work identifies a required fix.

## Edge cases

1. **Exact threshold match**
   - if local time equals `reminder_time`, reminder generation is allowed.

2. **Late poll**
   - if the reminder should have started at 09:00 and polling happens at 09:30, it should generate.

3. **Timezone change after setup**
   - applies only to future polls;
   - existing logs remain historical records.

4. **Reminder time changed during the same day**
   - new value applies to future polls that day;
   - if the new threshold is already in the past and no reminder has yet been generated, next poll may generate it.

5. **DST transitions**
   - local-time computation should rely on IANA timezone support so DST adjustments are handled automatically.

6. **Toggle off after prior sends**
   - future reminders stop;
   - existing reminder logs remain unchanged.

## Testing strategy

Implementation should follow TDD and cover at least the following.

### Backend unit/integration tests

- valid IANA timezone scheduling;
- never generate before local `reminder_time`;
- generate after local `reminder_time`;
- warning-day calculation using tenant-local dates;
- toggle disabled returns no items and creates no logs;
- invalid timezone skips only the broken tenant;
- repeated polling does not duplicate reminder generation;
- batch-loading behavior avoids obvious N+1 regressions.

### API tests

- `GET /subscription-settings` includes `reminders_enabled`;
- `PUT /subscription-settings` persists `reminders_enabled` and validates timezone;
- `GET /subscription-settings/timezones` returns normal data from primary source;
- `GET /subscription-settings/timezones` returns fallback data when the provider fails.

### Frontend tests / checks

- toggle hides and reveals the configuration block;
- updated copy reflects "starting at" semantics;
- timezone list loads from backend endpoint;
- disabled-by-default experience is clear and not misleading.

### n8n verification

- trigger schedule changed to every 30 minutes;
- send/mark-sent/mark-failed flow still works;
- workflow contains no tenant-timezone logic.

## Implementation notes

- Keep n8n simple; do not move scheduling logic into the workflow.
- Keep reminder generation in backend service code.
- Avoid broad refactors outside reminder settings, reminder generation, and the specific frontend reminder settings area.
- Ensure any new timezone utility path does not become a hard dependency on an external service.

## Recommended rollout shape

1. data model and API contract update;
2. backend timezone-aware eligibility + performance refactor;
3. n8n polling schedule update;
4. frontend toggle/UX/timezone catalog update;
5. documentation refresh and verification.
