# User Help and Tenant Orientation Requirements

## Purpose

This document defines the approved product requirements for TrackPal's private in-app manuals and the Tenant Admin orientation tour. It is an **explanation and product requirements document** for product, design, documentation, and engineering contributors.

The system must describe only capabilities that are implemented and available to the authenticated audience. Planned or incomplete behavior must not appear as current functionality.

Implementation is tracked in [GitHub Issue #81](https://github.com/cgs-works/trackpal/issues/81).

## Terminology

- **Tenant**: the business entity using TrackPal.
- **Tenant Admin**: the person who operates that Tenant.
- **Client**: an end customer of a Pro Tenant.
- **Manual**: authenticated, searchable help rendered from repository Markdown.
- **Orientation Tour**: the optional first-login Web walkthrough for a Tenant Admin.
- **Tour Release**: a versioned, plan-aware set of orientation steps that a Tenant can complete or skip.

## Audiences and Channels

TrackPal will provide two separate manuals:

1. **Tenant Admin Manual**
2. **Client Manual**

Both manuals cover Web and WhatsApp, with separate instructions for each channel. The manuals must be available in Spanish and English and follow the authenticated user's locale.

The Orientation Tour is only for Tenant Admins. Clients receive a manual but no tour. Master users, including Master Support Context, receive neither these manuals nor this tour.

## Publication and Privacy

- Manuals are available only after authentication.
- Help content must not be included in public Vite assets.
- Repository Markdown is the only editable prose source for the in-app manuals.
- The first release is atomic: both manuals, both locales, search, plan filtering, contextual help, the tour, contracts, and required QA must be ready before the feature is exposed.
- No PDF, public documentation site, public share link, screenshot library, or runtime machine translation is part of this design.

## Current Capability Scope

### Tenant Admin Web

All plans:

- Dashboard with plan, mailbox status, enabled code-service count, and access-control count
- Language
- WhatsApp linking, status, pairing code, QR code, and disconnect
- Enabled code platforms
- Central lookup mailbox through OAuth or IMAP, connection test, and disconnect
- WhatsApp access control: list, search, block, and unblock
- Profile identity fields
- Password change

Pro only:

- Clients: search, create, edit, activate, deactivate, delete, and open client subscriptions
- Catalog: create, rename, and delete services and plans, including delete impact preview
- Subscriptions: filter, create, edit, cancel, renew, reactivate, and reveal credentials
- Reminder settings
- Timezone
- Public API Key and Allowed Origins for Public API Catalog

### Tenant Admin WhatsApp

Starter menu:

- `1`: Profile
- `2`: Access-code search
- `3`: Access control
- `4`: Help
- `0`: Exit

Pro menu:

- `1`: Clients
- `2`: Catalog
- `3`: Profile
- `4`: Subscriptions
- `5`: Access control
- `6`: Help
- `7`: Access-code search
- `0`: Exit

The manual must also cover WhatsApp navigation (`0`, `8`, `9`), mailbox and enabled-platform prerequisites, session timeout, and safe recovery from invalid input.

### Client Web

Clients of Pro Tenants can:

- View profile and provider information
- View active subscriptions
- Change their password

### Client WhatsApp

Clients of Pro Tenants can:

- View their profile
- View active subscriptions
- Search for an access code through the Tenant's configured mailbox flow
- Exit the console

Client password changes are Web-only. Client login and manuals are unavailable while the Tenant is on Starter, although Client data is preserved.

## Manual Information Architecture

The primary index is organized by the modules and menus users can actually see. Each module chapter lists its actions, prerequisites, plan and channel availability, states, limits, consequences, recoverable errors, and support boundary.

Cross-module how-to guides supplement the module index instead of replacing it.

### Tenant Admin Manual

1. Dashboard
2. Clients (Pro)
3. Catalog (Pro)
4. Subscriptions (Pro)
5. Settings
   - Reminder settings (Pro)
   - Language
   - Timezone (Pro)
   - Public API Key (Pro)
   - WhatsApp
   - Enabled platforms
   - Central lookup mailbox
   - Access control
   - Profile
   - Password
6. WhatsApp Console
   - Starter menu
   - Pro menu
   - Navigation and sessions
   - Client Context Shortcut (Pro)
7. Cross-module guides
   - Activate access-code lookup
   - Set up the first Pro Client
   - Manage subscription expirations
   - Publish the Public API Catalog
8. States, limits, security, and troubleshooting
9. Module and action reference

The Public API Catalog chapter includes a developer handoff appendix. The Tenant Admin can copy a package of instructions and code snippets to share through an external channel. TrackPal must never insert the Tenant's actual Public API Key into that package automatically.

### Client Manual

1. Dashboard
2. Profile
3. Active subscriptions
4. Password change on Web
5. WhatsApp Console
   - Profile
   - Active subscriptions
   - Access-code search
   - Navigation and exit
6. States, security, and troubleshooting
7. Available-action reference

## Topic Content Standard

Each topic must:

- Use the exact current product label in the selected locale.
- Explain TrackPal-specific concepts for beginners without explaining obvious browser controls.
- Separate Web and WhatsApp steps.
- State audience, plan, prerequisites, and expected result.
- Cover empty, loading, unavailable, validation, success, and recoverable error states where applicable.
- Explain destructive or sensitive consequences before their steps.
- Link to related topics and to authorized TrackPal modules.
- Avoid screenshots; contextual help and the Orientation Tour point to the real UI.
- Avoid undocumented workarounds, planned behavior, REST internals, and implementation details.

## In-App Help Experience

### Permanent entry

Tenant Admin and Client navigation includes **Help** at the bottom of the sidebar, separated from operational modules and placed before the account/logout area.

Desktop and mobile layouts must expose equivalent navigation. The current Admin and Client mobile headers lack module navigation, so a shared, role-aware mobile navigation drawer is a prerequisite for this feature.

### Help Center

Desktop layout:

- Existing application sidebar
- Help-topic navigation and full-text search
- Main article column limited to approximately 65–75 characters
- On-page table of contents on wide screens

Mobile layout:

- Full-width article
- Search at the top
- Topic navigation in a Sheet

Search covers titles, tasks, actions, states, errors, and maintained synonyms. Results are always filtered by authenticated role, current plan, and locale.

### Contextual help

“Help about this screen” opens the exact topic in a side panel so unsaved local form state is not lost. On mobile, the panel becomes an appropriate Sheet. The full Help Center remains a dedicated route.

Manual links may navigate to authorized modules and safely open a Settings category. They must never submit a form, reveal credentials, or execute a mutation.

## Orientation Tour

### Goal

The tour's “aha moment” is a clear operational map: the Tenant Admin understands which modules are included in the current plan, where actions live, and how Web, WhatsApp, enabled platforms, and the central mailbox relate.

The audience is assumed to be beginner-level. The welcome step promises **2–3 minutes**.

### Trigger and lifecycle

- Start automatically on the first successful Tenant Admin Web login for an unseen eligible Tour Release.
- Never start for Master Support Context or Client sessions.
- Remain optional and replayable from Help.
- Closing the tour means skipping that Tour Release, but requires a short confirmation that explains how to replay it.
- Store completed and skipped Tour Release IDs at Tenant scope, not user scope.
- Do not store extra product analytics.

### Updates and plan changes

- Existing Tenants see only eligible feature-announcement releases, not the complete initial tour again.
- A Starter-to-Pro upgrade triggers a Pro-new-capabilities Tour Release even if the initial Starter tour was skipped.
- After a Pro-to-Starter downgrade, show a notice explaining that Pro data is preserved and automation is paused, then show the normal Starter-filtered manual. Do not launch a downgrade tour.

### Interaction rules

- Maximum seven total steps.
- Follow the real navigation order.
- Use the real Tenant UI and real data.
- Adapt to empty states; highlight first-action controls and omit unavailable targets rather than inventing data.
- Navigate across routes and open safe informational panels when needed.
- Never create, save, delete, cancel, disconnect, revoke, reveal secrets, or open destructive confirmations.
- Explain sensitive and destructive actions in copy without activating them.
- Summarize WhatsApp capabilities from the Web WhatsApp Settings step and link to the WhatsApp manual chapter.
- Provide Back, Next, progress, Skip/Close, Done, and “Learn more” controls.
- Desktop uses an anchored popover. Mobile preserves the spotlight and uses a stable bottom Sheet for explanation and controls.
- Keyboard operation, visible focus, screen-reader labels, WCAG 2.2 AA contrast, and reduced-motion behavior are required.

### Approved Starter sequence

1. Welcome, Starter plan, purpose, and duration
2. Dashboard and available navigation
3. Account: language, profile, and password
4. WhatsApp linking and Starter console summary
5. Enabled platforms, central mailbox, and access-code lookup
6. Access control
7. Help Center and replaying the tour

### Approved Pro sequence

1. Welcome, Pro plan, purpose, and duration
2. Dashboard and navigation map
3. Clients and their action group
4. Catalog services and plans
5. Subscriptions and reminders
6. Settings: language, timezone, Public API Key, platforms, mailbox, access control, profile, and security
7. WhatsApp summary, Help Center, and replaying the tour

## Failure Behavior

- If the private Help API is unavailable, TrackPal remains usable, the tour does not start, Help shows a retry state, and the Tour Release is not acknowledged.
- If frontend and Help artifact versions are incompatible, the authorized manual remains available but the tour is disabled until versions and targets match.
- Missing optional runtime targets are skipped only when the release explicitly declares them conditional. An unexpected missing required target is a QA failure and stops the tour safely without acknowledging the release.
- Help caches must clear on logout, login, role change, and Tenant context change.

## Fidelity and Release Gates

Implemented product behavior, verified by current code and tests, is the source of truth. Existing documentation must be corrected when it contradicts implemented behavior. Planned functionality is documented only after it ships.

CI must block:

- Invalid or duplicate capability IDs
- Invalid frontmatter
- Spanish/English topic or metadata mismatch
- Unknown role, plan, channel, route, action, Tour Release, or `data-help-id`
- Broken internal links
- Unsafe Markdown or raw HTML
- Help artifact schema incompatibility
- Missing unit and API contract coverage

The approved decision does not add browser E2E tests. Therefore every Help release requires a mandatory manual QA matrix covering:

- Tenant Admin Starter: desktop and mobile, Spanish and English
- Tenant Admin Pro: desktop and mobile, Spanish and English
- Client manual: desktop and mobile, Spanish and English
- Initial, skipped, replayed, feature-update, upgrade, downgrade, API-failure, and version-mismatch states
- All seven tour steps, route transitions, safe panels, keyboard controls, reduced motion, and required targets

## Non-Goals

- Client or Master orientation tours
- Help in Master Support Context
- Public manuals or unauthenticated login help
- PDF manuals or screenshot-based instructions
- A full private REST API reference
- Runtime-editable help content
- Runtime machine translation
- Tutorial or demo data
- Mandatory setup tasks or activation checklist
- Detailed help analytics
- Automated browser E2E tests in the first design
