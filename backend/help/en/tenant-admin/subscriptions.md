---
id: tenant-admin.subscriptions
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: subscriptions
capabilities:
  - tenant_subscriptions
route: /admin/subscriptions
help_targets:
  - admin.subscriptions
title: Client Subscriptions
summary: Open and manage the subscriptions attached to a client, service, and plan.
search_tags:
  - subscriptions
  - client subscriptions
  - filter subscriptions
  - create subscription
  - cancel subscription
  - renew subscription
  - reactivate subscription
  - reveal credentials
synonyms:
  - memberships
  - client plans
  - service access
order: 120
safe_navigation:
  route: /admin/subscriptions
  settings_category: null
related_topics:
  - tenant-admin.clients
  - tenant-admin.catalog
  - tenant-admin.first-pro-client
---

# Client Subscriptions

Subscriptions connect a Client to a Catalog service and plan. Open Subscriptions from the sidebar, or use the subscriptions action in a Client row to arrive with that client selected.

## Channel, prerequisites, and actions

- **Web:** Filter the list by status, service, or client. Create a subscription, edit its fields, cancel it, renew it, reactivate a cancelled subscription, or open the credential reveal dialog when you have a valid reason.
- **WhatsApp:** From the Pro main menu choose `4` Subscriptions. Filter the list, select a subscription, then use the actions shown for its status: edit, cancel, renew, or reactivate when available.
- **Prerequisites:** The Tenant must be Pro. Create the required service and plan in Catalog and have an active Client before creating a subscription.

## States, confirmations, and sensitive data

Active, expired, and cancelled are distinct statuses. Cancelling changes the status and does not delete the subscription. Renewing or reactivating changes its dates after a confirmation. Create and lifecycle dialogs show a summary before the mutation; cancel with the visible Cancel action or `0` in WhatsApp.

Streaming passwords and profile PINs are sensitive credentials. Reveal them only through the explicit Web action when necessary, do not paste them into Help or support, and remember that a Help link never reveals them. A duplicate active subscription may offer extending its expiry instead of creating another one.

## Empty, validation, and recovery states

An empty list means no subscriptions match the current filters, not that the Client or Catalog was deleted. A missing service, plan, or Client prevents creation. Invalid email, date, duration, selection, or confirmation keeps the existing subscription unchanged. If a load or mutation fails, retry after checking the visible error.

## Support boundary

Support can help with a persistent subscription or lifecycle error using the visible status and identifiers. Never share streaming passwords, profile PINs, mailbox credentials, or revealed credentials.
