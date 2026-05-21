# Business Rules & Constraints

## Tenant Lifecycle

1. A tenant is created with `is_active = true`
2. An active tenant can be deactivated; this revokes all active refresh sessions
3. A deactivated tenant cannot log in or be identified by phone
4. A deactivated tenant can be reactivated
5. Only inactive tenants can be deleted
6. Deleting a tenant removes the Evolution API instance and the database record permanently

## Client Lifecycle

1. A client is created by a Tenant and linked to that tenant
2. A client has a `local_username` (e.g. `pepe`) which is combined with the tenant's `client_prefix` (e.g. `t1_`) to form the technical login `t1_pepe`
3. Clients can be deactivated/reactivated; deactivation revokes active sessions
4. Clients can only be managed by their owner Tenant or a Master (via tenant context)

## Authentication

1. Only users with `role = "master"` can access the WhatsApp Master Console
2. Tenant login attempts via WhatsApp console are rejected with role-not-allowed error
3. Failed login attempts are tracked per phone number with a sliding 15-minute window
4. After 5 consecutive failures, the phone is locked out for 5 minutes
5. Successful login resets the failure counter

## WhatsApp Consoles
**Note: Client users have NO WhatsApp console access. Master and Tenant consoles are separate.**

### Master Console
1. Available only via the n8n webhook integration (not directly)
2. All messages are relayed through Evolution API -> n8n -> Backend
3. Backend always returns HTTP 200 to n8n, even during infrastructure failures
4. Conversation state is ephemeral (Redis), never persisted to the database
5. TTL refreshes only on valid progress, not on noise or error input
6. Master phone number is identified via the `POST /api/v1/integrations/n8n/console` endpoint

### Tenant Console
1. Available only to users with `role = "tenant"`
2. Phone-based auto-auth via `POST /api/v1/integrations/n8n/identify`
3. Uses same Evolution API -> n8n -> Backend relay
4. Conversation state is ephemeral in Redis under `session:admin:{phone}`
5. `0` at top level exits; `0` inside a flow cancels the active operation

## Phone Number Handling

1. All phone numbers are stored in canonical digits-only format (no `+` prefix)
2. WhatsApp JID suffixes (`@c.us`, `@s.whatsapp.net`) are stripped before storage and lookup
3. Device suffixes (`:N`) are stripped before storage and lookup
4. Phone lookup checks both canonical and `+`-prefixed variants for backward compatibility
5. Phone uniqueness is per-role (master and tenant can share the same phone number)

## Evolution API

1. Each tenant gets one Evolution API instance, prefixed with `tenant-`
2. Instance creation is part of tenant creation (rolled back on failure)
3. Instance deletion is part of tenant deletion
4. Changing `evolution_instance_name` does not recreate or rename the Evolution instance
5. When Evolution API is not configured, all operations are no-ops with a warning log

## Input Validation

1. All field validation goes through the centralized `app/core/input_validation.py`
2. Usernames: max 20 chars, lowercase + digits + underscores, must start with a letter
3. Full names: Unicode letters, digits, and spaces only (no punctuation)
4. Emails: validated via `email_validator` (syntax only, no deliverability check)
5. Client Local Usernames: Must be unique within the tenant; used to build technical login
6. Phones: validated as international E.164 format via `phonenumbers` library

## Deployment Constraints

1. Backend runs on Render free tier (web service)
2. PostgreSQL database (external, configured via `DATABASE_URL`)
3. Redis primary + backup (optional; console works in degraded mode without Redis)
4. Frontend hosted on Cloudflare Pages

## Subscription Lifecycle

1. Subscriptions belong to a tenant, client, service, and plan.
2. Streaming password and PIN are encrypted at rest.
3. `starts_at` is stored explicitly and `expires_at` is derived from duration or custom dates.
4. Cancelled subscriptions keep history via events and reminder logs.
5. Reminder jobs run through n8n using the subscription reminders workflow.
