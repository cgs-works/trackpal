---
id: tenant-admin.mailbox
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: settings
capabilities:
  - tenant_mailbox
route: /admin/settings
help_targets:
  - admin.settings.mailbox
title: Central mailbox for access codes
summary: Connect the inbox that receives emails containing access codes.
search_tags:
  - mailbox
  - email inbox
  - OAuth
  - IMAP
  - connection test
  - access-code email
synonyms:
  - code mailbox
  - central inbox
  - email connection
order: 70
safe_navigation:
  route: /admin/settings
  settings_category: mailbox
related_topics:
  - tenant-admin.activate-access-code-lookup
  - tenant-admin.code-services
  - tenant-admin.whatsapp
---

# Central mailbox for access codes

TrackPal checks this mailbox when someone requests an access code in WhatsApp. Use an inbox managed by the business, not a client's personal email.

## Choose how to connect

- **Google or Microsoft:** guided connection. Approve access in the provider window without entering your password in TrackPal. This option uses OAuth.
- **IMAP:** manual setup for other providers or anyone who prefers to enter the connection details. You can choose IMAP as an alternative to OAuth.

After connecting the account, select **Test connection**. Continue when the status is **Connected**.

## If the connection fails

Review the visible message and test again. If Google or Microsoft permission expired, reconnect the account. For IMAP, confirm the details supplied by your email provider. Disconnect the mailbox only when you intend to replace it, because access-code search pauses until a new connection is ready.
