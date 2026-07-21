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
title: Publish the Public API Catalog
summary: Prepare a read-only browser integration and hand safe implementation instructions to your developer.
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
---

# Publish the Public API Catalog

The Public API Catalog lets a Pro Tenant publish its services and plans to a Tenant-owned browser frontend. It is **read-only**: the public payload contains service and plan IDs and names, not prices, availability, descriptions, credentials, or mutation controls. This topic is private Help for Tenant Admins; it does not create, reveal, regenerate, or revoke a key for you.

## Prepare the Catalog and Allowed Origins

First make the Catalog ready. Create the services and plans that the website should display, and confirm their names and order in Catalog. The public endpoint reads the current Catalog, so later Catalog changes are reflected without copying records into the website.

An Allowed Origin is the exact browser origin where the catalog will run. Register the complete `http://` or `https://` scheme, host, and optional port, such as `https://shop.example.com` or `http://localhost:5173`. Do not add a path, query string, fragment, wildcard, or a server URL. The browser's `Origin` must match exactly; server-to-server use is outside this version.

## Create the key and connect the website

Open Settings, choose API Key, add at least one Allowed Origin, and create the key. Keep the key out of source control, screenshots, public chat, and frontend logs. The developer handoff package in this Settings panel contains a placeholder, `YOUR_PUBLIC_API_KEY`, and maintained examples for HTML + JavaScript, React, Vue, Svelte, Angular, and Alpine.js. It never inserts this Tenant's real key. Send the package separately, then provide the real key through a secure channel.

The browser integration makes a `GET` request to `/api/v1/public/catalog?api_key=YOUR_PUBLIC_API_KEY`. The browser supplies `Origin` automatically. TrackPal returns the read-only catalog only when both the key and exact origin are valid. A missing Origin, unknown key, non-matching origin, or Starter downgrade returns a forbidden response.

The handoff examples are reference snippets, not a full REST API manual. Select the example matching the site's existing technology. Help links only open this Settings category or Catalog; they never submit the form or call an API operation.

## Lifecycle and consequences

Regenerating the key replaces the old key and preserves the Allowed Origins. Every integration using the old value must be updated, and the old value stops authorizing requests. Revoking or deleting the key removes the public configuration and disables the catalog on connected websites. It is irreversible from the integration's point of view; a future key must be created and shared separately.

Changing an Allowed Origin affects browser authorization immediately. Removing a site's origin does not delete Catalog data, but that site will receive a forbidden response until its exact origin is registered again. Catalog deletion remains a separate destructive operation with its own impact preview.

## States, protection, and recovery

A missing key means the public integration has not been created. An empty or invalid origin is rejected before key creation. A forbidden response usually means the key, `Origin`, plan, or registered origin does not match; verify the exact scheme, host, and port without adding a path. If a Catalog request fails, confirm the browser request is made from an authorized site and check the visible error before retrying.

Before broad production exposure, protect `GET /api/v1/public/catalog` with a Cloudflare rate-limit or WAF rule for all public traffic. Cloudflare protection is the expected abuse boundary for this public route; do not add an application, Redis, or in-memory rate limiter as a workaround.

Starter Tenant Admins cannot retrieve, search, or invoke this topic. A downgrade pauses public access but preserves the key configuration for a future Pro reactivation. Contact support with the public endpoint, exact origin, response status, and visible non-secret error; never send the API Key itself.
