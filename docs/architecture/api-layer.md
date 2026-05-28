# API Layer

The backend exposes a FastAPI application at `app/main.py` with routes under `/api/v1`.

## Application Entrypoint

`app/main.py` creates the FastAPI app with:
- CORS middleware (configurable origins via `CORS_ORIGINS`)
- Redis connection manager lifecycle (init on startup, close on shutdown)
- Health check at `GET /health` → `{"status": "ok"}`
- Router inclusion under `/api/v1`

## Route Structure

| Prefix | Module | Tags | Auth |
|--------|--------|------|------|
| `/api/v1/auth/*` | `app.api.v1.endpoints.auth` | auth | None (public) |
| `/api/v1/catalog/*` | `app.api.v1.endpoints.catalog` | catalog | JWT + active tenant context |
| `/api/v1/clients/*` | `app.api.v1.endpoints.clients` | clients | JWT + tenant context |
| `/api/v1/me/*` | `app.api.v1.endpoints.me` | me | JWT bearer |
| `/api/v1/tenants/*` | `app.api.v1.endpoints.tenants` | tenants | JWT + master role |
| `/api/v1/integrations/*` | `app.api.v1.endpoints.integrations` | integrations | X-API-Key header |
| `/api/v1/dashboard` | `app.api.v1.endpoints.dashboard` | dashboard | JWT bearer |
| `/api/v1/i18n/*` | `app.api.v1.endpoints.i18n` | i18n | JWT bearer |
| `/api/v1/subscriptions/*` | `app.api.v1.endpoints.subscriptions` | subscriptions | JWT + active tenant context |
| `/api/v1/subscription-settings` | `app.api.v1.endpoints.subscriptions` | subscriptions | JWT + active tenant context |
| `/api/v1/subscriptions/jobs` | `app.api.v1.endpoints.subscriptions` | subscriptions | X-API-Key header |
| `/api/v1/subscriptions/reminders` | `app.api.v1.endpoints.subscriptions` | subscriptions | X-API-Key header |
| `/api/v1/tenant/mailbox/*` | `app.api.v1.endpoints.mailbox` | tenant-mailbox | JWT + active tenant context |
| `/api/v1/integrations/n8n/mail/lookups/*` | `app.api.v1.endpoints.integrations.mail_lookups` | integrations-mail | X-API-Key header |

### I18n Endpoints

- `GET /api/v1/i18n/catalog` — Returns merged translation catalog for current user's tenant locale. Tenant reads locale from `Tenant.locale`; client reads from parent tenant; master/unknown returns English. Catalog includes all English keys as fallback.

### Auth Endpoints

- `POST /api/v1/auth/login` — Authenticate with username/password, returns access + refresh tokens
- `POST /api/v1/auth/refresh` — Exchange refresh token for new token pair
- `POST /api/v1/auth/logout` — Revoke refresh token
- `POST /api/v1/auth/switch-tenant` — Master switches into an active tenant context (set `tenant_id`) or exits context (set `tenant_id: null`) and receives new token with/without `active_tenant_id`

### Me Endpoints (self-profile)

- `GET /api/v1/me` — Get current user profile
- `PUT /api/v1/me` — Update own profile fields
- `PUT /api/v1/me/password` — Change password

Client role receives readonly profile data from `GET /api/v1/me`; profile edits are rejected, but password change remains allowed.

### Tenants Endpoints (master-only)

- `POST /api/v1/tenants/` — Create tenant + Evolution instance
- `GET /api/v1/tenants/` — List all tenants with counts
- `GET /api/v1/tenants/{id}` — Get tenant detail
- `PUT /api/v1/tenants/{id}` — Update tenant fields
- `PATCH /api/v1/tenants/{id}/deactivate` — Deactivate tenant + revoke sessions
- `PATCH /api/v1/tenants/{id}/activate` — Reactivate tenant
- `DELETE /api/v1/tenants/{id}` — Delete inactive tenant + Evolution instance

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
- `POST /api/v1/integrations/n8n/console` — WhatsApp Master + Tenant + Client Console message processing (X-API-Key). Routes by instance first (`MASTER_WHATSAPP_INSTANCE`), resolves tenant by instance name, then identity within tenant. Client exit returns `status="closed"` for n8n/Evolution Go.
- `POST /api/v1/integrations/n8n/mail/lookups` — Create mailbox lookup job (`service_key`, `target_email`, `tenant_instance|tenant_id`) with `status=pending`.
- `GET /api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=<uuid>` — Poll mailbox lookup status; tenant scope required.

### Tenant Mailbox Endpoints (tenant-scoped)

- `GET /api/v1/tenant/mailbox/` — Current tenant mailbox config
- `PUT /api/v1/tenant/mailbox/` — Upsert mailbox config (OAuth/IMAP exclusivity)
- `POST /api/v1/tenant/mailbox/test` — Connection test
- `POST /api/v1/tenant/mailbox/oauth/{provider}/start` — Start OAuth
- `GET /api/v1/tenant/mailbox/oauth/{provider}/callback` — Complete OAuth callback
- `POST /api/v1/tenant/mailbox/disconnect` — Disconnect and clear stored credentials

### Dashboard Endpoints

- `GET /api/v1/dashboard` — Role-aware dashboard data (master sees tenant counts, tenant sees own profile, client sees readonly profile)

### Catalog Endpoints (tenant-scoped)

All catalog endpoints require tenant context. Tenant users derive it from their owned tenant. Master users must call switch-tenant first.

- `GET /api/v1/catalog/services`
- `POST /api/v1/catalog/services`
- `GET /api/v1/catalog/services/{service_id}`
- `PUT /api/v1/catalog/services/{service_id}`
- `DELETE /api/v1/catalog/services/{service_id}`
- `GET /api/v1/catalog/services/{service_id}/plans`
- `POST /api/v1/catalog/services/{service_id}/plans`
- `PUT /api/v1/catalog/services/{service_id}/plans/{plan_id}`
- `DELETE /api/v1/catalog/services/{service_id}/plans/{plan_id}`

Duplicate service/plan names return 409. Cross-tenant resources return 404.

## Dependency Injection

Defined in `app/api/dependencies.py`:
- `get_current_user` — Decodes JWT, loads user, checks tenant active status
- `get_active_tenant_id` / tenant context helpers — Resolve `active_tenant_id` for tenant users and switched Master users; set RLS context for tenant-scoped work
- `require_role(role)` — Returns a dependency that checks `current_user.role`
- `verify_n8n_api_key_header` — Validates `X-API-Key` header against `settings.n8n_api_key`
- `resolve_locale(db, tenant_id)` — Fetches `Tenant.locale` from DB, returns `"en"` fallback. Used before mutating service calls to translate `UserFacingError` responses. Must be called *before* the mutating call to avoid post-rollback RLS context loss.
- Type aliases: `CurrentUser`, `MasterUser`, `DbDep`, `ActiveTenantId`
