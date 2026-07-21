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
title: Help
summary: Find answers and replay the orientation whenever you need it.
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
    title: Help is always here
    content: |
      # Help is always here

      Search for any TrackPal Starter task or problem. You can also replay this orientation whenever you need it.
  - release_id: tenant-admin-pro-1
    order: 7
    target: admin.help
    conditional: false
    plans:
      - pro
    title: Help is always here
    content: |
      # Help is always here

      Find instructions for any TrackPal Pro section. You can also replay this orientation whenever you need it.
---

# Help

Search for a task, screen, or problem. TrackPal shows only the topics available in your current plan.

To take another tour of the application, select **Replay orientation tour**. You can close it and start again later from this page.
