---
id: tenant-admin.activate-access-code-lookup
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: help
capabilities:
  - tenant_access_code_lookup
route: /admin/settings
help_targets:
  - admin.settings
title: Activate access-code lookup
summary: Connect the dependencies in order, then run the first safe WhatsApp code search.
search_tags:
  - activate access-code lookup
  - first code search
  - access-code setup
  - search prerequisites
  - code lookup recovery
synonyms:
  - enable code search
  - first access code
  - code search setup
order: 90
safe_navigation:
  route: /admin/settings
  settings_category: code-services
related_topics:
  - tenant-admin.code-services
  - tenant-admin.mailbox
  - tenant-admin.whatsapp
  - tenant-admin.access-control
---

# Activate access-code lookup

Use this path when the business wants to find a service access code from WhatsApp. Complete the dependencies in order; the lookup is available only after the linked WhatsApp instance, enabled platform, and central mailbox are ready.

## Dependency chain

1. **Link WhatsApp:** In Web Settings, configure the business phone in Profile, open WhatsApp, and pair with a pairing code or QR code. Wait for Connected. A disconnected or missing-phone state must be recovered before continuing.
2. **Select a platform:** In Settings, open Enabled code platforms, select at least one globally active service, and save. If the list is loading, unavailable, or returns an error, wait or retry before testing a search.
3. **Connect the mailbox:** In Settings, open Central lookup mailbox and connect Google, Microsoft, or custom IMAP. Run Test connection and continue only when the status is Connected. Pending, error, revoked, or timed-out connections need recovery in that category.
4. **Start from the matching WhatsApp menu:** Starter uses `2` for Find Access Code. Pro uses `7`. Choose a listed service, enter the subscription email, and review it before confirming with `1`.
5. **Handle the first result:** The search is pending while TrackPal checks recent mailbox messages. A found code or link is returned to the WhatsApp conversation. A not-found, duplicate, error, or timeout result tells you which recovery to use.

## Navigation and safe recovery

The shared navigation contract uses `0` to cancel, while the current prompt labels `8` and `9` for page navigation or returning to the previous screen. On email confirmation, `2` corrects the email and `9` returns to the service list. Use `0` instead of sending credentials or abandoning a half-completed search. If the session times out, start the flow again from the plan menu.

## States and recovery

- **Pending:** Wait for the result instead of starting repeated searches. If it does not arrive, use the timeout recovery and check the mailbox status.
- **Found:** Use the code promptly because service codes can expire. Treat a returned link as sensitive and open it only when expected.
- **Not found:** Request a new code from the service, wait for the email, and try again with the correct service and subscription email.
- **Duplicate:** Wait the displayed cooldown, then retry for the latest code instead of repeating immediately.
- **Error:** Check that the mailbox is Connected and the selected platform is still available, then retry later.
- **Timeout:** Check the provider and mailbox connection, then start a new search. Do not disconnect a healthy WhatsApp instance or mailbox as a first response.
- **Missing prerequisites:** Return to Web Settings and complete the first missing dependency. Existing platform selections and business data are preserved when a connection is repaired.

## Web and WhatsApp actions

The Web Help link opens Settings without saving forms, connecting or disconnecting a service, blocking an identity, or starting a search. The WhatsApp flow is the place where the search is requested; the guide never asks you to paste mailbox credentials, passwords, tokens, pairing codes, or QR images into chat.

## Support boundary

Support can trace a persistent lookup error, timeout, or unexpected result when given the service, mailbox status, visible error, and approximate time. Never send the access code, email password, OAuth token, pairing code, or QR image in a support request.
