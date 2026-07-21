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
summary: Create and organize services and plans before assigning subscriptions to clients.
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
---

# Catalog

The Catalog is the Pro Tenant's list of services and plans. A service is the offering, and its plans are the selectable variants used when creating a subscription.

## Channel, prerequisites, and actions

- **Web:** Open Catalog from the sidebar. Create a service, select it, create or rename its plans, rename a service, or open the delete preview before deleting a service or plan.
- **WhatsApp:** From the Pro main menu choose `2` Catalog. With services, choose `1` to view them, `2` to create a service, or `3` to delete a service. Select a service to edit its name, view plans, create a plan, or delete a plan. With no services, the menu offers the first service creation directly.
- **Prerequisites:** Catalog is Pro-only. To create a plan, create or select its service first. A catalog change does not create a client or subscription automatically.

## Services, plans, and empty states

A service can exist without plans. The service detail screen shows an empty plans state and offers Create plan; return with `9` or cancel with `0`. An empty service list means no services exist, so create the first service. An empty plan list means the selected service has no plans; it is not a loading failure.

Lists may paginate. Use `8` only when Next is displayed and `9` to go back. A loading state means TrackPal is retrieving the current catalog. A failed load or save leaves the prior catalog unchanged; retry after checking the visible error.

## Create and rename

Enter a non-empty service or plan name and save on Web, or answer the WhatsApp prompt. A successful result returns to a post-action prompt; choose `1` to return to the main menu. A blank name, invalid selection, duplicate name, or unavailable service is rejected and can be corrected without creating a partial record. Renaming changes the label only; it does not move plans or change existing subscriptions.

## Deletion preview and consequences

Deleting a service or plan is irreversible. Before confirmation, Web and WhatsApp show the delete impact preview. For a service, review the affected plan count, active subscriptions, historical subscriptions, total subscriptions, and the listed active subscription rows. For a plan, review the active, historical, and total subscription counts and rows. Historical subscriptions are included in the consequence summary even though they are no longer active.

Deleting a service permanently removes that service, its plans, and all subscriptions attached to it. Deleting a plan permanently removes that plan and all subscriptions attached to it. Active subscriptions are not preserved or converted. Use the listed client, service, plan, and expiration details to verify the impact before proceeding.

On Web, type `DELETE` in the preview confirmation field. In WhatsApp, type `CONFIRM` or `CONFIRMAR` when prompted. Any other value shows a confirmation re-prompt; `0` cancels and `9` returns to selection. A cancelled preview or failed deletion does not mutate the catalog.

## Limits, validation, and recovery

Only services that are globally active can be selected for access-code lookup; Catalog names do not enable a code platform. The Catalog does not reveal subscription credentials. If the preview cannot load, do not guess the impact or repeat the destructive action; retry the preview and contact support with the visible error.

## Support boundary

Support can investigate a persistent catalog load, validation, preview, or deletion error. Share the affected service or plan name and visible counts only; never share subscription passwords, PINs, mailbox credentials, or access codes.
