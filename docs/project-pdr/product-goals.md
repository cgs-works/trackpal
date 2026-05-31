# Product Goals & Use Cases

## Overview

Trackpal is a multi-tenant platform that enables a Master operator to manage WhatsApp-based service delivery for streaming account management. The Master creates and manages tenants (service intermediaries), each with their own Evolution WhatsApp instance. Tenants manage clients, catalog, profiles, subscriptions, and mailbox code ingestion through REST, web dashboard, and WhatsApp.

The system bridges three channels: **WhatsApp Console** (chatbot-driven admin), **Web Dashboard** (full CRUD UI), and **Mailbox Ingestion** (automated code extraction from OAuth/IMAP mailboxes).

## Core Use Cases

### Master Console (WhatsApp)

Master interacts via WhatsApp chatbot to:
1. **View tenants** — List all tenants with active/inactive counts and status
2. **Create tenants** — Step-by-step form collecting name, email, phone, username, Evolution instance name, and password
3. **Edit tenants** — Update tenant fields (name, email, phone, Evolution instance)
4. **Deactivate tenants** — Disable tenant login and identification, revoke active sessions
5. **Reactivate tenants** — Restore deactivated tenants
6. **Delete tenants** — Permanently remove inactive tenants plus their Evolution instance and all cascaded data

### Tenant Console (WhatsApp)

Tenant admins interact via WhatsApp chatbot to:
1. **Manage clients** — List, create, edit, deactivate, reactivate, delete own clients
2. **Manage catalog** — View and edit service and plan names
3. **Manage profile** — View and edit own profile data, change password
4. **Manage subscriptions** — List, create, edit, cancel, renew, reactivate, reveal credentials
5. **Access code retrieval** — Multi-step mailbox lookup dialog: select service → enter email → poll for extraction code. Supports mailbox configuration check, IMAP/OAuth mailbox connect, provider-based mail polling with Netflix OTP URL resolution

### Client WhatsApp Console (read-only)

Resolved inside tenant instance scope. Clients can:
1. **View own profile** — Read-only name, phone, username, status
2. **Change own password** — Password update with current-password confirmation
3. **Exit session** — Returns `status="closed"` so n8n closes Evolution session

### Web Dashboard

- **Master Dashboard** (`/master/dashboard`): Full tenant management UI (CRUD, activate/deactivate, delete) with summary cards and modal forms. Includes global code-service activation panel.
- **Tenant Dashboard** (`/admin/dashboard`): Self-service profile + password management, catalog panel, client management panel, subscriptions page, mailbox config panel, code-service selection panel.
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
- Full tenant CRUD with Evolution instance lifecycle
- Catalog management (services, plans), Client management, Subscriptions
- Mailbox config (OAuth + IMAP), Mail lookup jobs (n8n-facing)
- Code-services governance (global + tenant)
- I18n catalog endpoint (en/es)
- Dashboard (role-aware response assembly)

## User Roles

| Role | Capabilities |
|------|-------------|
| **Master** | Full access via WhatsApp Console + REST API + Web Dashboard. Manages all tenants, global code-service activation, system config. One instance. |
| **Tenant** | Manages own profile, catalog, clients, subscriptions, mailbox config, and code-service selection via REST API, WhatsApp Tenant Console, and Web Dashboard. Unlimited tenants. |
| **Client** | Read-only profile view and password management via REST API and WhatsApp Client Console. Tenant-prefixed login (`{prefix}_{local_username}`). |

## User Interaction Channels

| Channel | Master | Tenant | Client |
|---------|--------|--------|--------|
| WhatsApp Console | Full admin (CRUD tenants) | Full admin (clients, catalog, subs, access codes) | Read-only profile + password |
| Web Dashboard | Tenant list + CRUD + global code-services | Profile, catalog, clients, subs, mailbox, code-services | Profile + password |
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
