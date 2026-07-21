---
id: client.whatsapp
audience: client
plans:
  - pro
channels:
  - whatsapp
module: help
capabilities:
  - client_whatsapp
route: /client/dashboard
help_targets: []
title: Client WhatsApp Console
summary: Use the available WhatsApp actions without confusing them with Web-only account changes.
search_tags:
  - WhatsApp
  - profile
  - subscriptions
  - access code
  - exit
synonyms:
  - chat menu
  - bot menu
order: 50
safe_navigation:
  route: /client/dashboard
  settings_category: null
related_topics:
  - client.dashboard
  - client.profile
  - client.subscriptions
  - client.password
---

# Client WhatsApp Console

The Client WhatsApp console is a separate, limited channel for viewing information and requesting an access-code lookup through the provider's configured flow.

## Channel, prerequisites, and actions

- **Channel:** WhatsApp. Your provider must have an active Pro setup and a WhatsApp flow that recognizes your Client account.
- **Prerequisites:** Use the phone associated with the Client account and follow the menu sent by the bot. The provider must have the required mailbox and enabled platform configuration for access-code lookup.
- **Actions:** View your profile, view active subscriptions, search for an access code when the option is available, and exit the console. Follow the current menu labels instead of guessing numbers.

## Web-only boundary

Password changes are Web-only. Open the Web Profile page for that action. WhatsApp cannot edit your name, phone, provider, account status, subscriptions, or service credentials.

## Results, navigation, and recovery

A successful request returns the permitted profile, subscription, or lookup result. A missing configuration, unavailable subscription, invalid input, or timeout returns a recoverable message; follow the prompt or start a new session. Use the menu's exit option when finished. Do not send passwords, credentials, pairing codes, or arbitrary private commands to the bot.

## Support boundary

The provider controls Client WhatsApp access and the mailbox lookup configuration. Share only the visible error and approximate time with support, never a password, access code, subscription credential, or private message content.
