---
id: client.subscriptions
audience: client
plans:
  - pro
channels:
  - web
  - whatsapp
module: subscriptions
capabilities:
  - client_subscriptions
route: /client/dashboard
help_targets:
  - client.subscriptions
title: Active Subscriptions
summary: Understand the active service subscriptions assigned to your Client account.
search_tags:
  - subscriptions
  - service
  - plan
  - expiration
  - status
synonyms:
  - memberships
  - access plans
order: 30
safe_navigation:
  route: /client/dashboard
  settings_category: null
related_topics:
  - client.dashboard
  - client.whatsapp
---

# Active Subscriptions

The Dashboard lists the active subscriptions assigned to you by your provider.

## Channel, prerequisites, and actions

- **Channels:** Web and WhatsApp. Your provider must assign a subscription to your active Client account.
- **Prerequisites:** Sign in on Web, or enter the Client WhatsApp console when your provider has made it available.
- **Actions:** On Web, read the service, plan, status, start date, and expiration date. On WhatsApp, choose the active-subscriptions option shown by the console. Clients cannot create, renew, cancel, or reveal subscription credentials.

## Results and states

Active, pending, expired, or cancelled status is shown without allowing a Client to change it. An empty list means there are no active assignments. An expiration date close to today may show a remaining-days warning; ask the provider about renewal. Loading and failed states can be retried on Web.

## Web-only and WhatsApp boundaries

The Web Dashboard is the complete source for dates and provider information. WhatsApp is a convenient summary and does not change subscription data. Password changes are Web-only and are documented in Password change on Web.

## Support boundary

The provider owns subscription lifecycle decisions and any service credentials. Never send subscription credentials, access codes, or screenshots of private data to support.
