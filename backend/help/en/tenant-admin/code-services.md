---
id: tenant-admin.code-services
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: settings
capabilities:
  - tenant_code_services
route: /admin/settings
help_targets:
  - admin.settings.code-services
title: Enabled code platforms
summary: Choose which supported services can be searched for access codes.
search_tags:
  - code services
  - access code
  - platform
  - provider
  - enabled service
synonyms:
  - streaming services
  - services list
  - code providers
order: 60
safe_navigation:
  route: /admin/settings
  settings_category: code-services
related_topics:
  - tenant-admin.activate-access-code-lookup
  - tenant-admin.mailbox
  - tenant-admin.dashboard
  - tenant-admin.whatsapp
---

# Enabled code platforms

Enabled code platforms are the services that TrackPal can search when a Tenant Admin or a client requests an access code. The available list is controlled by the platform catalog and your Tenant selection.

## Channel, prerequisites, and actions

- **Channel:** Web for configuration; WhatsApp for using the selected platforms in the access-code search.
- **Prerequisites:** Be a Tenant Admin. The business WhatsApp instance and central lookup mailbox are separate prerequisites for completing a search.
- **Actions:** Open Settings, choose Enabled code platforms, select the services that should be available, and save. Only globally active services can be selected.

## Results and states

- **Loading:** TrackPal is retrieving the platform list. Wait for the list before changing selections.
- **Enabled:** A selected, globally active platform appears in the WhatsApp service list.
- **Unavailable:** A platform marked globally inactive cannot be selected. It is not an error in your Tenant configuration.
- **Missing:** If no platform is selected, access-code lookup cannot start and WhatsApp reports that code services are not configured.
- **Error:** If the list or save request fails, keep the current selection, retry from Settings, and do not start repeated WhatsApp searches until the list is available.

## Web and WhatsApp actions

On Web, selecting a platform changes which services appear in future searches; it does not search the mailbox or send a WhatsApp message. In WhatsApp, the Starter menu opens access-code search with `2` and the Pro menu opens it with `7`. The service list contains only the effective selection: Tenant-selected services that are still globally active.

## Limits, consequences, and recovery

The list is limited to the services currently supported and globally active by TrackPal. Enabling a platform does not connect its provider account and does not create a client or subscription. If a platform becomes globally inactive, it is omitted from effective searches until it is available again. If lookup reports no configured services, return to this category, select an available platform, save, and start a new search.

## Support boundary

Support can confirm whether a platform is globally available and investigate a persistent load or save error. Share the platform label and visible error only; never share mailbox credentials, access codes, passwords, or tokens.
