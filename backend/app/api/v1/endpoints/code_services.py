"""Code services API — global status (master) + tenant selection (tenant/master)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import ActiveTenantId, DbDep, MasterUser
from app.repositories import code_services_repository
from app.schemas.code_services import (
    SUPPORTED_CODE_SERVICES,
    VALID_SERVICE_KEYS,
    CodeServiceGlobalBulkUpdateRequest,
    CodeServiceGlobalItem,
    CodeServiceGlobalListResponse,
    CodeServiceGlobalUpdateRequest,
    TenantCodeServiceItem,
    TenantCodeServiceListResponse,
    TenantCodeServiceUpdateRequest,
)

router = APIRouter(prefix="/code-services", tags=["code-services"])


def _build_tenant_response(
    tenant_id: UUID, selected_keys: set[str], global_active: set[str]
) -> TenantCodeServiceListResponse:
    items = [
        TenantCodeServiceItem(
            service_key=key,
            label=SUPPORTED_CODE_SERVICES.get(key, key),
            is_selected=key in selected_keys,
            is_globally_active=key in global_active,
        )
        for key in sorted(SUPPORTED_CODE_SERVICES.keys())
    ]
    return TenantCodeServiceListResponse(tenant_id=str(tenant_id), services=items)


# ── Master: global status endpoints ──────────────────────────────────────


@router.get("/global", response_model=CodeServiceGlobalListResponse)
async def list_global_code_services(db: DbDep, _master: MasterUser):
    """List all globally supported code services with active status."""
    rows = await code_services_repository.get_all_global(db)
    items = [
        CodeServiceGlobalItem(
            service_key=r.service_key,
            label=SUPPORTED_CODE_SERVICES.get(r.service_key, r.service_key),
            is_active=r.is_active,
        )
        for r in rows
    ]
    return CodeServiceGlobalListResponse(services=items)


@router.put("/global/{service_key}", response_model=CodeServiceGlobalItem)
async def update_global_code_service(
    service_key: str,
    payload: CodeServiceGlobalUpdateRequest,
    db: DbDep,
    _master: MasterUser,
):
    """Toggle global active status for a single service key."""
    if service_key not in VALID_SERVICE_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid service_key: {service_key}",
        )
    row = await code_services_repository.set_global_active(
        db, service_key, payload.is_active
    )
    await db.commit()
    return CodeServiceGlobalItem(
        service_key=row.service_key,
        label=SUPPORTED_CODE_SERVICES.get(row.service_key, row.service_key),
        is_active=row.is_active,
    )


@router.put("/global", response_model=CodeServiceGlobalListResponse)
async def bulk_update_global_code_services(
    payload: CodeServiceGlobalBulkUpdateRequest,
    db: DbDep,
    _master: MasterUser,
):
    """Bulk-set global active status for multiple services."""
    try:
        payload.validate_keys()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    for key, active in payload.services.items():
        await code_services_repository.set_global_active(db, key, active)
    await db.commit()
    rows = await code_services_repository.get_all_global(db)
    items = [
        CodeServiceGlobalItem(
            service_key=r.service_key,
            label=SUPPORTED_CODE_SERVICES.get(r.service_key, r.service_key),
            is_active=r.is_active,
        )
        for r in rows
    ]
    return CodeServiceGlobalListResponse(services=items)


# ── Tenant-facing: /tenants/current (MUST come before /tenants/{tenant_id}) ──


@router.get("/tenants/current", response_model=TenantCodeServiceListResponse)
async def get_my_tenant_code_services(
    db: DbDep,
    tenant_id: ActiveTenantId,
):
    """Get current tenant's code service selection with global active status."""
    selected_keys = await code_services_repository.get_tenant_selected_keys(
        db, tenant_id
    )
    global_active = await code_services_repository.get_active_global_keys(db)
    return _build_tenant_response(tenant_id, selected_keys, global_active)


@router.put("/tenants/current", response_model=TenantCodeServiceListResponse)
async def update_my_tenant_code_services(
    payload: TenantCodeServiceUpdateRequest,
    db: DbDep,
    tenant_id: ActiveTenantId,
):
    """Replace current tenant's code service selection (full-replace sync)."""
    try:
        payload.validate_keys()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    await code_services_repository.replace_tenant_selections(
        db, tenant_id, payload.service_keys
    )
    await db.commit()
    selected_keys = await code_services_repository.get_tenant_selected_keys(
        db, tenant_id
    )
    global_active = await code_services_repository.get_active_global_keys(db)
    return _build_tenant_response(tenant_id, selected_keys, global_active)


@router.get("/tenants/current/effective", response_model=list[str])
async def get_my_effective_code_services(
    db: DbDep,
    tenant_id: ActiveTenantId,
):
    """Return effective service keys for current tenant, sorted A-Z."""
    return await code_services_repository.get_effective_service_keys(db, tenant_id)


# ── Tenant selection endpoints with explicit UUID ────────────────────────


@router.get("/tenants/{tenant_id}", response_model=TenantCodeServiceListResponse)
async def get_tenant_code_services(
    tenant_id: UUID,
    db: DbDep,
    _master: MasterUser,
):
    """Get tenant's code service selection with global active status."""
    selected_keys = await code_services_repository.get_tenant_selected_keys(
        db, tenant_id
    )
    global_active = await code_services_repository.get_active_global_keys(db)
    return _build_tenant_response(tenant_id, selected_keys, global_active)


@router.put("/tenants/{tenant_id}", response_model=TenantCodeServiceListResponse)
async def update_tenant_code_services(
    tenant_id: UUID,
    payload: TenantCodeServiceUpdateRequest,
    db: DbDep,
    _master: MasterUser,
):
    """Replace tenant's code service selection (full-replace sync)."""
    try:
        payload.validate_keys()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    await code_services_repository.replace_tenant_selections(
        db, tenant_id, payload.service_keys
    )
    await db.commit()
    selected_keys = await code_services_repository.get_tenant_selected_keys(
        db, tenant_id
    )
    global_active = await code_services_repository.get_active_global_keys(db)
    return _build_tenant_response(tenant_id, selected_keys, global_active)


@router.get("/tenants/{tenant_id}/effective", response_model=list[str])
async def get_effective_code_services(
    tenant_id: UUID,
    db: DbDep,
    _master: MasterUser,
):
    """Return effective service keys (tenant_selected ∩ global_active), sorted A-Z."""
    return await code_services_repository.get_effective_service_keys(db, tenant_id)
