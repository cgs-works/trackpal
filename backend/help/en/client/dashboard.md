---
id: client.dashboard
audience: client
plans:
  - pro
channels:
  - web
module: dashboard
capabilities:
  - client_dashboard
route: /client/dashboard
help_targets:
  - client.dashboard
title: Client Dashboard
summary: See your provider, account status, and active subscription overview.
search_tags:
  - dashboard
  - home
  - provider
  - account
synonyms:
  - home page
  - overview
order: 10
safe_navigation:
  route: /client/dashboard
  settings_category: null
related_topics:
  - client.profile
  - client.subscriptions
  - client.password
  - client.whatsapp
---

# Client Dashboard

The Client Dashboard is the read-only starting point for your TrackPal account with a Pro provider.

## Channel, prerequisites, and actions

- **Channel:** Web. Sign in with the Client account created by your provider.
- **Prerequisites:** Your provider's TrackPal plan must include client access, and your account must be active.
- **Actions:** Open Dashboard to see your name, provider, account, and active subscriptions. The page does not edit Client data.

## Results and states

The summary shows the provider name and the number of subscriptions available to you. The subscription list shows each service, plan, status, start date, and expiration date. An empty list means your provider has not assigned an active subscription yet.

Loading means TrackPal is retrieving current data. If the page cannot load, use Retry. An inactive account or a provider that has moved to Starter cannot use the Client session; contact the provider instead of trying to create another account.

## Web and WhatsApp

Use the Web Dashboard for the complete read-only overview. WhatsApp has a separate Client console for profile, active subscriptions, access-code search, and exit. WhatsApp does not provide Client password changes.

## Support boundary

Your provider controls your Client access and subscriptions. Support can help investigate a persistent loading or sign-in error, but never send a password, access code, subscription credential, or private WhatsApp message.
