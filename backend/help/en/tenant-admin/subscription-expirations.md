---
id: tenant-admin.subscription-expirations
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: help
capabilities:
  - tenant_subscriptions
  - tenant_settings
route: /admin/subscriptions
help_targets: []
title: Manage subscription expirations
summary: Connect local dates, reminders, manual lifecycle actions, and automatic subscription transitions.
search_tags:
  - subscription expirations
  - expiration management
  - expiring subscriptions
  - renewal workflow
  - automatic expiration
  - warning days
synonyms:
  - expiry management
  - renewal planning
  - subscription end dates
order: 160
safe_navigation:
  route: /admin/subscriptions
  settings_category: null
safe_links:
  - route: /admin/settings
    settings_category: timezone
  - route: /admin/settings
    settings_category: reminders
related_topics:
  - tenant-admin.subscriptions
  - tenant-admin.reminders
  - tenant-admin.timezone
---

# Manage subscription expirations

Expiration management joins three Pro surfaces: Subscriptions for manual action, Timezone for the Tenant-local calendar, and Subscription reminder settings for optional WhatsApp automation. The guide is informational. Its links open safe screens only; Help never creates, edits, cancels, renews, reactivates, reveals, or deletes a subscription.

## Prepare the operational calendar

1. Open Timezone and confirm the business IANA timezone. TrackPal uses it for local dates, reminder thresholds, and the end-of-day boundary used by cleanup.
2. Open Subscription reminder settings and decide whether to opt in. If enabled, select warning days such as 7, 3, and 1, set the local reminder time, choose Tenant, Client, or Both recipients, and review custom-message placeholders.
3. Open Subscriptions and check the Client, service, plan, status, start date, expiry date, and stored email. The Tenant must be Pro for subscription data and automation to be operational.

The timezone and reminder links are safe navigation: they select a Settings category but do not save a form or send a message. A Help link into Subscriptions does not open a credential reveal dialog.

## Manual expiration response on Web or WhatsApp

For an active subscription that is approaching expiry, review the dates and choose Renew. Select a supported duration or custom date, read the proposed new expiry, and confirm. If the service relationship or credentials changed, use Edit separately and save only after checking the form summary.

If a subscription is Expired, renew or reactivate it according to the available action and the business decision. Reactivation starts it again with new dates; renewal extends from the current expiry. If access must stop before the expiry date, Cancel changes the status to Cancelled without immediately deleting the row. Cancel and lifecycle actions require the visible Web confirmation or `CONFIRM`/`CONFIRMAR` in WhatsApp.

In WhatsApp, use Pro menu `4`, choose the status filter, select the subscription, then use `1` Edit, `2` Cancel, `3` Renew, or `4` Reactivate when shown. Use `8` Next, `9` Back, and `0` Cancel according to the current prompt. Never paste a secret into a Help link or a confirmation message.

## Automated transitions and reminders

When reminders are enabled, the backend checks only active Pro subscriptions. It calculates days until expiry from the Tenant-local date, waits until the local reminder time, prepares one payload per eligible recipient, and deduplicates the same subscription, warning day, recipient, and local date. n8n polls about every 30 minutes only to transport pending payloads and report success or failure.

Cleanup is separate from reminder delivery. It uses the Tenant-local end of day when deciding whether an already-passed expiry should transition. When a cleanup run sees an eligible active subscription, it becomes Expired and an event is recorded. An Expired subscription that remains expired for at least 7 days is automatically moved to Cancelled. A Cancelled subscription older than 30 days is deleted by cleanup. These transitions are automation, not actions performed by Help or by an n8n reminder message.

Disabling reminders stops new reminder payloads and logs, but it does not pause or delete subscriptions. Downgrading a Tenant to Starter preserves Pro rows and settings while subscription, reminder, and cleanup jobs ignore that Tenant. Upgrading back to Pro makes the preserved data available again subject to its current status and dates.

## Expiry states and recovery

- No reminder: check Pro access, the toggle, warning days, local time, timezone, active status, recipient phone, and WhatsApp readiness.
- Unexpected date: confirm the IANA timezone and distinguish a stored expiry instant from its local calendar representation.
- Expired but still needed: review the record and use Renew or Reactivate; do not create a duplicate without checking the existing Client, service, and email.
- Cancelled by automation: confirm whether the seven-day expired transition was expected and whether the record is still within the supported manual recovery path.
- Failed delivery: inspect the pending or failed status and visible error; do not repeatedly toggle settings or reveal credentials as a workaround.

## Security and support boundary

Reveal credentials is a separate sensitive Web action and is never opened by this guide. Streaming passwords, profile PINs, Client passwords, mailbox credentials, access codes, API keys, and WhatsApp pairing secrets must not be included in Help searches or support requests. Support can use non-sensitive IDs, statuses, dates, plan, timezone, recipient mode, and approximate times to investigate a persistent issue.
