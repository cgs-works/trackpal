---
id: tenant-admin.activate-access-code-lookup
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: help
capabilities:
  - tenant_access_code_lookup
route: /admin/settings
help_targets:
  - admin.settings.code-services
title: Set up access-code search
summary: Prepare WhatsApp, platforms, and the mailbox in the right order.
search_tags:
  - activate access-code lookup
  - first code search
  - access-code setup
  - search prerequisites
  - code lookup recovery
synonyms:
  - enable code search
  - first access code
  - code search setup
order: 90
safe_navigation:
  route: /admin/settings
  settings_category: code-services
related_topics:
  - tenant-admin.code-services
  - tenant-admin.mailbox
  - tenant-admin.whatsapp
  - tenant-admin.access-control
tour:
  - release_id: tenant-admin-starter-1
    order: 5
    target: admin.settings.code-services
    conditional: false
    plans:
      - starter
    title: Prepare access-code search
    content: |
      # Prepare access-code search

      Choose at least one platform and connect the central mailbox. Then open **Search for an access code** in WhatsApp.

      Select **Learn more** for the complete setup.
---

# Set up access-code search

Search is ready after these three steps:

1. **Link WhatsApp** in Settings and wait for **Connected**.
2. **Choose at least one platform** under Enabled platforms.
3. **Connect and test the central mailbox** with Google, Microsoft, or IMAP.

Then open **Search for an access code** in WhatsApp: option `2` in **TrackPal Starter** or option `7` in **TrackPal Pro**. Choose the service, enter the subscription email, and confirm it.

## Understand the result

- **Pending:** TrackPal is still checking the mailbox; wait before repeating.
- **Found:** use the code or link soon.
- **Not found:** request a new code from the service and try again.
- **Duplicate:** wait for the displayed cooldown before another search.
- **Error or timeout:** check the mailbox and platform first.

Use `8` to move forward when shown, `9` to go back, and `0` to cancel. If the issue continues, share the service, visible status, and approximate time, never the code or email password.
