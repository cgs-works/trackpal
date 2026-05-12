# API Routes

All endpoints are prefixed with `/api/v1/`.

## Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/login` | Public | Returns `access_token`, `refresh_token`, `user`. Rejects deactivated tenants. |
| POST | `/auth/refresh` | Public* | Rotates refresh token. Returns new token pair. Rejects inactive tenants. |
| POST | `/auth/logout` | Public* | Revokes the provided refresh token. |
| GET | `/integrations/n8n/identify?phone=` | X-API-Key | Identifies user by phone. Returns `user_id`, `role`, `username`. Rejects deactivated tenants. 404 if not found. |

\* These endpoints require a valid refresh token in the body, not a Bearer header.

## Tenants (Master only)

| Method | Path | Description |
|---|---|---|
| POST | `/tenants` | Create tenant. Accepts `full_name`, `email`, `phone`, `username`, `password` (optional). Auto-generates password if omitted. Returns `409` on duplicate username or phone. |
| GET | `/tenants` | List all tenants with meta (`total`, `active`, `inactive`). |
| GET | `/tenants/{id}` | Get single tenant details (includes user.username). |
| PATCH | `/tenants/{id}` | Update tenant fields. |
| POST | `/tenants/{id}/deactivate` | Soft-delete tenant. Revokes all active refresh sessions. |
| POST | `/tenants/{id}/activate` | Reactivate tenant. |
| DELETE | `/tenants/{id}` | Permanently delete tenant. Only allowed if `is_active=False`. |

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
