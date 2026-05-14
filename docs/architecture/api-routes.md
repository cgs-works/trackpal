# API Routes

All endpoints are prefixed with `/api/v1/`.

CORS: configured via `CORS_ORIGINS` env var (comma-separated, default `http://localhost:5173`).

## Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/login` | Public | Returns `access_token`, `refresh_token`, `user`. Rejects deactivated tenants. |
| POST | `/auth/refresh` | Public* | Rotates refresh token. Returns new token pair. Rejects inactive tenants. |
| POST | `/auth/logout` | Public* | Revokes the provided refresh token. |
| POST | `/integrations/n8n/console` | X-API-Key | WhatsApp Master Console entrypoint. Body `{phone, message, instance}`. Backend handles auth gating (lockout check → auth session → conversational login → menu/CRUD). Returns `{reply}`. See [data-flow.md](data-flow.md) for full flow. |
| GET | `/integrations/n8n/identify?phone=` | X-API-Key | Identifies user by phone (legacy — not used by Master Console since credential auth). Returns `user_id`, `role`, `username`. Rejects deactivated tenants. 404 if not found. |

\* These endpoints require a valid refresh token in the body, not a Bearer header.

## Tenants (Master only)

| Method | Path | Description |
|---|---|---|
| POST | `/tenants` | Create tenant. Requires `full_name`, `email`, `phone`, `username`, `evolution_instance_name`. Password optional (auto-generates if omitted). Also creates Evolution API instance + n8n integration. Returns `409` on duplicate username, phone, or Evolution API failure. |
| GET | `/tenants` | List all tenants with meta (`total`, `active`, `inactive`). |
| GET | `/tenants/{id}` | Get single tenant details (includes `user.username`). |
| PUT | `/tenants/{id}` | Update tenant fields (`full_name`, `email`, `phone`, `evolution_instance_name`). Changing `evolution_instance_name` does NOT recreate the Evolution instance. |
| PATCH | `/tenants/{id}/deactivate` | Soft-delete tenant. Revokes all active refresh sessions. |
| PATCH | `/tenants/{id}/activate` | Reactivate tenant. |
| DELETE | `/tenants/{id}` | Permanently delete tenant. Only allowed if `is_active=False`. Also deletes the Evolution API instance. Returns `409` on Evolution API failure. |

## Profile

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/me` | Bearer | Get current user profile (MasterProfile or TenantProfile based on role). |
| PUT | `/me` | Bearer | Update profile. Phone uniqueness enforced cross-table (409 on conflict). |
| PUT | `/me/password` | Bearer | Change password. Requires `old_password` + `new_password`. |

## Dashboard

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/dashboard` | Bearer | Returns role-aware data: Master gets tenant counts, Tenant gets placeholder status. |

## Health

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | Public | Returns `{"status": "ok"}`. |
