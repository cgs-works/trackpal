---
id: tenant-admin.mailbox
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: settings
capabilities:
  - tenant_mailbox
route: /admin/settings
help_targets:
  - admin.settings.mailbox
title: Central mailbox for access codes
summary: Connect the inbox that receives emails containing access codes.
search_tags:
  - mailbox
  - email inbox
  - Gmail
  - Google
  - connection test
  - access-code email
  - app password
synonyms:
  - code mailbox
  - central inbox
  - email connection
order: 70
safe_navigation:
  route: /admin/settings
  settings_category: mailbox
related_topics:
  - tenant-admin.activate-access-code-lookup
  - tenant-admin.code-services
  - tenant-admin.whatsapp
---

# Central mailbox for access codes

TrackPal checks this mailbox when someone requests an access code in WhatsApp. Use an inbox managed by the business, not a client's personal email.

## Connect your Gmail inbox

1. Go to [App passwords](https://myaccount.google.com/apppasswords) and make sure **2-Step Verification** is enabled on your Google Account.
2. If 2-Step Verification is not enabled, follow Google's guide at [2-Step Verification help](https://support.google.com/accounts/answer/185833) to activate it first.
3. On the App passwords page, select **Mail** as the app and **Other (Custom name)** as the device. Enter a name like "TrackPal" and click **Generate**.
4. Copy the 16-character password that appears.
5. In TrackPal, go to **Settings > Mailbox** and click **I have an app password**. This opens the Gmail app-password connection form.
6. Enter your Gmail address and paste the app password you generated.
7. Click **Test connection**. When the status shows **Connected**, your mailbox is ready.

## App password eligibility

You can generate an app password only when **2-Step Verification** is enabled on your Google Account. If you don't see the App passwords option, check the following:

- **2-Step Verification is not enabled.** Follow Google's guide to activate it first.
- **Work or school account.** Google Workspace accounts may not have app passwords available. Contact your administrator.
- **Advanced Protection Program.** Accounts enrolled in Advanced Protection cannot generate app passwords. You must use a different account.

If none of these apply and you still can't find the option, visit Google's [2-Step Verification help](https://support.google.com/accounts/answer/185833) for additional troubleshooting.

## Important security notes

- **Do not use your normal Gmail password.** Always use an app password for the connection.
- If you change your Google Account password, the app password is automatically revoked. You'll need to generate a new one and reconnect.
- If you lose access, generate a new app password at [App passwords](https://myaccount.google.com/apppasswords) and update the connection in TrackPal.

## If the connection fails

Review the visible message and test again. Make sure you're using an app password, not your regular password. If the connection was working before and stopped, check whether your Google Account password was changed — this revokes all app passwords.
