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
title: Business timezone
summary: Set the business time zone used for subscription dates, reminders, and expirations.
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
tour:
  - release_id: tenant-admin-pro-1
    order: 6
    target: admin.settings.timezone
    conditional: false
    plans:
      - pro
    title: Pro Settings and safe setup
    content: |
      # Settings keeps Pro operations connected

      Settings brings together language, timezone, Public API Key, enabled platforms, the central mailbox, access control, profile, password, and WhatsApp linking. Pro-only automation uses the business timezone and reminder settings.

      This step opens a safe informational category. The tour never saves settings, connects services, reveals keys, changes access, or opens a destructive confirmation.
---

# Business timezone

The business time zone applies to the whole account, not only to one browser. TrackPal uses it to interpret local subscription dates and schedule expiry reminders. This section appears when those tools are included in the current plan.

## Choose and save a timezone

Open Settings, choose Timezone, search by region or city, select the option that matches the business location, and save. The default is `UTC`, a universal time reference, until you choose the local region. Locale and timezone are separate settings: changing one does not translate the other or change subscription data.

Saving changes the time zone used for future calculations across the business account. Help only opens the Timezone category; it does not select, save, or silently convert a value. If the list is loading, wait for it. If the save fails, the previous timezone remains in effect and the visible error can be retried.

## What the timezone changes

- Reminder warning days use the business's local calendar date.
- The reminder time is interpreted as local time before TrackPal prepares a reminder.
- Subscription expiration cleanup uses the business's local end of day before moving an active subscription to Expired.
- WhatsApp subscription creation and reactivation use the business timezone when preparing the start date and confirmation.
- Dashboard and operational expiration information should be interpreted with the same local business calendar in mind.

The timezone does not create reminders, renew subscriptions, reactivate cancelled records, cancel a subscription, link WhatsApp, or reveal credentials. Use Subscriptions for manual actions and Reminder settings for opt-in and recipient choices.

## States, boundaries, and recovery

Choose a value from the available list and recheck the region if the business moves. TrackPal automatically follows the time rules for the selected region, including daylight-saving changes. A wrong timezone can make a warning day appear early or late without changing the stored expiry instant.

The setting applies to the active business. It does not change a client's device clock or the dates shown by the email provider; it only changes how TrackPal evaluates subscription dates and reminders for the business.

## Safe navigation and support boundary

The Help link opens Settings in the Timezone category without saving or opening a mutation dialog. Support can help verify the selected identifier and a visible scheduling or expiry error. Share the region, IANA value, and approximate time only; never share passwords, PINs, mailbox credentials, OAuth tokens, access codes, or WhatsApp pairing secrets.
