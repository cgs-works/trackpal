---
id: tenant-admin.clients
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: clients
capabilities:
  - tenant_clients
route: /admin/clients
help_targets:
  - admin.clients
title: Clients
summary: Create and manage accounts for the people who receive your services.
search_tags:
  - clients
  - client search
  - create client
  - edit client
  - activate client
  - deactivate client
  - delete client
  - canonical login
  - client subscriptions
synonyms:
  - customers
  - users
  - client accounts
order: 100
safe_navigation:
  route: /admin/clients
  settings_category: null
related_topics:
  - tenant-admin.first-pro-client
  - tenant-admin.subscriptions
  - tenant-admin.whatsapp
tour:
  - release_id: tenant-admin-pro-1
    order: 3
    target: admin.clients
    conditional: false
    plans:
      - pro
    title: Clients
    content: |
      # Organize your clients

      Create an account for each person who receives your services. From here you can find them, update access, and open subscriptions.
  - release_id: tenant-admin-pro-upgrade-1
    order: 1
    target: admin.clients
    conditional: false
    plans:
      - pro
    title: Clients in TrackPal Pro
    content: |
      # Meet Clients

      You can now create accounts for the people who receive your services, manage their access, and open their subscriptions.
---

# Clients

**TrackPal Pro** lets you create an account for each person who receives your services and manage their access on the Web or in WhatsApp.

## Add a client

Select **Create client** and enter the name, a local username, a password with at least six characters, and an optional phone. TrackPal adds your business prefix to the username. Give the client the full username shown after saving, for example `t1_pepe`.

## Manage access

Search by name, username, or phone. From each client you can edit details, deactivate or reactivate access, open subscriptions, and delete the account after it is inactive. Deactivation closes active sessions; reactivation allows a new sign-in.

In WhatsApp, open **Clients** from the **TrackPal Pro** menu. Use `9` to go back and `0` to cancel the current flow.

If a username or phone already exists, correct the highlighted value. Deletion is permanent, so confirm the client's name before continuing.
