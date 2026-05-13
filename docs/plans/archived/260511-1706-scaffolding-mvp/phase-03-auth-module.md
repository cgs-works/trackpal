# Phase 3: Auth Module

**Complexity:** M
**Dependencies:** Phase 2

## Objective

Implement unified JWT authentication with refresh token rotation, bcrypt hashing, role-based dependency injection, and the n8n identify endpoint protected with API Key.

## Preconditions

- Models created with Alembic migrations applied.
- Seed script creates Master.

## Tasks

1. **Security utilities** (`backend/app/core/security.py`):
   - Password hashing with bcrypt via passlib
   - JWT creation/validation with python-jose (access token 30min, refresh token 7 days)
   - Secure random token generation for refresh tokens
   - API Key validation (`N8N_API_KEY` env var)

2. **Auth schemas** (`backend/app/schemas/auth.py`):
   - `LoginRequest` — username, password
   - `TokenResponse` — access_token, refresh_token, token_type, user (id, role, username)
   - `RefreshRequest` — refresh_token
   - `IdentifyResponse` — user_id, role, username

3. **Auth service** (`backend/app/services/auth_service.py`):
   - `authenticate(db, username, password)` — verify credentials, check is_active
   - `create_tokens(db, user)` — generate access + refresh, store refresh_session (hashed)
   - `refresh_access_token(db, refresh_token)` — verify, rotate (invalidate old, create new)
   - `revoke_refresh_token(db, refresh_token)` — logout
   - `identify_by_phone(db, phone)` — search master_profiles + tenant_profiles, exclude inactive

4. **Auth endpoints** (`backend/app/api/v1/endpoints/auth.py`):
   - `POST /auth/login` — returns TokenResponse
   - `POST /auth/refresh` — refresh token rotation
   - `POST /auth/logout` — revoke refresh token

5. **Integrations endpoint** (`backend/app/api/v1/endpoints/integrations.py`):
   - `GET /integrations/n8n/identify?phone=X` — requires `X-API-Key` header, returns IdentifyResponse or 404

6. **Dependencies** (`backend/app/api/dependencies.py`):
   - `get_current_user` — decode JWT, load user from DB
   - `require_role('master')` — check user.role
   - `verify_n8n_api_key` — check X-API-Key header against N8N_API_KEY env

7. **CRUD helpers** (`backend/app/crud/users.py`):
   - `get_by_username(db, username)`
   - `get_by_phone(db, phone)` — search across both profile tables
   - `get(db, user_id)`

## Verification

- Commands:
  - `pytest tests/test_auth.py` — login success, login fail (wrong password, deactivated tenant), refresh token rotation, logout, identify with valid/invalid API Key
  - Manual: `curl -X POST /api/v1/auth/login -d '{"username":"master","password":"..."}'`
  - Manual: `curl /api/v1/integrations/n8n/identify?phone=X -H 'X-API-Key: ...'`
- OpenAPI docs at `/docs` show all auth endpoints

## Exit Criteria

- [ ] Login returns access + refresh tokens for valid credentials
- [ ] Login blocked for deactivated tenants
- [ ] Refresh token rotation works (old token invalidated)
- [ ] Identify endpoint returns correct user or 404
- [ ] Identify endpoint rejects requests without valid API Key
- [ ] All password hashes are bcrypt
