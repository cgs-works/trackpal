# Code-Services Governance

Master-controlled global activation + per-tenant selection for code-extraction services.

## Overview

Code-services govern which streaming services are available for mailbox code lookup in the WhatsApp tenant console. The system has two layers:

1. **Global status** (master-only): toggle services active/inactive globally.
2. **Tenant selection** (tenant or master): each tenant selects which globally-active services appear in their WhatsApp code flow.

Effective list for WhatsApp = `tenant_selected ∩ global_active`, sorted alphabetically by visible label.

## Data Model

### `code_service_global_status`

Master-controlled global activation table.

| Column | Type | Notes |
|--------|------|-------|
| service_key | VARCHAR(50) | PK, canonical key (e.g. `netflix`, `disney`) |
| is_active | BOOLEAN | Default true, master toggle |
| created_at | TIMESTAMPTZ | Server default now() |
| updated_at | TIMESTAMPTZ | Server default now(), onupdate now() |

### `tenant_code_service_selections`

Per-tenant selection — full-replace sync (last-write-wins).

| Column | Type | Notes |
|--------|------|-------|
| tenant_id | UUID | PK, FK → tenants.id CASCADE |
| service_key | VARCHAR(50) | PK, FK → code_service_global_status.service_key CASCADE |
| created_at | TIMESTAMPTZ | Server default now() |

Composite PK ensures one row per (tenant, service).

## Supported Service Catalog

Source of truth is the `SUPPORTED_CODE_SERVICES` dict in `app/schemas/code_services.py`:

| Key | Label |
|-----|-------|
| `disney` | Disney+ |
| `hbo_max` | HBO Max |
| `netflix` | Netflix |
| `prime_video` | Prime Video |
| `spotify` | Spotify |
| `universal_plus` | Universal+ |

Invalid `service_key` in any API payload returns HTTP 400 (not 422 — manual validation via `validate_keys()`).

## API Endpoints

All under `/api/v1/code-services`.

### Master: Global Status

| Method | Path | Description |
|--------|------|-------------|
| GET | `/code-services/global` | List all globally supported services with active status |
| PUT | `/code-services/global` | Bulk-set global active status for multiple services |
| PUT | `/code-services/global/{service_key}` | Toggle single service active status |

Auth: JWT + master role.

### Tenant: Self-Service (current tenant)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/code-services/tenants/current` | Get tenant's selection with global active status |
| PUT | `/code-services/tenants/current` | Full-replace tenant's selection |
| GET | `/code-services/tenants/current/effective` | Effective list = selected ∩ active, sorted |

Auth: JWT + active tenant context.

### Master: Any Tenant

| Method | Path | Description |
|--------|------|-------------|
| GET | `/code-services/tenants/{tenant_id}` | Get tenant's selection |
| PUT | `/code-services/tenants/{tenant_id}` | Full-replace tenant's selection |
| GET | `/code-services/tenants/{tenant_id}/effective` | Effective list for tenant |

Auth: JWT + master role.

## Validation

- Invalid `service_key` → `HTTPException(400, "invalid_service_key")`
- Empty selection → valid (tenant has no code services configured)
- Globally-disabled but tenant-selected services remain persisted and show as disabled in UI

## Repository

`app/repositories/code_services_repository.py` exposes:

- `get_all_global(db)` — all global status rows
- `set_global_active(db, service_key, is_active)` — upsert global toggle
- `get_active_global_keys(db)` — set of active service keys
- `get_tenant_selected_keys(db, tenant_id)` — set of selected keys
- `replace_tenant_selections(db, tenant_id, keys)` — full-replace, single transaction
- `get_effective_service_keys(db, tenant_id)` — intersection, sorted

## Frontend

Two panels under `frontend/src/components/`:

- `CodeServicesGlobalPanel.vue` — master dashboard panel for global toggles
- `CodeServicesTenantPanel.vue` — tenant dashboard panel for per-tenant selection

Empty-state: when global catalog has zero services, show `frontend.code_services.none` message. Tenant panel reloads latest state before showing success confirmation.

## Related

- [Mailbox Ingestion](mailbox-ingestion.md)
- [Database Schema](database-schema.md)
- [API Layer](api-layer.md)
