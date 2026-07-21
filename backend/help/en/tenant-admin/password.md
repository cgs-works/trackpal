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
title: Password
summary: Change your sign-in password without changing the business profile.
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

# Password

Use Password in Settings to change the password for the account you are currently using.

## Channel, prerequisites, and actions

- **Channel:** Web. Password changes are not available from the administrator WhatsApp console.
- **Prerequisites:** Sign in with the account whose password you want to change and open Settings, then Password. You need the current password.
- **Actions:** Enter the current password, enter a new password, confirm it, and save. TrackPal validates the new value before sending it.

## Results and states

A successful change confirms the update. While saving, the form is busy. Missing, incorrect, or mismatched values show a validation error and do not change the password. If the request fails, the existing password remains valid and the form can be retried.

## Limits, consequences, and recovery

Changing the password affects only the account you are currently using, not other administrators, clients, mailbox passwords, or WhatsApp sessions. Use a new password that meets the minimum shown by the form and do not reuse a shared mailbox password. If you forget the current password or repeated retries fail, stop guessing and use the supported account recovery or contact the workspace owner; do not reveal the password to support.

## Support boundary

Support can explain the visible validation or connection error, but cannot view, recover, or accept a password. Never put current or new passwords in a ticket, chat, screenshot, or Help search.
