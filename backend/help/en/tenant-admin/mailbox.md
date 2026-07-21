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
- **Prerequisites:** Be a Tenant Admin and have access to the mailbox. Choose Google or Microsoft OAuth, or provide a custom IMAP server, email, port, SSL setting, and mailbox password.
- **Actions:** Open Settings, choose Central lookup mailbox, connect with OAuth or save the IMAP form, then use Test connection. The status must be Connected before a search can run.

## Results and states

- **Not configured or disconnected:** No mailbox is ready, so WhatsApp access-code search stops before the service list or reports that the mailbox is not configured.
- **Pending:** An OAuth window or connection test is still in progress. Keep the window open and wait for the result instead of starting another connection.
- **Connected:** The mailbox passed its connection setup and is available to the lookup worker.
- **Error:** A failed test or provider error leaves an error status and may show the last connection error. Correct the configuration and test again.
- **Revoked:** If an OAuth provider revokes permission, reconnect the provider. A revoked connection cannot be repaired by repeating a WhatsApp search.
- **Timeout:** A slow provider or IMAP server can time out. Check the host, port, SSL setting, and provider availability before retrying.

## Web and WhatsApp actions

On Web, OAuth opens a provider authorization window. IMAP saves the configuration before testing it. In WhatsApp, the lookup flow reads the central mailbox after the email is confirmed; it does not ask the user to send a mailbox password to the bot.

## Limits, consequences, and recovery

The Tenant has one central lookup mailbox. Disconnecting it ends the mailbox connection, clears stored mailbox secrets, and makes access-code lookup unavailable until a new connection is completed; it does not remove enabled platforms, clients, subscriptions, or WhatsApp access-control entries. If a test fails, fix the visible provider settings and test again. If OAuth is revoked, reconnect it. Never disconnect a healthy mailbox just to recover a missing code; check the platform and email first.

## Support boundary

Support can help with a persistent OAuth, IMAP, revoked, or timeout error. Share the provider, status, host and port when relevant, and the approximate time; never share an OAuth token, IMAP password, provider password, or access code.
