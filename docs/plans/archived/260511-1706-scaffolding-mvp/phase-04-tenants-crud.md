# Phase 4: Tenants CRUD

**Complexity:** M
**Dependencies:** Phase 3

## Objective

Implement Master-only endpoints for tenant management with soft-delete logic, metadata metrics, and password auto/manual options on create.

## Preconditions

- Auth module working (login, JWT, role middleware).
- Models created.

## Tasks

1. **Tenant schemas** (`backend/app/schemas/tenant.py`):
   - `TenantCreate` — full_name, email, phone, username, password (optional — if null, auto-generate), evolution_instance_name
   - `TenantUpdate` — full_name, email, phone, evolution_instance_name (partial)
   - `TenantResponse` — id, full_name, email, phone, evolution_instance_name, is_active, username, created_at
   - `TenantListResponse` — data: list[TenantResponse], meta: { total, active, inactive }

2. **Tenant service** (`backend/app/services/tenant_service.py`):
   - `create_tenant(db, payload)` — create User + TenantProfile in transaction; if no password, generate with secrets.token_urlsafe(16); validate phone uniqueness; return created tenant + plain password (one-time display)
   - `get_tenants(db)` — return list + meta counts (total, active, inactive)
   - `get_tenant(db, tenant_id)` — return tenant or 404
   - `update_tenant(db, tenant_id, payload)` — update profile fields
   - `deactivate_tenant(db, tenant_id)` — set is_active = False
   - `activate_tenant(db, tenant_id)` — set is_active = True
   - `delete_tenant(db, tenant_id)` — only if is_active = False; delete User (cascades to profile)
   - Phone uniqueness validation cross-table

3. **Tenant endpoints** (`backend/app/api/v1/endpoints/tenants.py`):
   - `POST /tenants` — create (requires master role)
   - `GET /tenants` — list with metadata (requires master role)
   - `GET /tenants/{id}` — detail (requires master role)
   - `PUT /tenants/{id}` — update (requires master role)
   - `PATCH /tenants/{id}/deactivate` — soft-delete (requires master role)
   - `PATCH /tenants/{id}/activate` — reactivate (requires master role)
   - `DELETE /tenants/{id}` — permanent delete if inactive (requires master role)

## Verification

- Commands:
  - `pytest tests/test_tenants.py` — create, list, get, update, deactivate, reactivate, delete, delete without deactivate (403), duplicate phone (409)
  - Manual: `curl` create tenant → verify 201 + plain_password in response
  - Manual: verify GET /tenants returns meta with counts
  - Manual: attempt login as deactivated tenant → 401

## Exit Criteria

- [ ] Full CRUD working with correct HTTP status codes
- [ ] Metadata metrics returned in list endpoint
- [ ] Delete blocked unless tenant is deactivated
- [ ] Deactivated tenant cannot log in
- [ ] Phone uniqueness enforced cross-table
- [ ] Password auto-generation works (secure, returns once)
