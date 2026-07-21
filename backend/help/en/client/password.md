---
id: client.password
audience: client
plans:
  - pro
channels:
  - web
module: password
capabilities:
  - client_password
route: /client/profile
help_targets:
  - client.password
title: Password Change on Web
summary: Change your Client sign-in password from the Web Profile page.
search_tags:
  - password
  - security
  - sign in
  - credentials
synonyms:
  - change login
  - reset password
order: 40
safe_navigation:
  route: /client/profile
  settings_category: null
related_topics:
  - client.profile
  - client.whatsapp
---

# Password Change on Web

Client password changes are available only on the Web Profile page.

## Channel, prerequisites, and actions

- **Channel:** Web only. The WhatsApp Client console never changes a password.
- **Prerequisites:** Sign in to an active Pro Client account, open Profile, and know the current password. The new password must be at least eight characters and the confirmation must match.
- **Actions:** Enter the current password, enter and confirm the new password, then choose Update Password. TrackPal validates the fields before applying the change.

## Results and recovery

A successful update confirms that the password changed and clears the form. Missing fields, a short password, mismatched confirmation, or an incorrect current password leave the existing password unchanged. If the request fails, use Retry after checking the visible error. Do not try to change the password through WhatsApp.

## Consequences and security

The change affects your Client Web sign-in account. It does not edit your profile, subscriptions, provider data, WhatsApp session, or service credentials. Choose a unique password and do not share it with the provider or support.

## Support boundary

Support can explain a visible validation error but cannot view, reset, or accept your password. If you cannot verify the current password, contact the provider through their supported channel.
