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
summary: Review, search, block, and unblock WhatsApp identities for the business.
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
    title: Access control
    content: |
      # Access control

      Settings shows the people and numbers blocked from the business WhatsApp account. An empty list is a valid state. The tour only highlights the first available action and explains the boundary; it never blocks, unblocks, searches, or opens a confirmation dialog.
---

# WhatsApp access control

WhatsApp access control is the list administrators use to prevent specific people or numbers from using the business's WhatsApp menu. It protects the WhatsApp console and access-code flow; it is separate from a Client's portal account status.

## Channel, prerequisites, and actions

- **Channels:** Web for the full list and phone search; WhatsApp for the Access Control option in the administrator menu.
- **Prerequisites:** Sign in to the business administrator account. You need the phone number or WhatsApp entry you want to block. Blocking is available on Starter and Pro.
- **Actions:** On Web, open Settings, choose Access control, search the list by phone digits, block a phone, or unblock an existing entry. In WhatsApp, Starter opens Access Control with `3` and Pro with `5`; choose `1` to list blocked identities or `2` to block a phone.

## Results and states

- **Loading:** TrackPal is retrieving blocked identities. Wait before deciding that the list is empty.
- **Empty:** No identity is blocked, so Web shows the empty state and WhatsApp can show an empty list.
- **Blocked:** The identity is denied access to the WhatsApp bot, including access-code requests and console actions.
- **Unblocked:** Removing the entry allows the identity to use WhatsApp again when its other requirements are met.
- **Duplicate:** Trying to block an identity that is already blocked leaves the existing entry unchanged.
- **No search results:** A phone search can return no matching block; clear the search or check the digits.
- **Error:** A failed list, block, or unblock request leaves the current state unchanged. Retry and contact support if it persists.

## Web and WhatsApp actions

The Web list supports phone search without changing the stored blocks. In WhatsApp, use `9` to return to the main menu and `0` to cancel the current action. The bot block affects WhatsApp identity access; it does not log a Client out of the portal or change the Client's active/inactive account status.

## Limits, consequences, and recovery

Blocking prevents the identity from reaching the business's WhatsApp console, requesting access codes, viewing WhatsApp profile information, or checking WhatsApp subscriptions. It does not delete the Client, deactivate the Client portal account, or remove subscriptions. Unblock the exact identity from Web or the WhatsApp list when access should be restored. If TrackPal shows an unfamiliar WhatsApp identifier instead of a phone number, use the entry shown on screen and ask support for help rather than guessing a number.

## Support boundary

Support can help identify a persistent block or identity mismatch. Share the visible phone or identity and the approximate time; never share a password, access code, pairing code, QR image, or mailbox credential.
