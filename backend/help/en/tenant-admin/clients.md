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
summary: Manage Pro clients, their access, status, canonical login, and subscriptions.
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
---

# Clients

Clients are the people who receive the services offered by a Pro Tenant. Client management is available only to Pro Tenant Admins on Web and in the Pro WhatsApp console.

## Channel, prerequisites, and actions

- **Web:** Open Clients from the sidebar. Search by full name, canonical username, or phone; use Create to add a client, the edit action to change identity fields, the power action to activate or deactivate access, the subscriptions action to open that client's subscriptions, and the delete action for an inactive client.
- **WhatsApp:** From the Pro main menu choose `1` Clients. Choose `1` to view clients or `2` to create one. Select a listed client to edit, deactivate, reactivate, or delete it. Use `9` to go back and `0` to cancel.
- **Prerequisites:** The Tenant must be on Pro and you must be its Tenant Admin. To create a client, prepare a full name, a valid local username, a password of at least six characters, and an optional phone number.

## Create and canonical login

Enter the client's full name, local username, optional phone, and password, then save on Web or confirm the summary in WhatsApp. The local username must start with a lowercase letter and contain only lowercase letters, digits, and underscores. TrackPal combines it with the Tenant's immutable prefix to create the canonical login in the form `{client_prefix}_{local_username}`, such as `t1_pepe`. Give the client this full canonical login, not only the local portion.

A successful creation adds an active client. A duplicate local username, canonical username, or phone is rejected and leaves the existing clients unchanged. Correct the field and try again. A missing or invalid name, username, phone, or password is a validation error; it does not create a partial client.

## Search, edit, activate, and deactivate

Search is a local filter over the loaded client list and does not change data. An empty list means no clients exist; an empty search result means the filter has no match. Clear the search or adjust the spelling and digits.

Edit changes the full name, local username, or phone. Renaming the local username also updates the canonical login. A duplicate value or invalid field is rejected without applying the edit. Activate restores access for an inactive client. Deactivate changes the client to inactive and revokes that client's active Web sessions; the client must sign in again after reactivation.

## Subscriptions and deletion

Use the credit-card or subscriptions action on the client row to open Subscriptions already filtered to that client. This is a safe navigation link; it does not create, reveal, cancel, renew, or reactivate a subscription. The client topic is also related to the Subscriptions module for the full subscription workflow.

An active client cannot be deleted. Deactivate it first. Deletion is permanent: it removes the client account and its login, cannot be undone, and is not a substitute for deactivation. Confirm the deletion only after checking that the selected client is correct. A cancelled dialog or a failed request leaves the client in its previous state.

## WhatsApp validation and recovery

The Pro WhatsApp flow validates each requested field and repeats the prompt for an invalid selection, empty name, empty username, short password, or invalid phone. At the confirmation prompt type `CONFIRM` or `CONFIRMAR` as shown; type `0` to cancel. A failed create, edit, activation, deactivation, or deletion keeps the previous data and can be retried. `9` returns to the preceding screen and `8` advances only when the prompt displays it.

## Support boundary

Support can help with a persistent validation or access error when given the visible field and message. Never share a client's password, generated password, access token, or subscription credentials in a ticket or chat.
