---
id: tenant-admin.country
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.regional
title: Country
summary: Choose the country where your business operates.
search_tags:
  - country
  - country currency
  - business country
synonyms:
  - location
order: 21
safe_navigation:
  route: /admin/settings
  settings_category: my-account
  tab: regional
related_topics:
  - tenant-admin.currency
  - tenant-admin.language
---

# Country

TrackPal stores the country as an ISO code. Country names are displayed in the language you chose for the workspace.

Open **My Account > Regional settings**, select the country, and save. Choosing a country surfaces its official currency first in the currency picker without changing the saved currency.

This setting is available on TrackPal Starter and TrackPal Pro plans.
