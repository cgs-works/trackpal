# Product Goals & Use Cases

## Overview

TrackPal is a multi-tenant platform that enables a Master operator to manage WhatsApp-based service delivery for streaming account management. The Master creates and manages tenants (service intermediaries), each with their own Evolution WhatsApp instance. Tenants manage clients, catalog, profiles, subscriptions, and mailbox code ingestion through REST, web dashboard, and WhatsApp.

The system bridges three channels: **WhatsApp Console** (chatbot-driven admin), **Web Dashboard** (full CRUD UI), and **Mailbox Ingestion** (automated code extraction from OAuth/IMAP mailboxes).

## Core Use Cases

### Master Console (WhatsApp)

Master interacts via WhatsApp chatbot to:
1. **View tenants** — List all tenants with active/inactive counts and status
2. **Create tenants** — Step-by-step form collecting name, email, phone, username, Evolution instance name, and password
3. **Edit tenants** — Update tenant fields (name, email, phone, Evolution instance)
4. **Deactivate tenants** — Disable tenant login and identification, revoke active sessions
5. **Reactivate tenants** — Restore deactivated tenants
6. **Delete tenants** — Permanently remove inactive tenants plus their Evolution instance and all cascaded data. **Note**: Master deletion now requires password step-up and locale-aware destructive word confirmation (ELIMINAR/DELETE)

### Demo Account Evaluations (Web)

Master creates and manages bounded Starter or Pro evaluations from the dedicated Demos tab. The first successful Demo Credentials login starts one non-extendable 48-hour period. The backend stores identity and lifecycle only; realistic business changes and simulator operations remain isolated in a versioned browser-local Demo Workspace. Direct business, integration, Public API, export, and self-deletion requests are blocked server-side.

Starter demos preserve Starter navigation and provide the contained access-code Request simulator. Pro demos add local Clients, Catalog, Subscriptions, derived dashboards, plan-correct Settings, and Client/Tenant Admin console simulations. Both plans provide Help, password change, lifecycle heartbeat, reset, bilingual UI, and the neutral Demo Ended route without provisioning Evolution, n8n, mailbox, OAuth, Public API, or export resources.

### Tenant Console (WhatsApp)

Tenant Admin capabilities are plan-aware:

- **Starter**: manage own profile and language, search for access codes, manage WhatsApp access blocks, view help, and exit the console.
- **Pro**: all Starter capabilities plus client, catalog, and subscription management.

The implemented Pro menu supports:
1. **Manage clients** — List, create, edit, deactivate, reactivate, and delete own clients
2. **Manage catalog** — List, create, rename, and delete services and plans
3. **Manage profile** — View and edit identity data, change password, and change language
4. **Manage subscriptions** — List, filter, create, edit, cancel, renew, and reactivate subscriptions
5. **Manage access control** — List blocked identities, block a phone, and unblock through the client-management flows
6. **View help** — Review menu and navigation commands
7. **Access code retrieval** — Select a configured service, confirm the target email, and poll the connected mailbox for an extraction result

### Client WhatsApp Console (read-only)

Resolved inside a Pro tenant instance scope. Clients can:
1. **View own profile** — Read-only name, provider, phone, and status
2. **View active subscriptions** — Read-only service, plan, dates, and status
3. **Search for an access code** — Enter the tenant's mailbox lookup flow for an enabled service
4. **Exit session** — Returns `status="closed"` so n8n closes the Evolution session

Client password changes are available through the authenticated Web Dashboard, not the Client WhatsApp Console.

### Web Dashboard

- **Master Dashboard** (`/master/dashboard`): Separate Production and Demos tabs. Production provides Tenant CRUD, activate/deactivate/delete, summary cards, global code-service activation, support context, and export. Demos provides lifecycle-only creation, credential replacement, status/search, and deletion without workspace preview or telemetry.
- **Tenant Dashboard** (`/admin/dashboard`): Self-service profile + password management, catalog panel, client management panel, subscriptions page, mailbox config panel, code-service selection panel, access-control settings, WhatsApp self-linking configuration, My Account with Data tab for Tenant Data Export and Tenant Admin self-service deletion.
- **Client Dashboard** (`/client/dashboard`): Read-only profile view and password change for end-customers.

### Mailbox Ingestion (automated)

System features a fully automated mailbox code-extraction pipeline:
1. **Mailbox config** — Tenant connects mailbox via OAuth (Google/Microsoft) or IMAP app password
2. **Code extraction** — When a WhatsApp user requests an access code, system creates a lookup job and polls the connected mailbox for incoming messages from known streaming services, extracts codes via regex catalogs
3. **Netflix OTP resolution** — For Netflix, resolves travel-verify URLs by fetching the OTP page and extracting the challenge code via HTML parsing
4. **Delivery logging** — All extractions logged with deduplication (by `message_id`) to prevent re-delivery of the same code
5. **Cleanup** — Periodic cleanup expires stale jobs and rotates credentials

### Subscription Reminders (automated)

Daily n8n-triggered job:
1. **Reminder generation** — Finds subscriptions expiring within warning_days (default 7, 3, 1 day before expiry)
2. **WhatsApp delivery** — Sends Spanish reminder message to tenant (and optionally client) via Evolution
3. **Lifecycle transitions** — Auto-expire → auto-cancel (7d after expiry) → auto-delete (30d after cancel)

### Code-Services Governance

Master can globally toggle supported code-extraction services (e.g. netflix, hbo). Tenants select from active services which ones appear in their WhatsApp access code retrieval. Effective set = tenant selection ∩ global active services.

### REST API

Programmatic access for frontend SPA and n8n integration:
- JWT-based authentication with access/refresh token rotation and logout revocation
- Role-based authorization (master vs tenant vs client)
- Full tenant CRUD with Evolution instance lifecycle (deletion requires password step-up and destructive word)
- Catalog management (services, plans), Client management, Subscriptions
- Mailbox config (OAuth + IMAP), Mail lookup jobs (n8n-facing)
- Code-services governance (global + tenant)
- WhatsApp self-linking lifecycle management (status, pairing code, QR, disconnect) for Starter and Pro tenants
- I18n catalog endpoint (en/es)
- Dashboard (role-aware response assembly)
- **Tenant Data Export**: self-service (`/me/export/*`) and Master-scoped (`/tenants/{id}/export/*`) endpoints with password step-up
- **Tenant Admin self-deletion**: `/me/delete-account` with password step-up and destructive word confirmation
- **Master Tenant Deletion**: `/tenants/{id}/delete` with password step-up and destructive word confirmation

## User Roles

| Role | Capabilities |
|------|-------------|
| **Master** | Full access via WhatsApp Console + REST API + Web Dashboard. Manages production Tenants, global code-service activation, system config, and web-only Demo Tenant lifecycle. Can export active or inactive production Tenant data. Deletes inactive production Tenants with password step-up and destructive word confirmation; Demo deletion uses its separate bounded lifecycle contract. |
| **Tenant Admin** | Operates one tenant through plan-aware Web and WhatsApp administration. Starter covers profile, WhatsApp, mailbox code lookup, code-service selection, and access control; Pro adds clients, catalog, subscriptions, reminders, timezone, and Public API Catalog. Can export business data (all plans) and permanently self-delete the Tenant (My Account Data tab, password step-up + destructive word). |
| **Client** | For Pro tenants, views own profile and active subscriptions through Web and WhatsApp, searches for access codes through WhatsApp, and changes password through Web. Uses a tenant-prefixed login (`{prefix}_{local_username}`). |

## User Interaction Channels

| Channel | Master | Tenant | Client |
|---------|--------|--------|--------|
| WhatsApp Console | Full admin (CRUD tenants) | Plan-aware administration: profile, access codes, access control, and help; Pro also includes clients, catalog, and subscriptions | Read-only profile and active subscriptions, plus access-code search |
| Web Dashboard | Production Tenant management + Demo lifecycle management + global code-services | Plan-aware production administration or contained browser-local Demo Workspace | Read-only profile and active subscriptions, plus password change |
| REST API | Full | Self-scoped | Read-only self |
| Mailbox Ingestion | N/A | Configure mailbox, access code retrieval | N/A |

## Non-Goals

- Self-registration: Tenants are created only by the Master
- Client WhatsApp console: Clients have read-only access, no catalog/subscription management
- Multi-language: All user-facing text supported in both **Spanish (default)** and **English**, selected per-tenant via locale setting
- Public registration pages: No signup, forgot-password, or invite flows
- Native mobile apps: All interaction via WhatsApp + Web SPA
- Payment processing: No billing amounts, invoices, or credits tracked in the subscription system
- Evolution instance renaming: Changing `evolution_instance_name` does not recreate or rename the instance
- Webhook for mail delivery: Delivery is pull-based via n8n polling job status; no push webhook
- **WhatsApp Console export or deletion**: Self-service export and deletion are Web Dashboard capabilities only
- **Email or WhatsApp delivery of export**: Exports are downloaded via authenticated Web session only
- **Export restoration or import**: The export contract is not designed as an import contract
- **Revoking provider OAuth grants**: Local credentials are deleted; Google/Microsoft grants are not revoked
- **Grace period or recovery window**: Tenant Admin deletion is immediate with no pending-deletion state
- **Selective infrastructure cleanup**: Backups and logs follow operational retention; no per-Tenant purge
