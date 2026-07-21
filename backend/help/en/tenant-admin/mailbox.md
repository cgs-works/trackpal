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
title: Central lookup mailbox
summary: Connect and test the mailbox that receives access-code emails.
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

# Central lookup mailbox

The central lookup mailbox is the inbox TrackPal checks for recent access-code emails. It is a business-level connection, not a client's personal mailbox.

## Channel, prerequisites, and actions

- **Channel:** Web for setup, connection testing, and disconnection; WhatsApp uses the connected mailbox during access-code search.
- **Prerequisites:** Have access to the email account your business will use. Google or Microsoft guides you through granting access without entering the password in TrackPal; this option is labeled OAuth. If you prefer to set up the mailbox manually or use another provider, you can choose IMAP as an alternative. In that case, you will need the connection details supplied by your email provider.
- **Actions:** Open Settings and choose Central lookup mailbox. Select Google or Microsoft for guided setup, or IMAP for manual setup. Then use Test connection. The status must be Connected before a search can run.

## Results and states

- **Not configured or disconnected:** No mailbox is ready, so WhatsApp access-code search stops before the service list or reports that the mailbox is not configured.
- **Pending:** An authorization window or connection test is still in progress. Keep the window open and wait for the result instead of starting another connection.
- **Connected:** TrackPal can check the mailbox when someone requests an access code.
- **Error:** A failed test or provider error leaves an error status and may show the last connection error. Correct the configuration and test again.
- **Permission expired or removed:** If Google or Microsoft removes permission, reconnect the account. Repeating a WhatsApp search will not repair the connection.
- **Timeout:** The email service took too long to respond. If you use IMAP, check the connection details and security setting before retrying.

## Web and WhatsApp actions

On Web, Google or Microsoft opens a secure window where you grant TrackPal access. IMAP is the manual alternative: complete and save the connection details before testing them. In WhatsApp, the search checks the central mailbox after the email address is confirmed; it never asks anyone to send the mailbox password to the bot.

## Limits, consequences, and recovery

The business has one central lookup mailbox. Disconnecting it ends the mailbox connection, clears stored mailbox secrets, and makes access-code lookup unavailable until a new connection is completed; it does not remove enabled platforms, clients, subscriptions, or WhatsApp access-control entries. If a test fails, fix the visible provider settings and test again. If Google or Microsoft removes permission, reconnect the account. Never disconnect a healthy mailbox just to recover a missing code; check the platform and email first.

## Support boundary

Support can help with a persistent authorization, manual connection, or timeout error. Share the provider, visible status, and approximate time of the error; never share passwords, authorization codes, or access codes.
