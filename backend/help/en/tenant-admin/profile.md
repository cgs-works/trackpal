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
title: Profile
summary: Update the business identity and contact information used by TrackPal.
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
  settings_category: profile
related_topics:
  - tenant-admin.dashboard
  - tenant-admin.language
  - tenant-admin.whatsapp
---

# Profile

Profile stores the business identity and contact details that Tenant Admins use to configure TrackPal.

## Channel, prerequisites, and actions

- **Channel:** Web. Profile editing is not available as a WhatsApp action.
- **Prerequisites:** Sign in as a Tenant Admin and open Settings, then Profile.
- **Actions:** Review the business name, email, and phone fields; change the permitted values; select Save Profile.

## Results and states

A successful save shows a confirmation and the updated values remain in the form. Loading means TrackPal is retrieving the current profile. Validation errors identify a value that must be corrected. A failed save leaves the previous profile on the server and keeps the local form available for recovery.

## Limits, consequences, and recovery

Profile values identify the Tenant and may supply the WhatsApp phone prerequisite. Saving does not link or disconnect WhatsApp, send a message, change the password, or modify client data. Use a phone number that belongs to the business and follows the format shown by the form. If the save fails, correct validation messages and retry without refreshing; refreshing may discard unsaved local edits.

## Support boundary

Support can help with validation or a profile save that fails repeatedly. Share the field name and error message only. Do not share password values, WhatsApp pairing codes, API keys, or mailbox credentials.
