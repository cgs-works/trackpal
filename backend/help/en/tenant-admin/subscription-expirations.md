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
title: Manage expirations
summary: Combine dates, reminders, and lifecycle actions to keep subscriptions current.
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
    settings_category: my-account
    tab: regional
  - route: /admin/settings
    settings_category: reminders
related_topics:
  - tenant-admin.subscriptions
  - tenant-admin.reminders
  - tenant-admin.timezone
---

# Manage expirations

In **TrackPal Pro**, three things work together: the subscription date, the business timezone, and WhatsApp reminders.

## Before expiration

Confirm the timezone, enable reminders if you want them, and check that each subscription has the correct date and recipient phone.

When a subscription is about to expire, use **Renew** to extend it. If it already expired or was cancelled, use **Renew** or **Reactivate** when available. **Cancel** ends access before the planned date.

In WhatsApp, open **Subscriptions** from the **TrackPal Pro** menu. Visible actions use `1` Edit, `2` Cancel, `3` Renew, and `4` Reactivate; `8` moves forward, `9` goes back, and `0` cancels.

## Automatic changes

At the end of the local day, a past-due subscription becomes **Expired**. After 7 days it can become **Cancelled**, and after more than 30 days cancelled it is removed. Reminder automation is separate from these changes.

If a date looks wrong, check the timezone first. If a reminder is missing, check the subscription, recipients, and WhatsApp connection.
