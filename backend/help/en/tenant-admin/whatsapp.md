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
summary: Link your business phone and use TrackPal from chat.
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
  - release_id: tenant-admin-starter-1
    order: 4
    target: admin.settings.whatsapp
    conditional: false
    plans:
      - starter
    title: Connect WhatsApp
    content: |
      # Connect WhatsApp

      Link the business phone to use the private TrackPal Starter menu. When the status is **Connected**, you can continue with access-code search and Access control.
---

# WhatsApp

Link the business phone to manage TrackPal from a private menu and send notices.

## Link the phone

In **Settings > Profile**, confirm the business phone. Then open **WhatsApp**, choose a pairing code or QR code, and finish from **Linked devices** on your phone. Wait for **Connected**.

If the code expires, generate a new one. Use **Disconnect** only when you intend to end the link.

## Available menus

**TrackPal Starter** includes Profile, access-code search, Access control, Help, and Exit. **TrackPal Pro** also includes Clients, Catalog, and Subscriptions.

In the **TrackPal Pro** menu: `1` Clients, `2` Catalog, `3` My profile, `4` Subscriptions, `5` Access control, `6` Help, and `7` Search for an access code. Use `0` to exit or cancel; `8` and `9` appear when you can move forward or back.

## Private client menu

Type `menu` or `/menu` in your private administration chat while handling a contact. From there you can view or manage their account and open subscriptions. Only one client menu can stay active at a time; use `0` to close it.

If WhatsApp is connected but access-code search fails, check enabled platforms and the central mailbox first. Never share QR codes, pairing codes, or passwords with support.
