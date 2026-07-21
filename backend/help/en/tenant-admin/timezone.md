---
id: tenant-admin.timezone
audience: tenant_admin
plans:
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_settings
  - tenant_subscriptions
route: /admin/settings
help_targets:
  - admin.settings.timezone
title: Tenant timezone
summary: Set the IANA timezone used for local subscription dates, reminders, and expiration automation.
search_tags:
  - timezone
  - time zone
  - IANA timezone
  - local time
  - local date
  - daylight saving
synonyms:
  - business time zone
  - regional time
  - clock settings
order: 150
safe_navigation:
  route: /admin/settings
  settings_category: timezone
related_topics:
  - tenant-admin.reminders
  - tenant-admin.subscriptions
  - tenant-admin.subscription-expirations
---

# Tenant timezone

The Tenant timezone is a business setting, not a browser-only preference. TrackPal uses the selected IANA timezone to interpret local subscription dates and to schedule expiry reminders. It is available to Pro Tenant Admins; Starter Tenant Admins cannot see, retrieve, or search this topic. Master Support Context can inspect preserved Pro settings without changing the Tenant's plan.

## Choose and save a timezone

Open Settings, choose Timezone, search the timezone picker by region or identifier, select the matching IANA value, and save. The default is `UTC`. The picker displays a human-readable label and its identifier so you can confirm the business location before saving. Locale and timezone are separate settings: changing one does not translate the other or change subscription data.

Saving changes the Tenant-wide value used by future calculations. Help only opens the Timezone category; it does not select, save, or silently convert a value. If the list is loading, wait for it. If the save fails, the previous timezone remains in effect and the visible error can be retried.

## What the timezone changes

- Reminder warning days use the Tenant-local calendar date.
- The reminder time is interpreted as local time and is checked by the backend before a pending reminder is created.
- Subscription expiration cleanup uses the Tenant-local end of day before moving an active subscription to Expired.
- WhatsApp subscription creation and reactivation use the Tenant timezone when preparing the start date and confirmation.
- Dashboard and operational expiration information should be interpreted with the same Tenant-local calendar in mind.

The timezone does not create reminders, renew subscriptions, reactivate cancelled records, cancel a subscription, link WhatsApp, or reveal credentials. Use Subscriptions for manual actions and Reminder settings for opt-in and recipient choices.

## States, boundaries, and recovery

A missing or invalid value is handled defensively by backend services, but the supported picker values are valid IANA identifiers and should be preferred. Recheck the region after daylight-saving changes or when the business moves. A wrong timezone can make a warning day appear early or late without changing the stored expiry instant.

The setting applies to the active Tenant and should be confirmed after switching Tenant context. It does not change the Client's personal device clock, the mailbox provider's timestamps, or the absolute stored `starts_at` and `expires_at` instants. It changes how TrackPal evaluates those instants against the Tenant's local date.

## Safe navigation and support boundary

The Help link opens Settings in the Timezone category without saving or opening a mutation dialog. Support can help verify the selected identifier and a visible scheduling or expiry error. Share the region, IANA value, and approximate time only; never share passwords, PINs, mailbox credentials, OAuth tokens, access codes, or WhatsApp pairing secrets.
