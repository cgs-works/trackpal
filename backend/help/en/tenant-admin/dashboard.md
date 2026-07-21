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
title: Dashboard
summary: See how your business is doing and find what needs attention.
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
    title: Welcome to TrackPal Starter
    content: |
      # Meet TrackPal Starter

      In less than three minutes, you will see where your business tools are and how Dashboard, Settings, WhatsApp, and Help work together.

      Select **Next** to begin. You can replay this orientation at any time from Help.
  - release_id: tenant-admin-starter-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - starter
    title: Your Dashboard
    content: |
      # Start with the Dashboard

      Check the central mailbox, enabled platforms, and Access control here. Use the sidebar to open Settings or Help.
  - release_id: tenant-admin-pro-1
    order: 1
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Welcome to TrackPal Pro
    content: |
      # Meet TrackPal Pro

      In less than three minutes, you will tour the tools that connect clients, Catalog, subscriptions, Settings, and WhatsApp.

      Select **Next** to begin. You can replay this orientation at any time from Help.
  - release_id: tenant-admin-pro-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Your Dashboard
    content: |
      # Start with the Dashboard

      See clients, services, subscriptions, upcoming expirations, and setup tools at a glance. Use the sidebar to open each section.
---

# Dashboard

The Dashboard gives you a quick view of your business in TrackPal.

## What you will see

Every account shows the central mailbox status, enabled platforms, and blocked WhatsApp access. **TrackPal Pro** also shows clients, Catalog services, active subscriptions, and upcoming expirations.

Use these numbers to choose your next step: finish a setup, handle a subscription, or review an integration.

## If something looks wrong

A zero can be normal when a feature has not been set up yet. If the page does not load, try again. If the error continues, share the visible message with support, not passwords or codes.
