---
id: tenant-admin.dashboard
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: dashboard
capabilities:
  - tenant_dashboard
route: /admin/dashboard
help_targets:
  - admin.dashboard
title: Business Dashboard
summary: Understand your plan, operational status, and the services available to your business.
search_tags:
  - dashboard
  - plan
  - mailbox
  - access control
synonyms:
  - home
  - overview
order: 10
safe_navigation:
  route: /admin/dashboard
  settings_category: null
related_topics:
  - tenant-admin.language
  - tenant-admin.whatsapp
tour:
  - release_id: tenant-admin-starter-1
    order: 1
    target: admin.dashboard
    conditional: false
    plans:
      - starter
    title: Welcome to TrackPal
    content: |
      # Welcome to TrackPal

      This optional Starter orientation takes about 2 to 3 minutes. It explains where the tools in your current plan live and how Web, WhatsApp, enabled platforms, and the central mailbox fit together.

      Continue with **Next**, or choose **Skip tour**. Skipping never blocks your workspace, and you can replay this orientation from Help.
  - release_id: tenant-admin-starter-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - starter
    title: Dashboard and navigation
    content: |
      # Your Starter workspace

      The Dashboard shows your current plan and operational signals. Use the navigation to move between Dashboard, Settings, and Help. Starter exposes the modules included in your current plan.

      The values here are read-only. The tour uses your real workspace and does not create demo data or change settings.
  - release_id: tenant-admin-pro-1
    order: 1
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Welcome to Pro
    content: |
      # Welcome to Pro

      This optional Pro orientation takes about 2 to 3 minutes. It maps the Pro modules and explains how Web, WhatsApp, subscriptions, reminders, and the Public API fit together.

      Continue with **Next**, or choose **Skip tour**. Skipping never blocks your workspace, and you can replay this orientation from Help.
  - release_id: tenant-admin-pro-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Pro dashboard and navigation
    content: |
      # Your Pro workspace

      The Dashboard shows your current plan and operational signals. Pro adds Clients, Catalog, and Subscriptions to the navigation, while Settings and Help remain the safe starting points for configuration and guidance.

      The values here are read-only. The tour uses your real workspace and does not create demo data or change settings.
---

# Business Dashboard

The Business Dashboard is the starting point for Tenant Admins. It summarizes what TrackPal can do for your business on the current plan.

## Channel, prerequisites, and actions

- **Channel:** Web. The dashboard is not a WhatsApp menu.
- **Prerequisites:** Sign in as a Tenant Admin with an active Tenant. No setup is required to read the page.
- **Actions:** Open Dashboard from the sidebar and use the read-only indicators to decide which module to open next.

## Results and states

- You see your Starter or Pro plan, central lookup mailbox status, enabled code-service count, and blocked WhatsApp identity count.
- Pro also shows active Clients, Catalog services, active Subscriptions, and subscriptions expiring soon.
- A loading state means TrackPal is refreshing Tenant data. An empty mailbox or zero enabled services means access-code lookup is not ready.
- A failed load leaves the page without current metrics. Retry from the page and contact support if the error persists.

## Limits, consequences, and recovery

Dashboard is read-only: viewing it creates no records and changes no settings. It does not link WhatsApp, enable platforms, configure a mailbox, or start a WhatsApp session. Open the matching Settings category to complete setup. If a module is missing from navigation, the current plan does not include it; Pro data remains preserved after a downgrade but Pro actions are unavailable.

## Web and WhatsApp

Use Web Dashboard for the overview. WhatsApp has its own Tenant Admin menu and session rules; use the WhatsApp topic for that flow. Dashboard values are refreshed from the active Tenant and can change after another administrator updates setup.

## Support boundary

Support can help interpret a status, plan access, or a persistent loading error. Do not send passwords, pairing codes, access tokens, or mailbox credentials in a support request.
