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
title: Subscriptions
summary: Manage each client's access to your services and plans.
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
tour:
  - release_id: tenant-admin-pro-1
    order: 5
    target: admin.subscriptions
    conditional: false
    plans:
      - pro
    title: Subscriptions
    content: |
      # Manage subscriptions

      Connect each client with a service and plan. Review dates and status here, then renew, reactivate, or cancel when needed.
  - release_id: tenant-admin-pro-upgrade-1
    order: 3
    target: admin.subscriptions
    conditional: false
    plans:
      - pro
    title: Subscriptions in TrackPal Pro
    content: |
      # Meet Subscriptions

      Connect clients with services and plans, control their dates, and manage every stage of access.
---

# Subscriptions

In **TrackPal Pro**, a subscription connects a client with a Catalog service and plan. Use the filters to find subscriptions by client, service, or status.

## Create or edit

Select **New subscription**, choose the client, service, and plan, and enter the service email. Add a password, profile, and PIN when needed. Choose a duration or custom expiration date and review the summary before saving.

When editing, leaving a password or PIN empty keeps the stored value. If an active subscription already exists for the same client, service, and email, consider extending it instead of creating a duplicate.

## Status and actions

- **Active:** can be edited, cancelled, or renewed.
- **Expired:** can be renewed or reactivated.
- **Cancelled:** can be reactivated with new dates.

**Renew** extends the expiration. **Reactivate** starts a new period. **Cancel** changes the status without immediately deleting the record.

In WhatsApp, open **Subscriptions** from the **TrackPal Pro** menu. Use `1` Edit, `2` Cancel, `3` Renew, or `4` Reactivate when available; `8` moves forward, `9` goes back, and `0` cancels.

Use **Reveal credentials** only when necessary, and never copy passwords or PINs into a support request.
