---
id: tenant-admin.whatsapp
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: settings
capabilities:
  - tenant_whatsapp
route: /admin/settings
help_targets:
  - admin.settings.whatsapp
title: WhatsApp
summary: Link the business WhatsApp instance and understand the Tenant Admin console.
search_tags:
  - WhatsApp
  - pairing code
  - QR code
  - linked devices
  - disconnect
synonyms:
  - WhatsApp connection
  - link phone
  - bot
order: 30
safe_navigation:
  route: /admin/settings
  settings_category: whatsapp-link
related_topics:
  - tenant-admin.dashboard
  - tenant-admin.profile
  - tenant-admin.language
---

# WhatsApp

WhatsApp connects the business phone to TrackPal so the Tenant Admin bot can receive console messages and send replies.

## Channel, prerequisites, and actions

- **Channels:** Web for setup; WhatsApp for the conversational console after linking.
- **Prerequisites:** Be a Tenant Admin, open Settings, and configure a phone in Profile. Keep the phone with WhatsApp available while pairing. Access-code lookup also needs enabled platforms and a central mailbox.
- **Actions:** Open WhatsApp in Settings, choose Pairing Code or QR Code, complete linking in WhatsApp under Linked Devices, and wait for Connected. Use the visible disconnect action only when you intentionally want to end the link.

## Results and states

Connected means TrackPal can use the linked instance for the Tenant Admin console and notifications. Connecting means pairing is still in progress. Disconnected or missing phone means the console is not ready. A pairing code expires and a QR code may need refreshing. A successful link shows the instance status; a failed or timed-out attempt leaves the previous connection unchanged and can be retried.

## Web and WhatsApp actions

On Web, Settings is the safe place to pair, refresh a QR code, or review status. In WhatsApp, follow the plan menu shown by the bot. Starter exposes Profile, access-code search, Access Control, Help, and Exit. Pro also exposes Clients, Catalog, and Subscriptions. Use 0 to exit; follow the current menu for navigation and do not send credentials to the bot.

## Limits, consequences, and recovery

Only one configured business instance is used for this connection. Disconnecting ends the linked session and pauses WhatsApp actions until the phone is linked again; it does not delete clients, catalog entries, or subscriptions. If pairing expires, generate a new code or refresh the QR. If the phone is not configured, return to Profile. If a WhatsApp session times out, start it again from the menu. Do not repeatedly disconnect a healthy instance to fix an access-code lookup problem; check platforms and mailbox first.

## Support boundary

Support can help with a persistent pairing, status, or session error. Share the instance status and approximate time, never a pairing code, QR image, token, password, or mailbox credential.
