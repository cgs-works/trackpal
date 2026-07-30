---
id: tenant-admin.delete-account
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: data
capabilities:
  - tenant_delete_account
route: /admin/settings
help_targets:
  - admin.settings.my-account
  - admin.settings.data-tab
  - admin.settings.danger-zone
title: Account Deletion
summary: Permanently delete your TrackPal account and all associated data. This action is immediate and irreversible.
search_tags:
  - delete
  - remove
  - cancel
  - close account
  - offboarding
synonyms:
  - delete account
  - close account
  - cancel account
  - remove account
  - leave trackpal
order: 5
safe_navigation:
  route: /admin/settings
  settings_category: data
safe_links:
  - route: /admin/settings
    settings_category: data
related_topics:
  - tenant-admin.data-export
  - tenant-admin.dashboard
  - tenant-admin.help
---

# Account Deletion

You can permanently delete your TrackPal account and all associated data. This action is immediate and irreversible — there is no grace period or recovery window.

## What gets deleted

- Your account and login credentials
- All client accounts and their login access
- Your service catalog and all plans
- All subscription records and their history
- Mailbox configuration and stored credentials
- Blocked phone list
- Saved preferences (language, time zone)
- Any pending or saved data exports
- Your WhatsApp Evolution instance

## What is NOT deleted by this action

- **Provider OAuth grants**: Google access grants are not revoked. You can manage these from your Google account security settings.
- **Infrastructure backups**: Operational backups and logs follow their standard retention policies. They are used only for disaster recovery and are not accessible after deletion.
- **Ephemeral sessions**: Any active WhatsApp or Web sessions expire within minutes.

## Before you delete

Consider downloading a [Data Export](data-export.md) first. The export gives you a portable copy of your account profile, clients, catalog, and subscription records.

Deletion is available even without an export — the export step is optional.

## How to delete your account

1. Go to **Settings > My Account > Data**.
2. Scroll to the **Danger zone** at the bottom.
3. Click **Delete account permanently**.
4. Enter your current password.
5. Type **DELETE** (or **ELIMINAR** if your account is in Spanish) to confirm.
6. Click **Delete permanently**.

After successful deletion, you are signed out and redirected to the login page. You cannot sign in again with this account.

## What happens during deletion

1. Any in-progress export is cancelled.
2. Stored export files are permanently removed.
3. Your Evolution WhatsApp instance is deleted.
4. Your account and all data are removed from the active database.
5. Your Web session is cleared.

If external cleanup (export removal, Evolution deletion) fails, the account is preserved and you can try again. This prevents partial deletion.

## Related

- [Data Export](data-export.md) — Download your data before deleting
