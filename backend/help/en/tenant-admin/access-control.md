---
id: tenant-admin.access-control
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: settings
capabilities:
  - tenant_access_control
route: /admin/settings
help_targets:
  - admin.settings.access-control
title: WhatsApp access control
summary: Choose which people or numbers can use TrackPal in WhatsApp.
search_tags:
  - access control
  - blocked phone
  - blocked identity
  - unblock
  - WhatsApp block
synonyms:
  - bot blocking
  - blocked contacts
  - deny access
order: 80
safe_navigation:
  route: /admin/settings
  settings_category: access-control
related_topics:
  - tenant-admin.whatsapp
  - tenant-admin.activate-access-code-lookup
  - tenant-admin.profile
tour:
  - release_id: tenant-admin-starter-1
    order: 6
    target: admin.settings.access-control
    conditional: false
    plans:
      - starter
    title: Control WhatsApp access
    content: |
      # Control WhatsApp access

      Review blocked people, search for a phone, and restore access when needed. An empty list means nobody is blocked.
---

# WhatsApp access control

Use this list to block someone from the TrackPal WhatsApp menu or restore their access.

On the Web, open **Settings > Access control** to search for a phone, block it, or remove an existing block. In WhatsApp, open **Access control** from the **TrackPal Starter** or **TrackPal Pro** menu.

A block prevents bot access and access-code requests, but it does not delete the client or their subscriptions. An empty list means nobody is blocked. If a search finds nothing, check the digits or clear the filter.

To restore access, unblock the exact entry shown on screen. If the identity does not show a phone you recognize, ask for help before choosing another entry.
