---
id: tenant-admin.help
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: help
capabilities:
  - tenant_settings
route: /admin/help
help_targets:
  - admin.help
title: Help Center
summary: Find the private manual and replay the optional orientation tour.
search_tags:
  - help
  - manual
  - orientation
  - replay tour
synonyms:
  - guide
  - instructions
  - walkthrough
order: 170
safe_navigation:
  route: /admin/help
  settings_category: null
related_topics:
  - tenant-admin.dashboard
  - tenant-admin.whatsapp
  - tenant-admin.activate-access-code-lookup
tour:
  - release_id: tenant-admin-starter-1
    order: 7
    target: admin.help
    conditional: false
    plans:
      - starter
    title: Help and replay
    content: |
      # Help and replay

      Help contains the manual topics authorized for your Starter plan, including WhatsApp, enabled platforms, the central mailbox, and access control. Use the search box to find a topic without leaving your current data behind.

      You can replay this orientation from Help at any time. Manual links only open safe screens; they never submit forms, reveal credentials, or perform product actions.
  - release_id: tenant-admin-pro-1
    order: 7
    target: admin.help
    conditional: false
    plans:
      - pro
    title: WhatsApp, Help, and replay
    content: |
      # Finish with Help

      Pro WhatsApp includes Clients, Catalog, Profile, Subscriptions, Access Control, Help, and access-code lookup. Help contains the authorized manual and is where you can replay this orientation.

      Help navigation is read-only. It never submits forms, reveals credentials, changes data, or performs a WhatsApp action.
---

# Help Center

The Help Center shows guidance for the tools included in your current plan and in your selected language.

## Find a topic

Search for an action, state, error, or prerequisite. Starter Help includes Dashboard, Settings, WhatsApp, enabled code platforms, the central lookup mailbox, access control, profile, password, and cross-module access-code guidance. Pro-only Clients, Catalog, Subscriptions, reminder, timezone, and Public API administration are not shown to Starter users.

## Replay the orientation

The optional Starter orientation explains the operational map in about 2 to 3 minutes. Select Replay orientation tour when you want to see it again. Closing the tour requires confirmation before the skipped state is saved.

Help navigation is read-only. Its links open authorized modules or Settings categories without saving forms, changing status, connecting services, revealing secrets, or starting a search.
