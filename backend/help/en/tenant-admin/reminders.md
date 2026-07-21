---
id: tenant-admin.reminders
audience: tenant_admin
plans:
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_subscriptions
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.reminders
title: Subscription reminders
summary: Send a WhatsApp notice before a subscription reaches its expiration date.
search_tags:
  - reminders
  - subscription reminders
  - warning days
  - reminder time
  - recipients
  - custom message
  - expiring subscriptions
synonyms:
  - expiry alerts
  - renewal notifications
  - expiration warnings
order: 140
safe_navigation:
  route: /admin/settings
  settings_category: reminders
related_topics:
  - tenant-admin.subscriptions
  - tenant-admin.timezone
  - tenant-admin.subscription-expirations
tour:
  - release_id: tenant-admin-pro-upgrade-1
    order: 4
    target: admin.settings.reminders
    conditional: false
    plans:
      - pro
    title: Reminders in TrackPal Pro
    content: |
      # Prepare your reminders

      Choose the warning days, local time, recipients, and the message they will receive in WhatsApp.
---

# Subscription reminders

**TrackPal Pro** can send automatic notices before a subscription expires. This feature starts turned off.

## Set it up

Open **Settings > Reminders**, turn this feature on, and choose:

- the warning days before expiration, such as 7, 3, and 1;
- the local time for delivery;
- the recipients: administrators, the client, or both;
- the custom message for each recipient.

TrackPal fills values such as `{{client_name}}`, `{{service_name}}`, `{{days}}`, and `{{expires_at}}`. Keep those labels and use the preview to review the result.

Automation checks approximately every 30 minutes using the business timezone. If a reminder is missing, check that the subscription is active, the date is correct, WhatsApp is connected, and the recipient has a phone.

Saving reminder settings does not send an immediate message or change a subscription status. Availability depends on the current plan.
