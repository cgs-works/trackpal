---
id: tenant-admin.timezone
audience: tenant_admin
plans:
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_settings
  - tenant_subscriptions
route: /admin/settings
help_targets:
  - admin.settings.regional
title: Business timezone
summary: Keep expirations and reminders aligned with your business's local time.
search_tags:
  - timezone
  - time zone
  - IANA timezone
  - local time
  - local date
  - daylight saving
synonyms:
  - business time zone
  - regional time
  - clock settings
order: 150
safe_navigation:
  route: /admin/settings
  settings_category: my-account
  tab: regional
related_topics:
  - tenant-admin.reminders
  - tenant-admin.subscriptions
  - tenant-admin.subscription-expirations
tour:
  - release_id: tenant-admin-pro-1
    order: 6
    target: admin.settings.regional
    conditional: false
    plans:
      - pro
    title: TrackPal Pro settings
    content: |
      # Make TrackPal fit your business

      Set the timezone, reminders, WhatsApp, central mailbox, and the other tools that keep your operation connected.
---

# Business timezone

TrackPal uses this region for the local calendar, subscription dates, reminder time, and the end of each day.

Open **My Account > Regional settings**, search for your region or city, select it, and save. TrackPal uses `UTC` as a reference until you choose one.

The setting applies to the whole business and automatically follows regional clock changes. A wrong timezone can make a reminder appear early or late without changing the stored expiration time.

If saving fails, the previous timezone stays active. Check the selected region and try again. Availability depends on the current plan.
