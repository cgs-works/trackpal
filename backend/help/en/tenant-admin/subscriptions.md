---
id: tenant-admin.subscriptions
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: subscriptions
capabilities:
  - tenant_subscriptions
route: /admin/subscriptions
help_targets:
  - admin.subscriptions
title: Client Subscriptions
summary: Open and manage the subscriptions attached to a client, service, and plan.
search_tags:
  - subscriptions
  - client subscriptions
  - filter subscriptions
  - create subscription
  - cancel subscription
  - renew subscription
  - reactivate subscription
  - reveal credentials
synonyms:
  - memberships
  - client plans
  - service access
order: 120
safe_navigation:
  route: /admin/subscriptions
  settings_category: null
related_topics:
  - tenant-admin.clients
  - tenant-admin.catalog
  - tenant-admin.first-pro-client
tour:
  - release_id: tenant-admin-pro-1
    order: 5
    target: admin.subscriptions
    conditional: false
    plans:
      - pro
    title: Subscriptions and reminders
    content: |
      # Operate subscriptions

      Subscriptions connects Clients to Catalog services and plans. Review statuses, dates, filters, lifecycle actions, credentials boundaries, and the separate reminder settings before taking an action.

      This tour only highlights the real module. It never creates, edits, cancels, renews, reactivates, or reveals credentials.
  - release_id: tenant-admin-pro-upgrade-1
    order: 3
    target: admin.subscriptions
    conditional: false
    plans:
      - pro
    title: Your new Pro Subscriptions module
    content: |
      # Subscriptions are now available

      Your upgrade adds Subscriptions. Use the prepared Client and Catalog data here to manage service access and lifecycle decisions.

      The tour is read-only: it does not create, edit, cancel, renew, reactivate, or reveal credentials.
---

# Client Subscriptions

A Subscription connects one Client to one Catalog service and plan. It records the streaming email, optional profile details, start and expiry dates, and a lifecycle status. Open Subscriptions from the sidebar, or use the subscription action in a Client row to arrive with that Client selected.

## Channels, prerequisites, and list filters

- **Web:** The Pro Subscriptions page lists the Client, service, plan, streaming email, dates, and status. Filter by status, service, or Client; use the visible date and status values before choosing an action.
- **WhatsApp:** From the Pro main menu choose `4` Subscriptions, then `1` View subscriptions. Choose Active, Expired, Cancelled, or All, select a row, and follow the displayed actions.
- **Prerequisites:** Your current plan must include subscription management. Creating requires an active Client plus an existing Catalog service and plan. If the current plan does not include this section, it remains hidden while previously saved data is preserved.
- **Expected result:** A successful create or update returns the subscription to the list with its current status and dates. A Help link only opens this explanation or the safe module route; it never submits a form.

## Create and edit on Web

Choose New subscription and select the Client, service, and plan. Enter the required streaming email. A streaming password is optional; a profile name and profile PIN are also optional, but a PIN requires a profile name. Choose a duration such as 1, 3, 6, or 9 months, 1 year, or a custom expiry date, then review the start and expiry dates before saving.

Edit changes the fields exposed by the form. In edit mode the Client, service, and plan identify the existing relationship; blank password or PIN fields keep the stored value. A changed email, password, profile, duration, or date is not applied until the form saves successfully. A duplicate active subscription for the same Client, service, and streaming email may be reported so you can extend the existing expiry instead of creating another record.

## WhatsApp creation, editing, and navigation

From Subscriptions choose `2` Create subscription. Select the Client, service, and plan, enter the streaming email, optionally enter and confirm the streaming password, choose whether to add a profile name and PIN, select a duration, and enter a custom date when requested. The final creation summary shows the Client, service, plan, email, profile, duration, and dates; type `CONFIRM` or `CONFIRMAR` only after checking it.

For an existing row, the actions are `1` Edit, `2` Cancel, `3` Renew, and `4` Reactivate when the status allows it. Edit can change Client, service, plan, streaming email, streaming password, profile name, or profile PIN. Password and PIN changes are requested twice for confirmation. Use `8` for Next when a page offers it, `9` to go back, and `0` to cancel. Invalid selections keep the flow on its current step; a session timeout does not create a partial subscription.

## Statuses, durations, and lifecycle actions

- **Active:** The subscription is currently usable and can be edited, cancelled, or renewed. A reminder job considers only active subscriptions.
- **Expired:** The expiry date has passed according to the business's local end-of-day automation. It can be renewed or reactivated from the available actions.
- **Cancelled:** Cancellation changes the status and records the cancellation time; it does not immediately delete the row. It can be reactivated with a new duration and dates.

Cancel requires a visible confirmation on Web or a `CONFIRM`/`CONFIRMAR` response in WhatsApp. Renew extends from the current expiry, while Reactivate starts the cancelled subscription again with a new duration or custom date. Both lifecycle actions show the proposed dates before confirmation. Automated expiration and later cleanup are explained in Manage subscription expirations.

## Credentials, empty states, and recovery

The streaming email is not the same as a Client login. Use Reveal credentials on Web only when there is a legitimate operational reason; the dialog can show the stored streaming password and profile PIN. The WhatsApp subscription detail may include the stored access information for the authenticated administrator. Help never activates Reveal, opens a credential dialog, copies a secret, or exposes a credential through a module link.

An empty list can mean that no subscription matches the selected filters; it does not mean the Client or Catalog was deleted. A missing Client, service, or plan prevents creation. An invalid email, date, duration, selection, or confirmation leaves the existing record unchanged. If loading or a mutation fails, read the visible error and retry without sending credentials to support.

## Support boundary

Support can investigate a persistent subscription or lifecycle error from the visible status, dates, and non-sensitive identifiers. Never share streaming passwords, profile PINs, Client passwords, mailbox credentials, access codes, or revealed credentials. Use the Reminder settings and Timezone topics for automated expiry notifications and local-date behavior.
