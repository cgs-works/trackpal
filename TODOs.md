# TODOs

Nightmanager implementation queue.

## Status Tags

- `[bug]` — eligible urgent defect; may omit spec and then uses `specs/TEMPLATE.md ## Testing Plan`.
- `[ready]` — eligible only with a non-draft linked spec.
- `[draft]` — not eligible until human-promoted.
- `[blocked]` — not eligible until reason resolved.
- `[in-progress]` — currently being worked.
- `[done]` — complete; include commit hash, and PR URL only if PR creation succeeds.

## Queue

- [ready] Add tenant subscription data model and encryption foundation
  - Spec: `specs/tenant-subscriptions.md`
  - Scope: create subscription, event, reminder-log, and reminder-settings persistence with tenant RLS plus Fernet encryption helper using `DATA_ENCRYPTION_KEY`.
  - Acceptance:
    - Subscription tables exist with tenant/client/service/plan relationships and cascade behavior.
    - Password and PIN fields are encrypted at rest with Fernet.
    - Backend startup fails when `DATA_ENCRYPTION_KEY` is missing or invalid.
    - Tenant timezone defaults to `UTC`; reminder days default to `[7, 3, 1]`; reminder time defaults to `09:00`.
    - RLS policy tests cover subscription-related tables.
  - Notes: keep event/reminder logs cascade-deleted with subscriptions; do not add key rotation in v1. Validation comes from the spec Testing Plan.

- [ready] Add subscription CRUD API for tenant and master-context users
  - Spec: `specs/tenant-subscriptions.md`
  - Scope: implement `/api/v1/subscriptions` tenant-scoped create/list/detail/update/cancel/reactivate/renew/events endpoints and settings endpoints.
  - Acceptance:
    - Tenant can create, list, edit, cancel, reactivate, and renew own subscriptions.
    - Master with `activeTenantId` can manage selected tenant subscriptions.
    - Backend rejects cross-tenant client/service/plan IDs and plan-service mismatches.
    - PIN without profile is rejected.
    - List filters support status, client, service, quick expiry ranges, and custom expiry range.
    - Normal list/detail responses do not include decrypted password or PIN.
  - Notes: use flat `/api/v1/subscriptions` routes; cancelled subscriptions excluded from default listing. Validation comes from the spec Testing Plan.

- [ready] Add authorized subscription credential reveal flow
  - Spec: `specs/tenant-subscriptions.md`
  - Scope: implement reveal endpoint and service path for decrypted password/PIN access by authorized tenant context.
  - Acceptance:
    - Reveal endpoint returns both password and PIN when present.
    - Empty password returns an explicit empty/null shape suitable for “Sin contraseña”.
    - Unauthorized or cross-tenant reveal attempts are rejected.
    - Revealing credentials does not create history/audit events.
    - Plaintext secrets are not logged.
  - Notes: normal list/detail API must stay masked/flag-only. Validation comes from the spec Testing Plan.

- [ready] Add subscription lifecycle job endpoint
  - Spec: `specs/tenant-subscriptions.md`
  - Scope: implement protected job endpoint using `N8N_API_KEY` with `task=cleanup|reminders|all`, cleanup lifecycle actions, and detailed ID-only results.
  - Acceptance:
    - Active subscriptions past tenant-local end-of-day become `expired`.
    - Subscriptions expired for 7+ days become `cancelled` with `cancelled_at`.
    - Subscriptions cancelled for 30+ days are deleted with cascade logs/events.
    - Job continues processing remaining items when one item fails.
    - Job response includes per-item IDs/action/status/error metadata only, no PII/secrets.
  - Notes: tenant timezone controls date boundaries; default timezone is `UTC`. Validation comes from the spec Testing Plan.

- [ready] Add reminder payload generation and send-status API
  - Spec: `specs/tenant-subscriptions.md`
  - Scope: implement reminder payload generation, opaque cursor pagination, sent/failed mark endpoints, retry limits, and tenant reminder settings behavior.
  - Acceptance:
    - Reminder endpoint returns at most 100 payloads per page and optional opaque `next_cursor`.
    - Payloads are returned only when tenant local time is at or after configured reminder time.
    - Backend renders final Spanish message text for n8n.
    - `mark-sent` records sent status only after n8n confirms Evolution success.
    - `mark-failed` stores failure metadata and retries up to 3 attempts.
    - Client reminders skip clients without phone without failing job.
  - Notes: reminder logs store only metadata, not message text or PII. Validation comes from the spec Testing Plan.

- [ready] Add dedicated n8n workflow for subscription reminders
  - Spec: `specs/tenant-subscriptions.md`
  - Scope: create separate n8n workflow for reminder sending, independent from current Master/Tenant WhatsApp console workflows.
  - Acceptance:
    - Workflow calls backend reminder job with `N8N_API_KEY`.
    - Workflow processes one page per run.
    - Workflow sends through each tenant `evolution_instance_name`.
    - Workflow sends sequentially with 2-second delay between messages.
    - Workflow calls `mark-sent` after successful Evolution send and `mark-failed` on Evolution failure.
  - Notes: exact node-level error handling and workflow JSON still need design during implementation. Validation comes from the spec Testing Plan.

- [ready] Add subscriptions web page and navigation
  - Spec: `specs/tenant-subscriptions.md`
  - Scope: create dedicated subscriptions route/page with dashboard and client navigation entry points.
  - Acceptance:
    - Tenant dashboard links to subscriptions page.
    - Client rows/details link to subscriptions page filtered by client.
    - Page is accessible to Tenant and Master with active tenant context.
    - Page supports filters by status, client, service, quick expiry range, and custom expiry range.
    - Cancelled subscriptions are hidden by default and visible under cancelled filter/category.
  - Notes: exact UX layout remains open; keep implementation consistent with Vue 3 plain JS conventions. Validation comes from the spec Testing Plan.

- [ready] Add web create/edit/renew/reactivate subscription flows
  - Spec: `specs/tenant-subscriptions.md`
  - Scope: implement subscription form and actions on dedicated web page.
  - Acceptance:
    - Create form includes client, service, filtered plan, streaming email, optional password, duration, and optional profile/PIN block.
    - Duration options include 1 month, 3 months, 6 months, 9 months, 1 year, and custom date selector.
    - PIN requires profile.
    - Editing service clears/requires compatible plan.
    - Renew extends from current `expires_at`.
    - Reactivate asks for new duration and recalculates dates.
  - Notes: no price/payment fields in v1. Validation comes from the spec Testing Plan.

- [ready] Add web credential masking and reminder settings UI
  - Spec: `specs/tenant-subscriptions.md`
  - Scope: implement masked credential display/reveal controls and tenant reminder settings UI.
  - Acceptance:
    - Password and PIN are masked by default.
    - Reveal icon calls reveal endpoint per row/detail.
    - Empty password displays “Sin contraseña” and no reveal button for password.
    - Tenant can configure timezone, reminder days, reminder time, and recipient mode.
    - Defaults show `UTC`, `[7, 3, 1]`, `09:00`, and tenant-only recipient.
  - Notes: do not cache revealed secrets longer than needed in UI state. Validation comes from the spec Testing Plan.

- [ready] Add Tenant WhatsApp subscription CRUD
  - Spec: `specs/tenant-subscriptions.md`
  - Scope: extend Tenant WhatsApp console with subscription list/create/detail/edit/cancel/renew/reactivate flows.
  - Acceptance:
    - Tenant can list subscriptions by status/category.
    - Tenant can create subscriptions through WhatsApp with same validations as web.
    - Sensitive credential create/edit flow requires double confirmation before save.
    - Detail view shows full credentials without extra confirmation.
    - Tenant can cancel, renew, and reactivate subscriptions through WhatsApp.
  - Notes: exact Spanish conversational copy remains open; keep separate from reminder workflow. Validation comes from the spec Testing Plan.

<!--
- [draft] Add concise title
  - Spec: `specs/draft-title.md`
  - Scope: one reviewable vertical slice.
  - Acceptance:
    - Observable, testable behavior.
  - Notes: risks/constraints/follow-ups. Validation comes from the spec Testing Plan.
-->
