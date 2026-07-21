---
id: client.profile
audience: client
plans:
  - pro
channels:
  - web
module: profile
capabilities:
  - client_profile
route: /client/profile
help_targets:
  - client.profile
title: Client Profile
summary: Review the profile and provider information associated with your Client account.
search_tags:
  - profile
  - name
  - username
  - phone
  - provider
synonyms:
  - account details
  - personal information
order: 20
safe_navigation:
  route: /client/profile
  settings_category: null
related_topics:
  - client.dashboard
  - client.password
  - client.whatsapp
---

# Client Profile

Profile is a read-only view of the information associated with your Client account.

## Channel, prerequisites, and actions

- **Channel:** Web. Open Profile from the Client navigation after signing in.
- **Prerequisites:** Your Client account must be active under a Pro Tenant.
- **Actions:** Review your full name, username, phone when available, provider, and active status. You cannot edit these fields from the Client profile.

## Results and states

A blank phone or provider value means that information is not configured or is unavailable. An active status means the account can use the Client surfaces. If the profile request fails, use Retry; do not refresh by repeatedly submitting any form because Profile has no save action.

## Web and WhatsApp

The Web Profile page is the authoritative read-only view. WhatsApp can show a Client profile summary during a Client console session, but WhatsApp cannot edit profile fields. Ask the provider to correct a name, phone, or access status.

## Support boundary

Only the provider can update Client identity and access data. Do not share your password or private account details in a support request.
