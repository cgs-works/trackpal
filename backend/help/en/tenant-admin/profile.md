---
id: tenant-admin.profile
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.profile
title: Business profile
summary: Keep your business name, email, and phone up to date.
search_tags:
  - profile
  - name
  - email
  - phone
  - WhatsApp phone
synonyms:
  - account details
  - business information
order: 40
safe_navigation:
  route: /admin/settings
  settings_category: my-account
related_topics:
  - tenant-admin.dashboard
  - tenant-admin.language
  - tenant-admin.whatsapp
tour:
  - release_id: tenant-admin-starter-1
    order: 3
    target: admin.settings.profile
    conditional: false
    plans:
      - starter
    title: Set up your business
    content: |
      # Set up your business

      Keep the business name and phone current in Profile. Settings is also where you change the language and your password.
---

# Business profile

This is where you save the name, email, and phone TrackPal uses to identify your business.

Open **Settings > My Account > Profile**, update the fields you need, and select **Save profile**. The phone should belong to the business and follow the format shown because it can also be used when preparing WhatsApp.

If you see an error, correct the highlighted field and save again. Reloading before you save can discard your changes.
