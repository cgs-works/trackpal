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
title: Subscription reminder settings
summary: Opt in to expiry reminders and choose when, where, and how they are prepared.
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
    title: Pro reminders and timezone
    content: |
      # New Pro automation

      Your upgrade adds optional subscription reminders and the Pro timezone controls they use. Review the settings and the expiration guide before enabling automation.

      The tour only opens the safe settings view. It never toggles reminders, saves warning days, sends messages, or changes subscription lifecycle state.
---

# Subscription reminder settings

Reminder settings control optional WhatsApp notifications for subscriptions that are close to expiring. You choose whether to turn this feature on (opt in), and it is available only when reminders are included in the current plan. Turning it on does not create, renew, cancel, or reactivate a subscription, and Help never saves the form for you.

## Opt in and prerequisites

Open Settings, choose Subscription reminder settings, and turn on reminders when the business is ready to use automatic expiry notifications. Reminders are off by default. Your current plan must include reminders, the subscription must be active, and each recipient needs a usable WhatsApp phone number. Changing to a plan without reminders stops new notifications but does not delete saved subscription data.

When reminders are disabled, TrackPal does not prepare or send new reminder messages for the business. Saving the settings does not send a message immediately. The separate Subscriptions module remains the place for manual lifecycle actions.

## Warning days and local time

Choose one or more warning days before expiry. The default days are 7, 3, and 1; you can remove a default day or add another positive number. At least one warning day is required while reminders are enabled.

Set the reminder time using the business's local time. TrackPal can prepare that day's reminder once the local clock reaches the selected time. The time zone appears here for reference and can be changed in the separate Timezone section.

A warning day is calculated from the business's local calendar date. TrackPal handles this schedule automatically, so the selected time keeps the same meaning for the business.

## Recipients and custom messages

Choose who should receive an eligible reminder:

- **Administrators only:** send to the business WhatsApp phone.
- **Client only:** send to the Client's WhatsApp phone.
- **Both:** prepare one reminder for each available recipient.

The form provides separate custom messages for administrators and clients. Words between double braces, such as `{{client_name}}`, `{{service_name}}`, `{{days}}`, `{{streaming_email}}`, and `{{expires_at}}`, are details TrackPal fills in automatically; do not change or remove them. Use the preview to check the wording, and never include passwords or access codes.

If the selected recipient has no usable phone, that recipient is skipped. A failed save leaves the previous configuration in place. Correct the visible validation error for an empty warning-day list or invalid `HH:MM` time and save again.

## Automation and recovery

TrackPal checks approximately every 30 minutes for active subscriptions that need a reminder. It uses the selected warning days, local time, recipients, and duplicate protection, then reports whether WhatsApp delivered the message. This automation does not change subscription status or dates.

A reminder can be pending, sent, or failed after retries. If no reminder appears, check the Pro plan, toggle, warning day, local time, Timezone setting, active status, expiry date, WhatsApp link, and recipient phone. Do not disconnect WhatsApp or reveal credentials as a first response. The expiration guide connects these checks with manual renewal, reactivation, cancellation, and automatic transitions.

## Safe navigation and support boundary

The Help link opens Settings in the reminders category without saving, toggling, sending, or changing a setting. Support can inspect a persistent scheduling or delivery error using the visible status and approximate time. Never share a Client password, streaming password, profile PIN, mailbox credential, OAuth token, access code, or WhatsApp pairing secret.
