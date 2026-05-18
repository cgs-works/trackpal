from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import DbDep, MasterUser
from app.schemas.tenant import (
    TenantCreate,
    TenantListResponse,
    TenantMeta,
    TenantResponse,
    TenantUpdate,
)
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])
tenant_service = TenantService()


def _tenant_response(profile) -> TenantResponse:
    return TenantResponse(
        id=profile.id,
        full_name=profile.full_name,
        client_prefix=profile.client_prefix,
        email=profile.email,
        phone=profile.phone,
        evolution_instance_name=profile.evolution_instance_name,
        is_active=profile.is_active,
        username=profile.owner.username,
        created_at=profile.created_at,
    )


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreate, db: DbDep, current_user: MasterUser):
    try:
        profile, plain_password = await tenant_service.create_tenant(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    result = _tenant_response(profile).model_dump()
    result["plain_password"] = plain_password
    return result


@router.get("/", response_model=TenantListResponse)
async def list_tenants(db: DbDep, current_user: MasterUser):
    profiles, meta = await tenant_service.get_tenants(db)
    return TenantListResponse(
        data=[_tenant_response(profile) for profile in profiles],
        meta=TenantMeta(**meta),
    )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: UUID, db: DbDep, current_user: MasterUser):
    profile = await tenant_service.get_tenant(db, tenant_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return _tenant_response(profile)


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID, payload: TenantUpdate, db: DbDep, current_user: MasterUser
):
    try:
        profile = await tenant_service.update_tenant(db, tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return _tenant_response(profile)


@router.patch("/{tenant_id}/deactivate", response_model=TenantResponse)
async def deactivate_tenant(tenant_id: UUID, db: DbDep, current_user: MasterUser):
    profile = await tenant_service.deactivate_tenant(db, tenant_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return _tenant_response(profile)


@router.patch("/{tenant_id}/activate", response_model=TenantResponse)
async def activate_tenant(tenant_id: UUID, db: DbDep, current_user: MasterUser):
    profile = await tenant_service.activate_tenant(db, tenant_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return _tenant_response(profile)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: UUID, db: DbDep, current_user: MasterUser):
    try:
        deleted = await tenant_service.delete_tenant(db, tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
