# Phase 10: Evolution API Instance Creation on Tenant Registration

## Problem

When creating a tenant via the Master Dashboard, the `evolution_instance_name` field is not shown in the create form (only in edit mode), and the backend does not automatically create an Evolution API WhatsApp instance with n8n integration. The user must manually call Evolution API after creating the tenant.

## Changes

### 1. Config: Add Evolution API settings

**File:** `backend/app/core/config.py`
- Add `evolution_api_url: str`, `evolution_api_key: str`, `evolution_webhook_secret: str`
- Update `backend/.env.example` with the new vars

### 2. New service: Evolution API client

**File:** `backend/app/services/evolution_client.py`
- Async HTTP client using httpx (already in dev deps, add to main deps)
- `create_instance(instance_name: str)` - POST /instance/create with Baileys integration, webhook pointing to backend + X-Webhook-Secret header
- `setup_n8n_integration(instance_name: str)` - POST /n8n/create/{instanceName} with trigger keyword "/menu"

### 3. Schema: Make evolution_instance_name required

**File:** `backend/app/schemas/tenant.py`
- `TenantCreate.evolution_instance_name` → required (remove `| None = None`, add `min_length=1` validator)
- `TenantUpdate.evolution_instance_name` → keep optional (for edits)

### 4. Service: Integrate Evolution API in tenant creation

**File:** `backend/app/services/tenant_service.py`
- In `create_tenant()`:
  - Create User + TenantProfile as before but with `await db.flush()` instead of `commit()`
  - Call `evolution_client.create_instance(payload.evolution_instance_name)`
  - Call `evolution_client.setup_n8n_integration(payload.evolution_instance_name)`
  - If any Evolution call fails: `await db.rollback()` + raise ValueError
  - If success: `await db.commit()`
- In `update_tenant()`: if evolution_instance_name is being changed, warn but don't recreate the instance (document that it's not supported)

### 5. Frontend: Add evolution_instance_name to create form

**File:** `frontend/src/views/MasterDashboardView.vue`
- Show `evolution_instance_name` field in BOTH create and edit mode
- Make it required in the form validation
- Remove the conditional `v-if="!isEditMode"` / `v-else` that hides it

### 6. Dependencies: Add httpx to main deps

**File:** `backend/pyproject.toml`
- Move `httpx` from `[dependency-groups] dev` to `[project] dependencies`

## Transaction safety

```python
async def create_tenant(self, db, payload):
    # 1. Validate uniqueness (username, phone)
    # 2. Create User + Profile → db.add + db.flush()
    try:
        # 3. Evolution API create instance
        await evolution_client.create_instance(payload.evolution_instance_name)
        # 4. Setup n8n integration
        await evolution_client.setup_n8n(payload.evolution_instance_name)
    except Exception as exc:
        await db.rollback()
        raise ValueError(f"Evolution API error: {exc}")
    # 5. Commit DB only after Evolution succeeds
    await db.commit()
    return profile, password
```

## Verification

- Create tenant via API with valid evolution_instance_name → 201 + instance created in Evolution API + n8n integration configured
- Create tenant with invalid instance name (Evolution API fails) → 409 + no DB record created + no stale instance
- Frontend form shows evolution_instance_name in create mode
- `uv run pytest -v` passes all existing tests
