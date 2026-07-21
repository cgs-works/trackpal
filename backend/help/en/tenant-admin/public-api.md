---
id: tenant-admin.public-api
audience: tenant_admin
plans:
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_catalog
  - tenant_public_api
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.public-api
title: Publish your Catalog on a website
summary: Prepare the Catalog and give your developer what they need to display it.
search_tags:
  - public API
  - API Key
  - Allowed Origins
  - browser catalog
  - developer handoff
  - read-only catalog
  - Cloudflare
synonyms:
  - website catalog
  - external catalog
  - frontend integration
  - developer package
order: 155
safe_navigation:
  route: /admin/settings
  settings_category: public-api
safe_links:
  - route: /admin/catalog
    settings_category: null
related_topics:
  - tenant-admin.catalog
  - tenant-admin.first-pro-client
tour:
  - release_id: tenant-admin-pro-upgrade-1
    order: 5
    target: admin.settings.public-api
    conditional: false
    plans:
      - pro
    title: Publish your Catalog
    content: |
      # Bring your Catalog to your website

      Prepare the services you want to show, register your website, and give your developer the instructions available in Settings.
---

# Publish your Catalog on a website

**TrackPal Pro** can show your Catalog services and plans on your website. Visitors get read-only access: they cannot change TrackPal data or view credentials.

## What to prepare

1. Confirm that the Catalog contains the right services and plans.
2. In **Settings > API Key**, add each authorized website using its exact address, for example `https://shop.example.com`.
3. Create the key and give your developer the instructions package and the key through separate channels.

You do not need to write code. The package includes examples for several technologies and uses `YOUR_PUBLIC_API_KEY` as a placeholder. Your developer must replace it with the real key and protect `GET /api/v1/public/catalog` with a Cloudflare rate-limit or WAF rule.

## If the website does not show the Catalog

Confirm that the saved address exactly matches the browser's allowed origin. Regenerating the key invalidates the old one; revoking it disables the public Catalog. Never post the key in screenshots, repositories, or open chats.
