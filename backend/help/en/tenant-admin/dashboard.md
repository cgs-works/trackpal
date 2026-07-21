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

      This optional orientation takes about 2 to 3 minutes. It explains where to find the tools included in your current plan and how the Web dashboard, WhatsApp, enabled platforms, and the central mailbox fit together.

      Continue with **Next**, or choose **Skip tour**. Skipping never blocks your control panel, and you can replay this orientation from Help.
  - release_id: tenant-admin-starter-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - starter
    title: Dashboard and navigation
    content: |
      # Your control panel

      The Dashboard shows your current plan and the overall status of your tools. Use the navigation to move between Dashboard, Settings, and Help. It only shows the sections included in your current plan.

      The values here are read-only. The tour uses your business's real information and does not create demo data or change settings.
  - release_id: tenant-admin-pro-1
    order: 1
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Welcome to TrackPal
    content: |
      # Welcome to TrackPal

      This optional orientation takes about 2 to 3 minutes. It explains the tools included in your plan and how the Web dashboard, WhatsApp, subscriptions, reminders, and publishing your catalog on a website fit together.

      Continue with **Next**, or choose **Skip tour**. Skipping never blocks your control panel, and you can replay this orientation from Help.
  - release_id: tenant-admin-pro-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Dashboard and navigation
    content: |
      # Your control panel

      The Dashboard shows your current plan and the overall status of your tools. Depending on your plan, the navigation also includes Clients, Catalog, and Subscriptions. Settings contains your business configuration, and Help explains each section.

      The values here are read-only. The tour uses your business's real information and does not create demo data or change settings.
---

# Dashboard

The Dashboard is the starting point for your control panel. It summarizes what TrackPal can do for your business based on your current plan.

## Channel, prerequisites, and actions

- **Channel:** Web. The dashboard is not a WhatsApp menu.
- **Prerequisites:** Sign in as an administrator with an active business. No setup is required to read the page.
- **Actions:** Open Dashboard from the sidebar and use the read-only indicators to decide which module to open next.

## Results and states

- You see your Starter or Pro plan, central lookup mailbox status, enabled code-service count, and blocked WhatsApp identity count.
- Pro also shows active Clients, Catalog services, active Subscriptions, and subscriptions expiring soon.
- A loading state means TrackPal is refreshing business data. An empty mailbox or zero enabled services means access-code lookup is not ready.
- A failed load leaves the page without current metrics. Retry from the page and contact support if the error persists.

## Limits, consequences, and recovery

Dashboard is read-only: viewing it creates no records and changes no settings. It does not link WhatsApp, enable platforms, configure a mailbox, or start a WhatsApp session. Open the matching Settings category to complete setup. If a module is missing from navigation, the current plan does not include it; Pro data remains preserved after a downgrade but Pro actions are unavailable.

## Web and WhatsApp

Use Web Dashboard for the overview. WhatsApp has its own administrator menu and session rules; use the WhatsApp topic for that flow. Dashboard values are refreshed from the active business and can change after another administrator updates setup.

## Support boundary

Support can help interpret a status, plan access, or a persistent loading error. Do not send passwords, pairing codes, access tokens, or mailbox credentials in a support request.
