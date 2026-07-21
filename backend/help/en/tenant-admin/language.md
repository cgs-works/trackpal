---
id: tenant-admin.language
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
  - admin.settings.language
title: Language
summary: Change the language used by TrackPal for your business workspace.
search_tags:
  - language
  - locale
  - Spanish
  - English
synonyms:
  - idioma
  - translation
order: 20
safe_navigation:
  route: /admin/settings
  settings_category: locale
related_topics:
  - tenant-admin.dashboard
  - tenant-admin.profile
  - tenant-admin.password
---

# Language

Language controls the TrackPal interface and the private Help content for your active business workspace.

## Channel, prerequisites, and actions

- **Channel:** Web. WhatsApp replies follow the active locale but language is changed here.
- **Prerequisites:** Sign in as a Tenant Admin and open Settings. The Language category is available on Starter and Pro.
- **Actions:** Choose Language, select the available locale, and save the change. The page reloads the catalog after a successful save.

## Results and states

The navigation, Settings labels, and Help topics use the selected language after the update. While saving, the control is busy. The current selection remains visible when the page loads. If the locale cannot be loaded or saved, the existing language remains active and an error is shown.

## Limits, consequences, and recovery

Language is a Tenant setting, so it applies to the business rather than only one browser tab or one administrator. It does not translate messages from external providers and does not change credentials, subscriptions, or WhatsApp linking. If the selection does not persist, reload the page, confirm the request can reach TrackPal, and try again. Do not clear a working session or change mailbox credentials to recover a language error.

## Support boundary

Support can help when the language selector or catalog remains unavailable after retrying. Include the selected locale and the visible error, but never include a password, pairing code, access token, or mailbox secret.
