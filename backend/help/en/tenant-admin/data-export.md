---
id: tenant-admin.data-export
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: data
capabilities:
  - tenant_data_export
route: /admin/settings
help_targets:
  - admin.settings.my-account
  - admin.settings.data-tab
title: Data Export
summary: Request and download a point-in-time snapshot of your account data as a ZIP with CSV and JSON files.
search_tags:
  - export
  - download
  - backup
  - data
  - offboarding
  - snapshot
synonyms:
  - data export
  - download bundle
  - download data
  - account copy
  - save my data
order: 4
safe_navigation:
  route: /admin/settings
  settings_category: data
safe_links:
  - route: /admin/settings
    settings_category: data
related_topics:
  - tenant-admin.delete-account
  - tenant-admin.dashboard
  - tenant-admin.help
---

# Data Export

You can download a point-in-time snapshot of your TrackPal account data. The export is a ZIP file containing CSV spreadsheets and a JSON document with your account profile, client accounts, service catalog, subscription records, and blocked phone list.

## What's included

| File | Contents |
|------|----------|
| `account-profile.csv` | Your account name, contact email, WhatsApp phone, login username, current plan, language, and time zone |
| `client-data.csv` | Client name, login username, phone, account status, registration and last update dates |
| `service-catalog.csv` | Service name, creation and update dates, plan name and plan dates. Services without plans appear with empty plan fields |
| `subscription-snapshot.csv` | Client name and login, service, plan, streaming email and profile name, duration, start, expiry, cancellation dates, status, record timestamps |
| `blocked-phones.csv` | Blocked phone numbers and the date they were blocked |
| `trackpal-data.json` | Same data in JSON format with machine-readable structure |
| `README.txt` | Explanation of every file and field in your language |

## What's never included

For your security, the export intentionally excludes:

- Passwords (your login, client accounts, streaming subscriptions)
- Profile PINs and any sign that a password or PIN is set
- Mailbox login credentials or app passwords
- Evolution API tokens or Public API Keys
- Internal database IDs or technical identifiers
- WhatsApp LID-only identities from access control
- Subscription change history, reminder logs, or delivery records
- Mailbox lookup jobs or delivery logs

Timestamp values use your account time zone. The ZIP filename includes your account name and the generation date.

## How to request an export

1. Go to **Settings > My Account > Data**.
2. Enter your current password when prompted.
3. The system creates your export. Status changes from **Pending** to **Processing** to **Ready**.
4. When ready, click **Download ZIP** to save the file.

Status updates automatically while the Data tab is open.

## Limits

- **Cooldown**: One new export every 24 hours. The countdown shows when the next export is available.
- **Availability**: A ready export remains downloadable for 72 hours. After that, it is automatically deleted.
- **Replacement**: Requesting a new export while one is ready keeps the previous version available until the new one is generated.

## Cancellation

You can cancel a pending or processing export. If you cancel while processing, any partial upload is discarded. The previous ready version (if any) remains available.

## Related

- [Account Deletion](delete-account.md) — Permanently delete your account
