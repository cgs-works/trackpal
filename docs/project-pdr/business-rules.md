# Business Rules & Constraints

## Tenant Lifecycle

1. A tenant is created with `is_active = true`
2. An active tenant can be deactivated; this revokes all active refresh sessions
3. A deactivated tenant cannot log in or be identified by phone
4. A deactivated tenant can be reactivated
5. Only inactive tenants can be deleted
6. Deleting a tenant removes the Evolution instance and the database record permanently

## Client Lifecycle

1. A client is created by a Tenant and linked to that tenant
2. A client has a tenant-local username segment (e.g. `pepe`) combined with tenant `client_prefix` (e.g. `t1_`) to form canonical login `t1_pepe`
3. Clients can be deactivated/reactivated; deactivation revokes active sessions
4. Clients can only be managed by their owner Tenant or a Master (via tenant context)

## Authentication

1. Only users with `role = "master"` can access the WhatsApp Master Console
2. Tenant login attempts via WhatsApp console are rejected with role-not-allowed error
3. Failed login attempts are tracked per phone number with a sliding 15-minute window
4. After 5 consecutive failures, the phone is locked out for 5 minutes
5. Successful login resets the failure counter

## WhatsApp Consoles
**Note: System exposes Master, Tenant, and Client WhatsApp consoles through same n8n integration endpoint.**

### Master Console
1. Available only via the n8n webhook integration (not directly)
2. All messages are relayed through Evolution -> n8n -> Backend
3. Backend always returns HTTP 200 to n8n, even during infrastructure failures
4. Conversation state is ephemeral (Redis), never persisted to the database
5. TTL refreshes only on valid progress, not on noise or error input
6. Master phone number is identified via the `POST /api/v1/integrations/n8n/console` endpoint

### Tenant Console
1. Available to tenant identities resolved by instance-first routing (`POST /api/v1/integrations/n8n/console`)
2. Uses same Evolution -> n8n -> Backend relay
3. Conversation state is ephemeral in Redis under `session:admin:{phone}`
4. Navigation contract: `9` = back in interactive flows, `0` = global exit only

### Client Console
1. Read-only console for active clients resolved inside tenant instance scope
2. Client identities are resolved by `(tenant_id, phone)` and optional `whatsapp_lid` fallback
3. Navigation contract matches tenant/master: `9` back, `0` global exit
4. Exit responses include `status="closed"` so n8n can close Evolution session

## Phone Number Handling

1. All phone numbers are stored in canonical digits-only format (no `+` prefix)
2. WhatsApp JID suffixes (`@c.us`, `@s.whatsapp.net`) are stripped before storage and lookup
3. Device suffixes (`:N`) are stripped before storage and lookup
4. Phone lookup checks both canonical and `+`-prefixed variants for backward compatibility
5. Phone uniqueness is per-role (master and tenant can share the same phone number)

## Evolution

1. Each tenant gets one Evolution instance, prefixed with `tenant-`
2. Instance creation is part of tenant creation (rolled back on failure)
3. Webhook is registered per-instance with defensive upsert (`create` → `find` → `update`)
4. Instance token is encrypted via app-layer Fernet (`DATA_ENCRYPTION_KEY`) and stored in `tenants.evolution_instance_token`
5. Decryption happens only at runtime for subscription reminders send auth
6. Session closing is handled by n8n via `POST /webhook/change-status` (backend `close_chat_session` is deprecated no-op)
7. Outbound messages use `POST /send/text` with per-instance token auth
8. Instance deletion is part of tenant deletion
9. Changing `evolution_instance_name` does not recreate or rename the Evolution instance
10. When Evolution is not configured, all operations are no-ops with a warning log

**Note**: The deployed server may run Evolution API v2.x (Node/Express) or Evolution Go (Go/Gin). The `EvolutionClient` is version-agnostic for the endpoints used (`/instance/create`, `/webhook/*`, `/send/text`). Always verify the deployed version via `GET $BASE_URL/` when debugging contract mismatches.

## Input Validation

1. All field validation goes through the centralized `app/core/input_validation/`
2. Usernames: max 20 chars, lowercase + digits + underscores, must start with a letter
3. Full names: Unicode letters, digits, and spaces only (no punctuation)
4. Emails: validated via `email_validator` (syntax only, no deliverability check)
5. Client username local segment: unique within tenant; used to build canonical login username
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
