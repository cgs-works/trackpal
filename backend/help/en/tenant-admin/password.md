---
id: tenant-admin.password
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
  - admin.settings.password
title: Change your password
summary: Update the password for the account you use to manage TrackPal.
search_tags:
  - password
  - security
  - sign in
  - account security
synonyms:
  - reset password
  - credentials
order: 50
safe_navigation:
  route: /admin/settings
  settings_category: password
related_topics:
  - tenant-admin.profile
  - tenant-admin.language
---

# Change your password

Open **Settings > Password**. Enter your current password, create a new one, confirm it, and save.

The change affects only your signed-in account. It does not change other administrators, clients, WhatsApp, or the central mailbox.

If TrackPal rejects the change, review the form message. Your current password remains valid until the update succeeds. Never send a password to support.
