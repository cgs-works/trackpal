---
id: tenant-admin.catalog
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: catalog
capabilities:
  - tenant_catalog
route: /admin/catalog
help_targets:
  - admin.catalog
title: Catalog
summary: Organize the services and plans your business offers.
search_tags:
  - catalog
  - service
  - plan
  - create service
  - create plan
  - rename service
  - rename plan
  - delete service
  - delete plan
  - delete impact
synonyms:
  - product catalog
  - offerings
  - service list
order: 110
safe_navigation:
  route: /admin/catalog
  settings_category: null
related_topics:
  - tenant-admin.clients
  - tenant-admin.first-pro-client
  - tenant-admin.subscriptions
tour:
  - release_id: tenant-admin-pro-1
    order: 4
    target: admin.catalog
    conditional: false
    plans:
      - pro
    title: Catalog
    content: |
      # Prepare your Catalog

      Create the services your business offers and add their plans. You will use them when preparing a client subscription.
  - release_id: tenant-admin-pro-upgrade-1
    order: 2
    target: admin.catalog
    conditional: false
    plans:
      - pro
    title: Catalog in TrackPal Pro
    content: |
      # Meet the Catalog

      Organize your services and plans so they are ready for subscriptions.
---

# Catalog

In **TrackPal Pro**, the Catalog contains your services and the plans available for each one. Prepare it before creating subscriptions.

## Create and organize

Create a service, open it, and add its plans. You can also rename them on the Web or from **Catalog** in the **TrackPal Pro** WhatsApp menu. An empty list simply means the first service or plan has not been created yet.

## Service icons

Each service can have an optional icon. Choose, replace, or remove an icon from the Web catalog editor — these are visual-only actions. WhatsApp continues to manage service names and plans as text. If Iconify is temporarily unavailable, save with the current or generic icon and retry later.

## Before deleting

TrackPal shows how many active subscriptions and historical subscriptions depend on the service or plan. Review them carefully: deletion is irreversible and also removes the related subscriptions.

Enter `DELETE` on the Web to confirm. In WhatsApp use `CONFIRM` or `CONFIRMAR`; `0` cancels and `9` goes back.

If the preview does not load or a name already exists, correct the issue before continuing. Support does not need client credentials to help.
