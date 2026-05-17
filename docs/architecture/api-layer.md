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
| `/api/v1/me/*` | `app.api.v1.endpoints.me` | me | JWT bearer |
| `/api/v1/tenants/*` | `app.api.v1.endpoints.tenants` | tenants | JWT + master role |
| `/api/v1/integrations/*` | `app.api.v1.endpoints.integrations` | integrations | X-API-Key header |
| `/api/v1/dashboard` | `app.api.v1.endpoints.dashboard` | dashboard | JWT bearer |

### Auth Endpoints

- `POST /api/v1/auth/login` — Authenticate with username/password, returns access + refresh tokens
- `POST /api/v1/auth/refresh` — Exchange refresh token for new token pair
- `POST /api/v1/auth/logout` — Revoke refresh token

### Me Endpoints (self-profile)

- `GET /api/v1/me` — Get current user profile
- `PUT /api/v1/me` — Update own profile fields
- `PUT /api/v1/me/password` — Change password

### Tenants Endpoints (master-only)

- `POST /api/v1/tenants/` — Create tenant + Evolution API instance
- `GET /api/v1/tenants/` — List all tenants with counts
- `GET /api/v1/tenants/{id}` — Get tenant detail
- `PUT /api/v1/tenants/{id}` — Update tenant fields
- `PATCH /api/v1/tenants/{id}/deactivate` — Deactivate tenant + revoke sessions
- `PATCH /api/v1/tenants/{id}/activate` — Reactivate tenant
- `DELETE /api/v1/tenants/{id}` — Delete inactive tenant + Evolution instance

### Integrations Endpoints (n8n-facing)

- `GET /api/v1/integrations/n8n/identify?phone=` — Identify user by phone (X-API-Key)
- `POST /api/v1/integrations/n8n/console` — WhatsApp Master Console message processing (X-API-Key)

### Dashboard Endpoints

- `GET /api/v1/dashboard` — Role-aware dashboard data (master sees tenant counts, tenant sees own profile)

## Dependency Injection

Defined in `app/api/dependencies.py`:
- `get_current_user` — Decodes JWT, loads user, checks tenant active status
- `require_role(role)` — Returns a dependency that checks `current_user.role`
- `verify_n8n_api_key_header` — Validates `X-API-Key` header against `settings.n8n_api_key`
- Type aliases: `CurrentUser`, `MasterUser`, `DbDep`
