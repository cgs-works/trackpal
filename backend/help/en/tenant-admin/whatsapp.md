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
tour:
  release_id: tenant-admin-tracer-1
  order: 3
  target: admin.settings.whatsapp
  conditional: false
---

# WhatsApp

WhatsApp connects the business phone to TrackPal so the Tenant Admin bot can receive console messages and send replies.

## Channel, prerequisites, and actions

- **Channels:** Web for setup; WhatsApp for the conversational console after linking.
- **Prerequisites:** Be a Tenant Admin, open Settings, and configure a phone in Profile. Keep the phone with WhatsApp available while pairing. Access-code lookup also needs enabled platforms and a central mailbox.
- **Actions:** Open WhatsApp in Settings, choose Pairing Code or QR Code, complete linking in WhatsApp under Linked Devices, and wait for Connected. Use the visible disconnect action only when you intentionally want to end the link.

## Results and states

Connected means TrackPal can use the linked instance for the Tenant Admin console and notifications. Connecting or pending means pairing is still in progress. Disconnected or missing phone means the console is not ready. If WhatsApp revokes the linked device, the instance returns to a disconnected state and must be paired again. A pairing code expires and a QR code may need refreshing. A successful link shows the instance status; a failed or timed-out attempt leaves the previous connection unchanged and can be retried.

## Web and WhatsApp actions

On Web, Settings is the safe place to pair, refresh a QR code, or review status. In WhatsApp, follow the plan menu shown by the bot. Starter exposes Profile, access-code search, Access Control, Help, and Exit. Pro also exposes Clients, Catalog, and Subscriptions. Use `0` to exit or cancel. The current prompt labels `8` and `9` for page navigation or returning to the previous screen; follow those labels and do not send credentials to the bot.

## Pro menu, validation, and confirmations

The Pro main menu is `1` Clients, `2` Catalog, `3` My Profile, `4` Subscriptions, `5` Access Control, `6` Help, and `7` Find Access Code. Starter has a smaller menu and cannot open the Pro modules. The main menu uses `0` to exit. Inside a flow, `0` cancels, `9` goes back, and `8` advances only when the current message displays Next.

Each Pro flow validates selections and values before changing data. Invalid numbers, empty names, duplicate values, invalid phones, short passwords, and unavailable records show a recoverable validation message and keep the flow at the current step. Destructive Client or Catalog actions show a summary or impact preview and require `CONFIRM` or `CONFIRMAR`; any other response re-prompts and `0` cancels. A session timeout closes the flow without applying a partial mutation.

## Pro Client Context Shortcut boundaries

A Pro Tenant Admin can use `menu` or `/menu` from the private admin chat when the message targets a remote contact. TrackPal replies to the admin's private chat; the remote contact cannot see or operate the administrative menu. The shortcut can show client details, create or edit a client, activate or deactivate access, delete only an inactive client, and open that client's subscriptions. It does not expose the admin menu to the contact, edit a phone from the shortcut, reveal credentials automatically, or let the contact perform administrative actions.

Only one Client Context Shortcut may be active for an admin at a time. Send `0` in the private admin chat to close it before starting another. Do not send arbitrary messages to a remote contact expecting a shortcut: only `menu` or `/menu` starts it, and an already open context rejects collisions safely. The shortcut's block or unblock notifications to the contact are generic; the admin receives the management confirmation privately.

## Limits, consequences, and recovery

Only one configured business instance is used for this connection. Disconnecting ends the linked session and pauses WhatsApp actions until the phone is linked again; it does not delete clients, catalog entries, or subscriptions. If pairing expires, generate a new code or refresh the QR. If the phone is not configured, return to Profile. If a WhatsApp session times out, start it again from the menu. Do not repeatedly disconnect a healthy instance to fix an access-code lookup problem; check platforms and mailbox first.

## Support boundary

Support can help with a persistent pairing, status, session, validation, or Client Context Shortcut error. Share the instance status and approximate time, never a pairing code, QR image, token, password, mailbox credential, client password, or subscription credential.
