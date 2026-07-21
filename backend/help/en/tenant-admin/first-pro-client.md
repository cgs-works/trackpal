---
id: tenant-admin.first-pro-client
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: help
capabilities:
  - tenant_catalog
  - tenant_clients
  - tenant_subscriptions
route: /admin/catalog
help_targets: []
title: Set up your first client
summary: Follow the safe order from Catalog preparation to a client's first subscription.
search_tags:
  - first client
  - Pro setup
  - catalog setup
  - first subscription
  - onboarding order
synonyms:
  - get started with clients
  - first customer
  - initial setup
order: 130
safe_navigation:
  route: /admin/catalog
  settings_category: null
safe_links:
  - route: /admin/clients
    settings_category: null
  - route: /admin/subscriptions
    settings_category: null
related_topics:
  - tenant-admin.catalog
  - tenant-admin.clients
  - tenant-admin.subscriptions
---

# Set up your first client

Use this order when your business is ready to serve its first client. The guide is informational and its links only open authorized modules; Help never creates records or submits a form for you.

## 1. Prepare the Catalog

Open Catalog and create the service you offer. Select that service and create at least one plan. If the service or plan list is empty, that is the expected first state: use the create controls. Confirm the names before leaving the module. Read the Catalog delete preview guidance before removing anything.

## 2. Create the Client

Open Clients and choose Create. Enter the full name, a valid local username, the optional phone, and a password. Save the form and copy the generated canonical login pattern `{client_prefix}_{local_username}` for the person. Search for the new client and verify that its status is active.

If a local username or phone already exists, correct the value instead of retrying with duplicate data. Do not send the client's password to the person through an unsafe channel. The client can use the complete username only while the current plan includes client access and the account is active.

## 3. Open Client Subscriptions

From the Client row choose the subscriptions action, or open Subscriptions and select the client filter. Create the first subscription by choosing the prepared service and plan, then enter only the credentials and dates required by the form. Review the summary before confirming. The Client topic explains the direct link; the Catalog topic explains the data it depends on.

## Web and WhatsApp order

On Web the authorized module links are Catalog, Clients, and Subscriptions. In WhatsApp, use the Pro menu: `2` Catalog, `1` Clients, and `4` Subscriptions. Inside a flow, follow the displayed `9` Back, `8` Next, `0` Cancel, and confirmation prompts. Invalid input keeps the flow at its current step; it does not create partial setup.

## Completion and recovery

The setup is complete when the service, plan, active client, and first subscription appear in their respective authorized modules. If any module is loading or unavailable, retry that module and fix its visible validation error. If a subscription creation fails, the Catalog and Client remain available; check the service, plan, client status, and form values before trying again.

## Support boundary

Support can help identify which prerequisite is missing. Share module names and visible statuses only; never share client passwords, subscription credentials, mailbox credentials, access codes, or API keys.
