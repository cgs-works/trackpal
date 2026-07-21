# Business Rules & Constraints

## Tenant Lifecycle

1. Tenant created with `is_active = true`
2. Active tenant can be deactivated; this revokes all active refresh sessions for all users belonging to that tenant
3. Deactivated tenant cannot log in (REST or WhatsApp) or be identified by phone
4. Deactivated tenant can be reactivated; login reverts to normal behavior
5. Only inactive tenants can be deleted
6. Deleting a tenant is permanent: removes Evolution instance via API, cascades to delete all owned data (clients, catalog, subscriptions, mailbox config, lookup jobs, settings)
7. Changing `evolution_instance_name` does not recreate or rename the Evolution instance (field is for reference only)

## Client Lifecycle

1. Client created by a Tenant (or Master in tenant context) and linked to that tenant
2. Client has a tenant-local username segment (e.g. `pepe`) combined with tenant `client_prefix` (e.g. `t1_`) to form canonical login `t1_pepe`
3. `client_prefix` is unique across all tenants, lowercase, max 5 chars, set at tenant creation (immutable)
4. Both `clients.local_username` and the generated canonical `users.username` are wrote simultaneously and kept in sync (username rename updates both rows transactionally)
5. Clients can be deactivated/reactivated; deactivation revokes all active refresh sessions
6. Clients can only be managed by their owner Tenant or a Master (via tenant context / `active_tenant_id`)

## Authentication & Authorization

1. Users authenticate with `role = "master"`, `"tenant"`, or `"client"` — roles are set at creation and immutable
2. Only masters can access WhatsApp Master Console; tenant login via master WhatsApp is rejected with role-not-allowed error
3. JWT access token: short-lived (default 15 min). Refresh token: long-lived, consumed on use via **rotation** (old token invalidated on each refresh)
4. Logout explicitly revokes the refresh token (deletes from DB)
5. Failed WhatsApp login attempts tracked per phone number: sliding 5-minute window, max 5 consecutive failures. After lockout, phone is blocked for 5 minutes. Successful login resets counter.
6. REST API authentication uses JWT Bearer token. n8n integration uses `X-API-Key` header (validated by `verify_n8n_api_key` dependency).
7. Master can switch tenant context via `POST /api/v1/auth/switch-tenant` with `active_tenant_id`. This embeds `active_tenant_id` in the JWT, granting tenant-scoped access without re-authentication.

## WhatsApp Console Routing

1. All WhatsApp messages arrive via Evolution webhook → n8n → backend `POST /api/v1/integrations/n8n/console`
2. Routing is **instance-first**: the `instance` field from the Evolution payload identifies which tenant the message belongs to
3. `MASTER_WHATSSAPP_INSTANCE` env var identifies the Master's dedicated instance (reserved, must match exactly)
4. All other instance names are looked up in `tenants.evolution_instance_name` to resolve the tenant
5. Within a tenant instance, identity resolution:
   - **Tenant admin**: matched by tenant `whatsapp_phone`
   - **Client**: matched by `(tenant_id, phone)` in `clients.whatsapp_phone`
   - **LID fallback**: if phone not found, try `whatsapp_lid` (first master, then tenant, then clients within tenant scope)
   - Client exit returns `status="closed"` so n8n can close Evolution session
6. All messages get HTTP 200 to n8n even during infrastructure failures (fire-and-forget contract for retry avoidance)
7. Conversation state is ephemeral in Redis, never persisted to database
8. TTL refreshes only on valid user progress, not on noise or error input

## WhatsApp Console Navigation

1. Global navigation pattern across all consoles: `0` = Cancelar (cancel flow/close console), `9` = Regresar (back to previous screen), `8` = Siguiente (next page/screen)
2. Error input shows error message and re-prompts current step (does not reset conversation)
3. Inactivity timeout clears session from Redis; next message starts fresh from main menu
4. Master menu: 1=Ver empresas, 2=Crear empresa, 3=Desactivar empresa, 4=Eliminar empresa, 5=Ayuda, 0=Cancelar/Cerrar sesion
5. Starter Tenant Admin console: 1=Mi perfil, 2=Buscar código de acceso, 3=Control de acceso, 4=Ayuda, 0=Salir
6. Pro Tenant Admin console: 1=Clientes, 2=Catálogo, 3=Mi perfil, 4=Suscripciones, 5=Control de acceso, 6=Ayuda, 7=Buscar código de acceso, 0=Salir
7. Client console: 1=Ver perfil, 2=Ver suscripciones activas, 3=Buscar código de acceso, 0=Cancelar
8. Tenant Admin access code retrieval: select service → enter and confirm email → system creates lookup job → polling loop until code extracted, an error occurs, or the user exits
8. Shared module `app/services/whatsapp_navigation.py` implements the contract with `is_cancel()`, `is_back()`, `is_next()` and screen-stack helpers

## Contingency Reply Policy (Redis Degradation)

1. When both Redis primary and backup are unavailable, WhatsApp Console returns deterministic plain-text replies instead of menu state
2. **Session reset** (`SESSION_RESET`): Informs user of temporary contingency and resets to main menu options (works without Redis)
3. **Temporary unavailable** (`TEMPORARY_UNAVAILABLE`): Short message asking user to retry later
4. These replies are compatible with the existing `WhatsAppConsoleResponse.reply` schema — n8n relays them without workflow changes
5. No state is persisted; user will restart from menu on next message after recovery

## Phone Number Handling

1. All phone numbers stored in canonical digits-only format (no `+` prefix, no spaces, no dashes)
2. WhatsApp JID suffixes (`@c.us`, `@s.whatsapp.net`) stripped before storage and lookup
3. Device suffixes (`:N`) stripped before storage and lookup
4. Phone lookup checks canonical form; no `+`-prefixed backward compatibility (deprecated)
5. Phone uniqueness is **per-role**: master and tenant can share the same phone number (different roles, different consoles)

## LID Identity Resolution

1. `whatsapp_lid` columns added to `master_profiles`, `tenants`, and `clients` for LID fallback
2. Resolution priority inside a tenant instance:
   - Phone match on tenant `whatsapp_phone` → tenant admin
   - Phone match on client `whatsapp_phone` → client
   - LID match on tenant `whatsapp_lid` → tenant admin (for `@lid` senders who change numbers)
   - LID match on client `whatsapp_lid` → client
3. LID is stored as `@lid` value without the `@lid` suffix in DB; lookup appends it for matching

## Evolution Integration

1. Each tenant gets one Evolution instance, prefixed with `tenant-` (e.g. `tenant-acme`)
2. `MASTER_WHATSSAPP_INSTANCE` is a reserved instance name for the Master console (no prefix convention enforced)
3. Instance creation is part of tenant creation (rolled back if creation fails)
4. Webhook registered per-instance with defensive upsert: `create` → `find` → `update` flow
5. Instance token (`evolution_instance_token`) encrypted via app-layer Fernet using `DATA_ENCRYPTION_KEY` and stored in `tenants` table
6. Decryption happens only at runtime for Evolution API calls (outbound messages, instance management)
7. Evolution API version-agnostic: client works with both v2.x (Node/Express, JSON API) and Evolution Go (Go/Gin, same endpoints)
8. When Evolution not configured (`EVOLUTION_API_URL` / `EVOLUTION_API_KEY` not set), all operations are no-ops with a warning log
9. Outbound messages use `POST /send/text` with per-instance token auth
10. Instance deletion is part of tenant deletion: `DELETE /instance/delete/{name}` via Evolution client
11. Session closing handled by n8n via `POST /webhook/change-status` — backend `close_chat_session` is deprecated no-op

## Input Validation

All field validation goes through centralized `app/core/input_validation/`:

| Field | Rules |
|-------|-------|
| Username | Max 20 chars, lowercase + digits + underscores, must start with letter |
| Full name | Unicode letters, digits, and spaces only (no punctuation) |
| Email | Validated via `email_validator` (syntax only, no deliverability check) |
| Phone | Validated as international E.164 via `phonenumbers` library |
| Client local username | Unique within tenant; combined with `client_prefix` for canonical login |
| Text length | General-purpose text fields (names, descriptions) have length constraints per schema |
| Service keys | Validated against allowed set; invalid keys return HTTP 400 |

## Mailbox Lifecycle

1. One mailbox per tenant, identified by `mailbox_email` + `provider` (google/microsoft/imap_custom)
2. Auth methods: `oauth` (Google/Microsoft) or `imap_app_password` (IMAP with app password)
3. Status transitions: `disconnected` → `connected` (on successful config/test), `connected` → `error` (on fetch failure), `connected`/`error` → `revoked` (on OAuth grant invalid), any → `disconnected` (on manual disconnect)
4. Tenant can have only one mailbox; upsert replaces existing (one-to-one with tenant)
5. OAuth tokens encrypted via Fernet (`ACCESS_TOKEN_ENCRYPTION_KEY`) and stored in `tenant_mailboxes`
6. IMAP password encrypted via Fernet
7. Test connection (`POST /api/v1/tenant/mailbox/test`) attempts actual IMAP/IMAP-OAuth fetch of last N minutes of emails; returns count or error
8. Disconnect clears stored credentials and resets status to `disconnected`
9. OAuth tokens refreshed automatically on 401; `invalid_grant` → mailbox marked `revoked` (manual re-auth required)

## Mail Lookup Jobs Lifecycle

1. Created by n8n via `POST /api/v1/integrations/n8n/mail/lookups` with `service_key`, `target_email`, and tenant identification
2. Status transitions: `pending` → `processing` → `completed` or `failed` or `timeout`
3. `pending`: initial state, not yet picked up by worker
4. `processing`: worker is fetching emails and extracting codes
5. `completed`: code found (`result_type=code`), URL to resolve (`result_type=url`), or not found (`result_type=not_found`). Duplicate extractions suppressed (`result_type=duplicate_suppressed`).
6. `failed`: fetch failure after retries, mailbox not found, or unrecoverable error
7. `timeout`: job exceeded TTL (`expires_at`); n8n poll returns `status=timeout`
8. Jobs have TTL (`expires_at`) after which worker skips them; cleanup loop removes expired jobs
9. `result_value_encrypted`: code or resolved URL, encrypted via Fernet. Kept null in v1 for ephemeral responses delivered via WhatsApp instead of polling.
10. For Netflix `result_type=url`: worker fetches the travel-verify URL, parses HTML for OTP code (4-6 digits), replaces result_value with extracted code. If OTP not found in HTML, marks as `not_found`.
11. Status polling by n8n via `GET /api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=<uuid>`

## Mail Code Delivery Log

1. All extractions logged to `mail_code_delivery_log` table for audit trail
2. Deduplication enforced via unique index on `(tenant_id, service_key, message_id)` where `message_id` is non-null
3. Duplicate suppressed jobs (same tenant + service + message_id) return `result_type=duplicate_suppressed` without writing again
4. Delivery log record created with `status=delivered` alongside job completion
5. Cleanup loop retains records per retention policy (configurable via env, default 90 days)

## Code-Services Governance

1. Global active status per service key stored in `code_service_global_status` table (pre-seeded on first startup with known service keys)
2. Tenant selection stored in `tenant_code_service_selections` table (which services the tenant wants enabled)
3. Effective services = tenant selection ∩ global active services
4. Master toggles global status via `PUT /api/v1/code-services/global` or per-key toggle
5. Tenant replaces selection via `PUT /api/v1/code-services/tenants/current`
6. Invalid `service_key` in any payload returns HTTP 400 (validated via `validate_keys()`)
7. Empty selection results in empty effective set; access code retrieval shows "no services available" message

## Public API Catalog (planned)

1. Public API Catalog is Pro-only and exposes the tenant Catalog as read-only data for tenant-owned browser frontends.
2. Each tenant can have at most one active Public API Key in v1.
3. Public API Key management lives in Settings and is hidden from Starter tenant admins.
4. Allowed Origins are exact origins including scheme, host, and optional port; wildcard origins are not part of v1.
5. Public catalog requests require both a valid Public API Key and a matching `Origin` header.
6. Missing `Origin`, unknown key, non-matching origin, or downgraded Starter tenant returns 403.
7. Regeneration replaces the key and preserves Allowed Origins; revocation deletes the public API configuration.
8. The public payload includes only service and plan `id` + `name` values. Pricing, availability, descriptions, and metadata are out of scope.
9. Production abuse protection for the public catalog route belongs at Cloudflare rate limiting/WAF, not app-level rate limiting in v1.

## Subscription Lifecycle

1. Subscriptions belong to a tenant, client, service, and plan (all required)
2. Streaming password and profile PIN encrypted via Fernet using `DATA_ENCRYPTION_KEY`
3. `starts_at` stored explicitly; `expires_at` derived from duration map (30/90/180/270/365 days) or from `custom_end_date`
4. Status transitions: `active` → `expired` (automatic via cleanup job when `expires_at` passed), `active` → `cancelled` (manual),
   `expired`/`cancelled` → `active` (reactivate with new duration)
5. Reactivate recalculates `expires_at` from new `starts_at`; renew extends from current `expires_at`
6. Cancelled subscriptions keep history via events and reminder logs (no delete)
7. Cleanup lifecycle: expire → auto-cancel (7 days after expiry) → auto-delete (30 days after cancel)
8. Reminder generation: daily job checks subscriptions expiring within `warning_days` (default 7, 3, 1). Unique constraint prevents duplicate reminders per `(subscription_id, recipient_type, days_before_expiry, sent_for_date)`.

## Subscriptions — Reveal Security

1. Password/PIN reveal logs no event; it is a read operation, not a mutation
2. Reveal endpoint returns decrypted values only for the authenticated tenant-scoped subscription
3. Frontend shows masked "reveal" icon per row; password field shows "Sin contraseña" when null

## Metrics & Observability

| Counter | Labels | Location |
|---------|--------|----------|
| `lookup_job_total` | status, provider, service, result | mail_lookup_worker |
| `lookup_job_duration_seconds` | provider | mail_lookup_worker |
| `oauth_refresh_total` | provider, status | oauth_service |
| `mail_fetch_total` | provider, status | imap_fetcher |

All counters use `app.core.metrics` module backed by Prometheus-style counter registers (no push gateway).

## Deployment Constraints

1. Backend runs on Render free tier (web service, cold-start acceptable)
2. PostgreSQL database (external, configured via `DATABASE_URL`)
3. Redis primary + backup (optional; console works in degraded mode without Redis via ContingencyReplyPolicy)
4. Frontend hosted on Cloudflare Pages with SPA fallback redirect
5. Public catalog traffic must be protected by Cloudflare rate limiting/WAF before broad production exposure
6. n8n self-hosted or cloud; connects via `N8N_API_KEY` and public backend URL
7. `DATA_ENCRYPTION_KEY` and `ACCESS_TOKEN_ENCRYPTION_KEY` required at startup for Fernet encryption

## Compliance & Data Model

1. Cascade deletes are intentional: tenant deletion cascades to all linked records (no soft delete for tenant-level data)
2. `User` row is the parent identity for all roles; profile tables (`master_profiles`, `tenants`, `clients`) cascade on owner user delete
3. Unique constraints enforced at DB level with partial indexes (e.g. nullable `message_id`, nullable `whatsapp_lid`)
4. RLS (Row-Level Security) enabled on core auth tables (`users`, `refresh_sessions`, `master_profiles`) and all mailbox/subscription tables
