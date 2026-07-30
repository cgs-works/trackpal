# API Layer

The backend exposes a FastAPI application at `app/main.py` with routes under `/api/v1`.

## Application Entrypoint

`app/main.py` creates the FastAPI app with:
- CORS middleware (configurable origins via `CORS_ORIGINS`)
- Redis connection manager lifecycle (init on startup, close on shutdown)
- Public root at `GET /` → permanent redirect to `https://trackpal.wilfredocamacho.dev`
- Health check at `GET /health` → `{"status": "ok"}`
- Router inclusion under `/api/v1`

## Route Structure

| Prefix | Module | Tags | Auth |
|--------|--------|------|------|
| `/api/v1/tenant-settings` | `app.api.v1.endpoints.tenant_settings` | tenant-settings | JWT + tenant or master context |
| `/api/v1/auth/*` | `app.api.v1.endpoints.auth` | auth | None (public) |
| `/api/v1/catalog/*` | `app.api.v1.endpoints.catalog` | catalog | JWT + active tenant context |
| `/api/v1/clients/*` | `app.api.v1.endpoints.clients` | clients | JWT + tenant context |
| `/api/v1/me/*` | `app.api.v1.endpoints.me` | me | JWT bearer |
| `/api/v1/tenants/*` | `app.api.v1.endpoints.tenants` | tenants | JWT + master role |
| `/api/v1/demos/*` | `app.api.v1.endpoints.demos` | demos | JWT + master role |
| `/api/v1/integrations/*` | `app.api.v1.endpoints.integrations` | integrations | X-API-Key header |
| `/api/v1/dashboard` | `app.api.v1.endpoints.dashboard` | dashboard | JWT bearer |
| `/api/v1/i18n/*` | `app.api.v1.endpoints.i18n` | i18n | JWT bearer |
| `/api/v1/subscriptions/*` | `app.api.v1.endpoints.subscriptions` | subscriptions | JWT + active tenant context |
| `/api/v1/subscription-settings` | `app.api.v1.endpoints.subscriptions` | subscription-settings | JWT + active tenant context |
| `/api/v1/subscriptions/jobs` | `app.api.v1.endpoints.subscriptions` | subscriptions-jobs | X-API-Key header |
| `/api/v1/subscriptions/reminders` | `app.api.v1.endpoints.subscriptions` | subscriptions-reminders | X-API-Key header |
| `/api/v1/tenant/mailbox/*` | `app.api.v1.endpoints.mailbox` | tenant-mailbox | JWT + active tenant context |
| `/api/v1/tenant/whatsapp-link/*` | `app.api.v1.endpoints.whatsapp_link` | tenant-whatsapp-link | JWT + active tenant context (Starter + Pro) |
| `/api/v1/integrations/n8n/mail/lookups/*` | `app.api.v1.endpoints.integrations.mail_lookups` | integrations-mail | X-API-Key header |
| `/api/v1/code-services/*` | `app.api.v1.endpoints.code_services` | code-services | JWT + master or tenant context |
| `/api/v1/access-control/*` | `app.api.v1.endpoints.access_control` | access-control | JWT + active tenant context |
| `/api/v1/public/catalog` | Public API Catalog endpoint | public-catalog | Public API Key + exact `Origin` |
| `/api/v1/public-api-key/*` | Public API Key management | public-api-key | JWT + Pro tenant or master support context |
| `/api/v1/me/export` | Tenant Data Export self-service (request, status, cancel, download) | export | JWT + tenant or master (step-up) |
| `/api/v1/me/delete-account` | Tenant Admin self-service deletion | delete-account | JWT + tenant (step-up + destructive word) |
| `/api/v1/tenants/{tenant_id}/export` | Master-scoped Tenant Data Export (request, status, cancel, download) | tenant-export | JWT + master (step-up) |
| `/api/v1/tenants/{tenant_id}/delete` | Master Tenant deletion of inactive Tenant | tenants | JWT + master (step-up + destructive word) |

### Public API Catalog

Issue #73 added a Pro-only public catalog surface for tenant-owned browser frontends.

- `GET /api/v1/public/catalog?api_key=<tenant_public_api_key>` returns services with nested plans, limited to `id` and `name`.
- The request must include an `Origin` header that exactly matches one origin registered in `tenant_api_keys.allowed_origins`.
- Missing `Origin`, missing/invalid key, unregistered origin, inactive tenant, or Starter tenant returns 403.
- Successful responses set `Access-Control-Allow-Origin` to the matched origin and `Vary: Origin`.
- The endpoint does not use global CORS middleware and does not add app-level rate limiting.

Authenticated management endpoints:

- `GET /api/v1/public-api-key` returns the current config or `null`.
- `PUT /api/v1/public-api-key` creates or updates `{ "allowed_origins": ["https://example.com"] }` without rotating the key.
- `POST /api/v1/public-api-key/regenerate` rotates the key and preserves origins.
- `DELETE /api/v1/public-api-key` revokes the key and removes the row.

Production must configure Cloudflare rate limiting/WAF for `GET /api/v1/public/catalog` before the feature is advertised broadly.

### Code-Services Endpoints (master + tenant)

Auth for master endpoints: JWT + master role. Auth for tenant endpoints: JWT + active tenant context.

- `GET /api/v1/code-services/global` — List all globally supported services with active status
- `PUT /api/v1/code-services/global` — Bulk-set global active status
- `PUT /api/v1/code-services/global/{service_key}` — Toggle single service globally
- `GET /api/v1/code-services/tenants/current` — Get current tenant's selection
- `PUT /api/v1/code-services/tenants/current` — Replace current tenant's selection
- `GET /api/v1/code-services/tenants/current/effective` — Effective services (selected &cap; active)
- `GET /api/v1/code-services/tenants/{tenant_id}` — Master: get tenant selection
- `PUT /api/v1/code-services/tenants/{tenant_id}` — Master: replace tenant selection
- `GET /api/v1/code-services/tenants/{tenant_id}/effective` — Master: effective services

Invalid `service_key` returns HTTP 400 (manual validation via `validate_keys()`).

### I18n Endpoints

- `GET /api/v1/i18n/catalog` — Returns the merged translation catalog. Production Tenant Admins read `TenantSettings.locale`; Clients read the parent Tenant locale; Master returns English. Demo Tenant Admins may pass `?locale=en|es` so their browser-local workspace controls language without server-side Tenant Settings. Non-Demo query overrides are ignored. Catalogs include all English keys as fallback.

### Auth Endpoints

- `POST /api/v1/auth/login` — Authenticate with username/password, returns access + refresh tokens. Demo responses include only immutable lifecycle metadata (`is_demo`, plan, status, activation/expiry, credential version, and `server_time`); successful first login atomically starts the 48-hour evaluation.
- `POST /api/v1/auth/refresh` — Exchange refresh token for new token pair while preserving Demo lifecycle timestamps and checking credential version and current status
- `POST /api/v1/auth/logout` — Revoke refresh token; expired Demo Tenants are removed on this first relevant request
- `GET|POST /api/v1/auth/heartbeat` — Authenticated lifecycle-only check returning Demo status, credential version, timestamps, plan, and authoritative server time
- `POST /api/v1/auth/switch-tenant` — Master switches into an active production tenant context (set `tenant_id`) or exits context (set `tenant_id: null`) and receives new token with/without `active_tenant_id`; Demo Tenants cannot enter Master Support Context

### Me Endpoints (self-profile)

- `GET /api/v1/me` — Get current user profile, includes `locale` and `timezone` read-only projections from `TenantSettings`
- `PUT /api/v1/me` — Update own profile fields (identity fields only: name, email, phone; **not** locale or timezone)
- `PUT /api/v1/me/password` — Change password
- `POST /api/v1/me/delete-account` — **New**: Tenant Admin permanently deletes own active Tenant. See Tenant Deletion section below.

Client role receives readonly profile data from `GET /api/v1/me`; profile edits are rejected, but password change remains allowed.

**Locale and timezone** are read-only projections on `/me`. To update locale/timezone, use `PUT /api/v1/tenant-settings`.

### Demo Tenant Endpoints (master-only)

- `POST /api/v1/demos/` — Create a Pending Demo Tenant from only an immutable name and explicit Starter/Pro plan. Generates a validator-compatible username and cryptographically strong password; the plaintext password is returned once.
- `GET /api/v1/demos/` — List Demo Tenants with lifecycle-only identity, plan, username, derived status, timestamps, authoritative server time, and remaining seconds. Production Tenants and prospect/workspace telemetry are excluded.
- `POST /api/v1/demos/{demo_id}/credentials` — Replace credentials for Pending or Active demos, revoke all refresh sessions, increment the credential version, and preserve the original evaluation window. Expired demos return `demo_ended`.
- `DELETE /api/v1/demos/{demo_id}` — Idempotently delete a Pending, Active, or Expired Demo Tenant identity and its sessions without invoking production external cleanup.

Demo Tenant name and plan are immutable. Production tenant mutation routes reject Demo Tenants.

### Tenants Endpoints (master-only)

- `POST /api/v1/tenants/` — Create tenant + Evolution instance
- `GET /api/v1/tenants/` — List all tenants with counts
- `GET /api/v1/tenants/{id}` — Get tenant detail
- `PUT /api/v1/tenants/{id}` — Update tenant fields
- `PATCH /api/v1/tenants/{id}/deactivate` — Deactivate tenant + revoke sessions
- `PATCH /api/v1/tenants/{id}/activate` — Reactivate tenant
- `DELETE /api/v1/tenants/{id}` — **Updated**: Delete inactive tenant with password step-up and locale-aware destructive word confirmation. No longer a simple one-click delete. External-first cleanup (R2, Evolution).

Tenant prefix edits update client technical usernames transactionally.

### Clients Endpoints (tenant-scoped)

- `GET /api/v1/clients` — List clients for active tenant
- `POST /api/v1/clients` — Create client with tenant-local username and initial password
- `GET /api/v1/clients/{id}` — Get client detail
- `PUT /api/v1/clients/{id}` — Update client full name, local username, phone
- `PATCH /api/v1/clients/{id}/deactivate` — Deactivate client and revoke refresh sessions
- `PATCH /api/v1/clients/{id}/activate` — Reactivate client
- `DELETE /api/v1/clients/{id}` — Delete inactive client and linked auth user

### Integrations Endpoints (n8n-facing)

- `GET /api/v1/integrations/n8n/identify?phone=` — Identify user by phone (X-API-Key)
- `POST /api/v1/integrations/n8n/console` — WhatsApp Master + Tenant + Client Console message processing (X-API-Key). Routes by instance first (`MASTER_WHATSAPP_INSTANCE`), resolves tenant by instance name, then identity within tenant. Client exit returns `status="closed"` for n8n/Evolution Go. For tenant `codigo` flow, `lookup_job_id` + `tenant_id` are returned only after durable job commit and successful enqueue.
- `POST /api/v1/integrations/n8n/mail/lookups` — Create mailbox lookup job (`service_key`, `target_email`, `tenant_instance|tenant_id`) with `status=pending`.
- `GET /api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=<uuid>` — Poll mailbox lookup status; tenant scope required.

### Tenant Mailbox Endpoints (tenant-scoped)

- `GET /api/v1/tenant/mailbox/` — Current tenant Gmail mailbox config
- `PUT /api/v1/tenant/mailbox/` — Gmail app-password validate-and-connect
- `POST /api/v1/tenant/mailbox/test` — Test current mailbox connection
- `POST /api/v1/tenant/mailbox/oauth/google/start` — Start Google OAuth
- `GET /api/v1/tenant/mailbox/oauth/google/callback` — Complete Google OAuth callback
- `POST /api/v1/tenant/mailbox/disconnect` — Disconnect and clear stored credentials

### Dashboard Endpoints

- `GET /api/v1/dashboard` — Role-aware dashboard data (master sees tenant counts, tenant sees own profile, client sees readonly profile)

### Catalog Endpoints (tenant-scoped)

All catalog endpoints require tenant context. Tenant users derive it from their owned tenant. Master users must call switch-tenant first.

- `GET /api/v1/catalog/services`
- `POST /api/v1/catalog/services`
- `GET /api/v1/catalog/services/{service_id}`
- `PUT /api/v1/catalog/services/{service_id}`
- `DELETE /api/v1/catalog/services/{service_id}?confirm=true` — Confirmed cascade delete for a service, its plans, and all related subscriptions. Without `confirm=true`, returns 400.
- `GET /api/v1/catalog/services/{service_id}/plans`
- `POST /api/v1/catalog/services/{service_id}/plans`
- `PUT /api/v1/catalog/services/{service_id}/plans/{plan_id}`
- `DELETE /api/v1/catalog/services/{service_id}/plans/{plan_id}?confirm=true` — Confirmed cascade delete for a plan and all related subscriptions. Without `confirm=true`, returns 400.
- `GET /api/v1/catalog/services/{service_id}/delete-preview?page=1&page_size=10` — Preview cascade impact before deleting a service. Returns affected plan count, active/historical/total subscription counts, note, and paginated active subscription rows.
- `GET /api/v1/catalog/services/{service_id}/plans/{plan_id}/delete-preview?page=1&page_size=10` — Preview cascade impact before deleting a plan.

Active subscription counts use `status == "active"` only. Services and plans have no active/inactive lifecycle; existing rows count as active catalog items.

Duplicate service/plan names return 409. Cross-tenant resources return 404.

### Subscription Reminder Settings Endpoints

- `GET /api/v1/subscription-settings` — Get current tenant's reminder settings (warning_days, reminder_time, recipient_mode, reminders_enabled, custom messages). Auth: JWT + tenant or master.
- `PUT /api/v1/subscription-settings` — Update reminder settings (warning_days, reminder_time, recipient_mode, reminders_enabled, custom messages). Auth: JWT + tenant or master.

Note: Timezone is no longer part of subscription-settings. Timezone is managed via `TenantSettings` at `/api/v1/tenant-settings`. The timezone catalog moved to `GET /api/v1/tenant-settings/timezones`.

### Tenant Settings Endpoints

- `GET /api/v1/tenant-settings` — Get current tenant's locale and timezone settings. Auth: JWT + tenant or master + ActiveTenantId.
- `PUT /api/v1/tenant-settings` — Update locale and/or timezone. Auth: JWT + tenant or master + ActiveTenantId.
- `GET /api/v1/tenant-settings/timezones` — Return a list of supported IANA timezones with labels. The backend serves this catalog using a three-tier strategy: external provider → system zoneinfo data → bundled fallback. Auth: JWT bearer (tenant or master).


### Access Control Endpoints (tenant-scoped)

- `GET /api/v1/access-control/blocks` — List active blocked identities for the current tenant. Auth: JWT + active tenant context.
- `POST /api/v1/access-control/blocks` — Block a phone number. Auth: JWT + active tenant context.
- `DELETE /api/v1/access-control/blocks/{block_id}` — Unblock an identity. Auth: JWT + active tenant context.

### Tenant Data Export Endpoints

Self-service endpoints (tenant or master in support context):

- `POST /api/v1/me/export` — Request a new Tenant Data Export. Requires password step-up via shared three-attempt/fifteen-minute rate limiter. Enforces 24-hour cooldown. Returns the current export status or 409 on cooldown. Auth: JWT + tenant or master.
- `GET /api/v1/me/export` — Get the latest export job with enriched metadata (status, timestamps, actor attribution, expiry, cooldown, previous version). Returns 204 No Content when no export exists. Auth: JWT + tenant or master.
- `POST /api/v1/me/export/cancel` — Cancel the current pending or processing export. Purges partial uploads from storage. Returns 404 if no job, 409 if job not cancellable. Auth: JWT + tenant or master.
- `GET /api/v1/me/export/download` — Get a presigned download URL valid for 15 minutes (capped to object lifetime). No password reauthentication required. Returns 404 if no ready export. Auth: JWT + tenant or master.

Master-scoped endpoints (target Tenant by ID):

- `POST /api/v1/tenants/{tenant_id}/export` — Request export for specified Tenant (active or inactive). Requires Master password step-up. Auth: JWT + master.
- `GET /api/v1/tenants/{tenant_id}/export` — Get export status for specified Tenant. Auth: JWT + master.
- `POST /api/v1/tenants/{tenant_id}/export/cancel` — Cancel export for specified Tenant. Auth: JWT + master.
- `GET /api/v1/tenants/{tenant_id}/export/download` — Get presigned download URL for specified Tenant. Auth: JWT + master.

### Tenant Deletion Endpoints

- `POST /api/v1/me/delete-account` — Tenant Admin permanently deletes own active Tenant. Requires password step-up + locale-aware destructive word (ELIMINAR/DELETE). External-first cleanup (R2, Evolution) before DB commit. Returns success and redirect info or error. Auth: JWT + tenant.
- `POST /api/v1/tenants/{tenant_id}/delete` — Master deletes an inactive Tenant. Requires password step-up + destructive word. Same external-first, fail-closed cleanup contract. Auth: JWT + master.

### Step-up Authentication Common Contract

Both export generation and deletion use the same shared mechanism:
- Current actor password required
- Three failed attempts per actor in a sliding fifteen-minute window
- Successful attempt resets counter
- Fails closed when Redis HA cannot enforce the limiter
- One generic localized error returned regardless of which input (password vs destructive word) was wrong
- No password, confirmation word, or signed URL is ever logged


### Plan-aware tenant access

Tenant package is stored on `tenants.plan` with allowed values `starter` and `pro`. Backend gates read this database value. Frontend `tenant_plan` is only a rendering hint.

- Starter tenant admins receive HTTP 404 for Pro-only modules: `/clients`, `/catalog/*`, `/subscriptions/*`, `/subscription-settings`.
- Public API Catalog is Pro-only; downgraded Starter tenants receive 403 on public catalog calls while key configuration is preserved.
- Master users switched into a Starter tenant bypass Pro gates for support.
- Starter can access profile, locale, `/tenant/mailbox/*`, `/tenant/whatsapp-link/*`, `/code-services/tenants/current`, `/access-control/blocks`, dashboard, and WhatsApp code lookup.

## Dependency Injection

Defined in `app/api/dependencies.py`:
- `get_current_user` — Decodes JWT, loads user, checks tenant active status
- `get_active_tenant_id` / tenant context helpers — Resolve `active_tenant_id` for tenant users and switched Master users; set RLS context for tenant-scoped work
- `require_role(role)` — Returns a dependency that checks `current_user.role`
- `verify_n8n_api_key_header` — Validates `X-API-Key` header against `settings.n8n_api_key`
- `resolve_locale(db, tenant_id)` — Fetches `TenantSettings.locale` from DB via `tenant_settings_repository`, returns `"en"` fallback. Used before mutating service calls to translate `UserFacingError` responses. Must be called *before* the mutating call to avoid post-rollback RLS context loss.
- Type aliases: `CurrentUser`, `MasterUser`, `DbDep`, `ActiveTenantId`, `TenantPlanDep`, `ProTenantId`

### Demo Guardrail Dependency

`require_demo_guardrail` is the reusable production-boundary dependency. `ActiveTenantId`, `ProTenantId`, and tenant-plan resolution reject Demo Accounts with HTTP 403 and the stable `demo_operation_blocked` code before route handlers run. Dashboard/profile mutations and Help acknowledgement opt into the same dependency explicitly; authentication, password change, Help/i18n reads, and lifecycle heartbeat remain allowlisted. Integration routes apply the same policy after resolving a target Tenant and before mailbox, queue, OAuth, Evolution, export, or public-catalog side effects.
