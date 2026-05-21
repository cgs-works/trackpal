# Spec: Tenant Subscriptions

Status: active
Owner: Wilfredo
Created: 2026-05-20

## Problem

Tenants can currently manage catalog services/plans and clients, but cannot assign streaming-account access to clients as subscriptions. Trackpal needs a tenant-scoped subscription module so tenants can sell or manage access to streaming accounts, track expiration/cancellation, renew service periods, and receive configurable renewal warnings.

## Goals

- Allow each Tenant to create subscriptions from their own catalog for their own clients.
- Support both recurring subscriptions and one-off/puntual access records using the same entity.
- Store subscription duration on the subscription, not on the plan.
- Provide predefined durations: 1 month, 3 months, 6 months, 9 months, 1 year, and custom date.
- Require service, plan, client, streaming account email, start date, and expiration date.
- Make streaming account password optional.
- Make streaming profile optional.
- Make streaming profile PIN optional, but require profile when PIN is provided.
- Encrypt streaming password and profile PIN reversibly with `DATA_ENCRYPTION_KEY` from environment.
- Show credentials masked by default in web UI, with reveal icons per row/detail.
- Keep streaming account email in plain text for display/search/filtering.
- Support subscription states: `active`, `expired`, `cancelled`.
- Cancel subscriptions by status change, not immediate deletion.
- Hide cancelled subscriptions from default active listings; show them in their own filter/category.
- Auto-cancel expired subscriptions after 7 days.
- Auto-delete cancelled subscriptions after 30 days if not reactivated.
- Reactivate cancelled subscriptions by asking for a new duration and recalculating dates.
- Renew active subscriptions by extending from current `expires_at`, not from today.
- Keep a simple subscription event history.
- Provide tenant-scoped REST API under `/api/v1/subscriptions`.
- Allow both Tenant users and Master users in active tenant context to manage subscriptions.
- Add a dedicated frontend page for subscriptions.
- Add navigation from Tenant dashboard and client rows/details to subscriptions.
- Add full WhatsApp CRUD for Tenant subscription management.
- Add configurable web + WhatsApp expiration reminders.

## Non-Goals

- No price, cost, payment, invoice, or balance tracking in v1.
- No client-initiated renewal via WhatsApp in v1.
- No validation that streaming account email is unique.
- No validation that profile name is unique.
- No payment history.
- No full audit trail beyond simple subscription events.

## Current Behavior

Relevant existing modules:

- `backend/app/models/tenant.py`: core tenant entity.
- `backend/app/models/client.py`: tenant-scoped clients with optional phone.
- `backend/app/models/service.py`: tenant-scoped catalog service.
- `backend/app/models/plan.py`: tenant-scoped catalog plan. Current fields: `id`, `tenant_id`, `service_id`, `name`.
- `backend/app/api/v1/endpoints/catalog.py`: service/plan API scoped through `ActiveTenantId`.
- `backend/app/api/v1/endpoints/clients.py`: client API scoped through `ActiveTenantId`.
- `backend/app/services/catalog_service.py`: tenant-scoped catalog CRUD.
- `backend/app/services/client_service.py`: tenant-scoped client CRUD.
- `backend/app/services/whatsapp_tenant_console_service.py`: existing Tenant WhatsApp console for clients/catalog/profile.
- `frontend/src/views/TenantDashboardView.vue`: current tenant dashboard with profile, catalog, clients, password change.
- `frontend/src/stores/auth.js`: active tenant context for Master.
- `frontend/src/router/index.js`: route guards allow Tenant and Master-with-context.

Current plan model has no price or duration. Duration for subscriptions must therefore be stored on the subscription.

## Desired Behavior

### Data Model

Create `subscriptions` table with tenant isolation and relationships:

- `id: UUID`
- `tenant_id: UUID` FK `tenants.id`, cascade delete
- `client_id: UUID` FK `clients.id`, cascade delete
- `service_id: UUID` FK `services.id`, cascade delete
- `plan_id: UUID` FK `plans.id`, cascade delete
- `streaming_email: str`
- `streaming_password_encrypted: str | null`
- `profile_name: str | null`
- `profile_pin_encrypted: str | null`
- `duration_type: enum/string` with values like `1_month`, `3_months`, `6_months`, `9_months`, `1_year`, `custom`
- `starts_at: date/datetime`
- `expires_at: date/datetime`
- `cancelled_at: date/datetime | null`
- `status: active | expired | cancelled`
- timestamps from existing mixin

Create `subscription_events` table:

- `id: UUID`
- `tenant_id: UUID`
- `subscription_id: UUID`
- `event_type: str` such as `created`, `updated`, `renewed`, `cancelled`, `reactivated`, `expired`, `auto_cancelled`, `auto_deleted`, `reminder_sent`
- `notes: str | null`
- `metadata: JSON | null`
- `created_at`

Create reminder-send log table to deduplicate WhatsApp/web reminder jobs:

- `id: UUID`
- `tenant_id: UUID`
- `subscription_id: UUID`
- `recipient_type: tenant | client`
- `recipient_phone: str | null`
- `days_before_expiry: int`
- `sent_for_date: date`
- `status: pending | sent | failed`
- `attempt_count: int`
- `last_error: str | null`
- `sent_at: date/datetime | null`
- `created_at`

Reminder logs must store only IDs and metadata, not rendered message text, emails, password, PIN, or other secrets.

Add tenant settings for reminders and time handling:

- Config is per tenant.
- Tenant timezone is configurable.
- Default tenant timezone is `UTC`.
- Subscription expiration uses tenant local timezone.
- A subscription that expires on a given date remains active through 23:59:59 of that date in tenant local timezone.
- Default warning days: `[7, 3, 1]`.
- Default reminder time: `09:00` in tenant local timezone.
- Reminder time is configurable per tenant.
- Backend sends reminder payloads only when tenant local time is greater than or equal to configured reminder time and reminder was not already sent.
- Default recipient mode: Tenant only.
- Recipient mode configurable: tenant only, client only, tenant + client.
- If client reminders are enabled and a client has no phone, omit client message and do not fail whole job.

### Validation Rules

- `client_id`, `service_id`, and `plan_id` must belong to active tenant context.
- Selected plan must belong to selected service.
- `streaming_email` is required and stored in plain text.
- `streaming_password` is optional and encrypted if present.
- `profile_name` is optional.
- `profile_pin` is optional, encrypted if present, and requires `profile_name`.
- Email may repeat across subscriptions.
- Profile may repeat across subscriptions.
- Editing service must clear/require new plan selection unless selected plan belongs to new service.
- Deleting client/service/plan should cascade delete subscriptions, but UI must warn and require confirmation when related subscriptions exist.

### API

Use tenant-scoped flat routes under `/api/v1/subscriptions`:

- `POST /api/v1/subscriptions`
- `GET /api/v1/subscriptions`
- `GET /api/v1/subscriptions/{subscription_id}`
- `PUT/PATCH /api/v1/subscriptions/{subscription_id}`
- `POST/PATCH /api/v1/subscriptions/{subscription_id}/cancel`
- `POST/PATCH /api/v1/subscriptions/{subscription_id}/reactivate`
- `POST/PATCH /api/v1/subscriptions/{subscription_id}/renew`
- `GET /api/v1/subscriptions/{subscription_id}/events`
- `GET/PUT /api/v1/subscription-settings` or equivalent tenant settings endpoint
- Protected admin/job endpoint for expiration, cancellation, deletion, and reminders.
- Job endpoint reuses existing `N8N_API_KEY` authentication.
- Job endpoint supports task selection by parameter, for example `task=cleanup`, `task=reminders`, or `task=all`.
- Job endpoint returns detailed per-item results with IDs/metadata only; it must not return credentials or PII.
- Reminder mark endpoints for n8n:
  - mark reminder as sent after successful Evolution send.
  - mark reminder as failed when Evolution send fails.

List filters:

- `status`: `active`, `expired`, `cancelled`
- `client_id`
- `service_id`
- expiration quick filters: expired, today, next 7 days, next 30 days
- custom expiration range: `expires_from`, `expires_to`

### Job Behavior

A protected endpoint must run daily from a dedicated n8n reminder workflow. This workflow must be separate from the existing Master/Tenant WhatsApp console workflows.

- Endpoint authentication reuses `N8N_API_KEY`.
- Endpoint supports `task=cleanup`, `task=reminders`, and `task=all`.
- Reminder endpoint supports batch pagination with `limit` and opaque `next_cursor`.
- Default/max reminder batch size is 100 per execution.
- n8n should process one page per workflow run.
- Mark active subscriptions with past `expires_at` as `expired`.
- Move subscriptions expired for 7+ days to `cancelled` and set `cancelled_at` if needed.
- Delete subscriptions cancelled for 30+ days if not reactivated.
- Continue processing other subscriptions when one item fails.
- Return detailed per-item results with only IDs, action names, statuses, and errors.
- Send reminder payloads based on tenant settings.
- For reminders, backend renders final Spanish message text and returns payloads to n8n.
- n8n sends reminders through Evolution using each tenant's `evolution_instance_name`.
- n8n sends messages sequentially.
- n8n waits 2 seconds between messages.
- Backend marks reminders as sent only after n8n confirms successful Evolution send.
- If Evolution send fails, n8n marks reminder as `failed`.
- Failed reminders retry up to 3 attempts.
- Deduplicate reminders using persistent DB log.

### Frontend

Create dedicated subscriptions page, not inside `TenantDashboardView.vue`.

Required UI:

- Navigation from Tenant dashboard to subscriptions page.
- Navigation from client list/row/detail to subscriptions filtered by client.
- Create subscription form:
  - Client selector.
  - Service selector.
  - Plan selector filtered by selected service.
  - Streaming email.
  - Optional streaming password.
  - Duration selector: 1 month, 3 months, 6 months, 9 months, 1 year, custom.
  - Custom duration shows date selector.
  - Button to add profile/PIN fields.
  - PIN input requires profile.
- List/table with filters by status, client, service, quick expiry range, custom expiry range.
- Default list excludes cancelled subscriptions unless cancelled filter/category selected.
- Password and PIN masked by default with reveal icon.
- Empty password shows “Sin contraseña” and no reveal button.
- Edit subscription flow including service/plan reset rule.
- Cancel action moves to `cancelled`.
- Reactivate action asks for new duration.
- Renew action extends from current `expires_at`.
- Reminder settings UI for timezone, warning days, reminder time, and recipient mode.

### WhatsApp Tenant Console

Add full Tenant subscription CRUD to existing Tenant WhatsApp console.

Required flows:

- List subscriptions with filters/status categories.
- Create subscription.
- View subscription details.
- Edit subscription.
- Cancel subscription.
- Reactivate subscription with new duration.
- Renew subscription extending from current `expires_at`.
- Reveal credentials directly in WhatsApp when viewing details; no confirmation required for reveal.
- When creating/editing credentials through WhatsApp, use double confirmation before saving sensitive values.
- Respect same backend validations as web.

### Security

- Add `DATA_ENCRYPTION_KEY` to `.env.example`.
- Use `cryptography.Fernet` with a base64 Fernet key generated by `Fernet.generate_key()`.
- Do not implement key rotation in v1.
- Backend startup must fail if `DATA_ENCRYPTION_KEY` is missing or invalid.
- Password and PIN must be encrypted at rest with reversible encryption.
- Do not log plaintext password or PIN.
- List/detail API responses return masked/flag fields only, not decrypted secrets.
- Add a dedicated reveal endpoint that returns both password and PIN if present.
- Do not create subscription history events when credentials are revealed.
- WhatsApp detail flow may call reveal internally and show full credentials without extra confirmation.
- Web UI must reveal credentials only after user clicks reveal icon.

## Acceptance Criteria

- [ ] Tenant can create subscription for own client with service, plan, streaming email, optional password, optional profile, optional PIN, and duration.
- [ ] Master in active tenant context can manage subscriptions for selected tenant.
- [ ] Backend rejects client/service/plan from another tenant.
- [ ] Backend rejects plan not belonging to selected service.
- [ ] Backend rejects PIN without profile.
- [ ] Password and PIN are encrypted in DB using Fernet and decrypted only through authorized reveal flows.
- [ ] `DATA_ENCRYPTION_KEY` exists in `.env.example` and backend fails startup if key is missing/invalid.
- [ ] Normal list/detail API responses do not include decrypted password or PIN.
- [ ] Dedicated reveal endpoint returns both password and PIN when authorized.
- [ ] Revealing credentials does not create history/audit events.
- [ ] Subscription list supports status, client, service, quick expiry filters, and custom expiry range.
- [ ] Cancelled subscriptions do not appear in default list and appear under cancelled filter/category.
- [ ] Cancelling sets status `cancelled` and `cancelled_at` without immediate delete.
- [ ] Reactivating asks for duration and recalculates `starts_at`/`expires_at`.
- [ ] Renewing active subscription extends from existing `expires_at`.
- [ ] Tenant timezone is configurable and defaults to `UTC`.
- [ ] Subscription expiration uses tenant local end-of-day semantics.
- [ ] Reminder time is configurable and defaults to `09:00` tenant local time.
- [ ] Reminder payloads are returned only after configured local reminder time.
- [ ] Job endpoint reuses `N8N_API_KEY`, supports task parameter, and returns detailed ID/metadata-only results.
- [ ] Job marks expired subscriptions, auto-cancels after 7 days expired, and auto-deletes after 30 days cancelled.
- [ ] Job continues processing other items when one subscription fails.
- [ ] Reminder endpoint supports `limit` plus opaque `next_cursor`, with batch size 100.
- [ ] Dedicated n8n reminder workflow processes one page per run and sends reminder payloads through each tenant's Evolution instance.
- [ ] Backend renders final reminder message text for n8n.
- [ ] Backend marks reminders sent only after n8n confirms Evolution success.
- [ ] n8n can mark reminders failed, and failed reminders retry up to 3 attempts.
- [ ] Job sends configurable reminders and deduplicates sends.
- [ ] Tenant default reminder settings are `[7, 3, 1]` days and tenant-only recipient.
- [ ] Client reminder omission due to missing phone does not fail job.
- [ ] Frontend dedicated subscriptions page exists and is reachable from dashboard and clients.
- [ ] Web credentials are masked by default and revealable per row/detail.
- [ ] WhatsApp Tenant console supports subscription CRUD, renewal, reactivation, cancellation, listing, and detail view.
- [ ] WhatsApp creation/editing of sensitive credentials requires double confirmation before save.
- [ ] WhatsApp detail view can show full credentials without extra confirmation.
- [ ] Tests cover model constraints, service validations, API permissions, job behavior, encryption, frontend build, and WhatsApp flows.

## Edge Cases

- Custom duration date before start date.
- Renewal when active subscription already expired but job has not run.
- Reactivation of cancelled subscription older than 30 days if cleanup has not run.
- Client/service/plan deletion with existing subscriptions requires UI warning/confirmation.
- Client phone missing while client reminders enabled.
- Invalid or missing `DATA_ENCRYPTION_KEY`.
- Empty password on create or edit.
- Clearing existing password/PIN during edit.
- Changing service while old plan no longer valid.
- Master without `activeTenantId` attempting tenant-scoped subscription access.
- Duplicate job execution on same day.
- Timezone/date boundary for expiration and reminders.

## Suggested Approach

Likely backend files:

- Add models under `backend/app/models/`:
  - `subscription.py`
  - optional `subscription_event.py`
  - optional `subscription_reminder_log.py`
- Add schemas under `backend/app/schemas/subscription.py`.
- Add service under `backend/app/services/subscription_service.py`.
- Add endpoint under `backend/app/api/v1/endpoints/subscriptions.py`.
- Register router in `backend/app/api/v1/router.py`.
- Add Fernet encryption helper under `backend/app/core/` and config field in `backend/app/core/config.py`.
- Add Alembic migration with RLS policies for subscription tables.
- Add tests under `backend/tests/test_subscriptions.py` and WhatsApp-specific tests.
- Extend `backend/app/services/whatsapp_tenant_console_service.py` and facade/menu routing.

Likely frontend files:

- Add `frontend/src/views/SubscriptionsView.vue`.
- Update `frontend/src/router/index.js`.
- Update `frontend/src/views/TenantDashboardView.vue` for navigation.
- Update client UI area for client-filtered subscription navigation.
- Extend API wrapper usage in `frontend/src/services/api.js` if needed.

Implementation should be phased because scope includes database, API, frontend, job, and WhatsApp flows.

## Testing Plan

Run narrow checks relevant to changed area first, then full listed set when risk warrants:

```bash
cd backend && uv run pytest -v
cd frontend && npm run build
```

Additional targeted tests expected:

```bash
cd backend && uv run pytest tests/test_subscriptions.py -v
cd backend && uv run pytest tests/test_tenant_console_service.py -v
cd backend && uv run pytest tests/test_rls_policy_sql.py -v
```

## Documentation Updates

- Update `docs/architecture/database-schema.md` with subscription tables and relationships.
- Update `docs/architecture/api-layer.md` with subscription endpoints.
- Update `docs/architecture/frontend-architecture.md` with subscriptions page.
- Update `docs/architecture/whatsapp-console-flow.md` with Tenant subscription CRUD.
- Update `docs/project-pdr/business-rules.md` with subscription lifecycle rules.
- Update `.env.example` with `DATA_ENCRYPTION_KEY`.

## Risks / Open Questions

- Exact UX layout of dedicated subscription page remains open.
- Exact Spanish reminder message copy remains open.
- Exact n8n workflow JSON and node-level error handling remain open.
