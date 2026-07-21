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

Reminder settings control the optional WhatsApp notifications prepared for subscriptions that are approaching their expiry. The reminders are an opt-in feature: they remain off until a Pro Tenant Admin enables them. This is a Pro Tenant setting. It does not create, renew, cancel, or reactivate a subscription, and Help never saves the form for you.

## Opt in and prerequisites

Open Settings, choose Subscription reminder settings, and turn on the reminders toggle when the Tenant is ready to use automated expiry notifications. Reminders are off by default. The Tenant must be Pro, the subscription must be active, and recipients need usable WhatsApp phone numbers. Starter Tenant Admins cannot see, retrieve, or search this topic; preserved subscription data is not changed by reminder automation while the Tenant is Starter.

When reminders are disabled, no pending reminder payloads or reminder logs are generated for the Tenant. Saving the settings does not send a message immediately. The separate Subscriptions module remains the place for manual lifecycle actions.

## Warning days and local time

Choose one or more warning days before expiry. The default days are 7, 3, and 1; you can remove a default day or add another positive number. At least one warning day is required while reminders are enabled.

Set the reminder time in the Tenant's local time. The time is a threshold: the backend can prepare that day's reminder once the local clock reaches the configured time. The timezone is shown here for reference and is edited in the separate Timezone category. Use the Timezone topic before changing this value if the business operates in another IANA timezone.

A warning day is calculated from the Tenant-local calendar date, not by treating every day as a fixed UTC interval. The backend owns the local-time check, so the n8n transport schedule does not change the meaning of the configured time.

## Recipients and custom messages

Choose who should receive an eligible reminder:

- **Tenant only:** send to the business WhatsApp phone.
- **Client only:** send to the Client's WhatsApp phone.
- **Both:** prepare one reminder for each available recipient.

The settings form also provides separate Tenant and Client custom-message fields. Keep the supported placeholders such as `{{client_name}}`, `{{service_name}}`, `{{days}}`, `{{streaming_email}}`, and `{{expires_at}}` intact when editing them. The preview replaces sample values so you can check the wording before saving; do not put passwords, mailbox secrets, or access codes in a message.

If the selected recipient has no usable phone, that recipient is skipped. A failed save leaves the previous configuration in place. Correct the visible validation error for an empty warning-day list or invalid `HH:MM` time and save again.

## Automation and recovery

The backend evaluates Pro tenants, active subscriptions, local warning days, local time, recipients, and duplicate protection. A separate n8n workflow polls approximately every 30 minutes, transports pending payloads to WhatsApp, and reports delivery success or failure. It does not decide the Tenant timezone or perform subscription lifecycle changes.

A reminder can be pending, sent, or failed after retries. If no reminder appears, check the Pro plan, toggle, warning day, local time, Timezone setting, active status, expiry date, WhatsApp link, and recipient phone. Do not disconnect WhatsApp or reveal credentials as a first response. The expiration guide connects these checks with manual renewal, reactivation, cancellation, and automatic transitions.

## Safe navigation and support boundary

The Help link opens Settings in the reminders category without saving, toggling, sending, or changing a setting. Support can inspect a persistent scheduling or delivery error using the visible status and approximate time. Never share a Client password, streaming password, profile PIN, mailbox credential, OAuth token, access code, or WhatsApp pairing secret.
