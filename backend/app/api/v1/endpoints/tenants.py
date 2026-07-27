from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import DbDep, MasterUser
from app.core.demo_guardrail import DemoGuardrailError
from app.schemas.tenant import (
    TenantCreate,
    TenantListResponse,
    TenantMeta,
    TenantResponse,
    TenantUpdate,
)
from app.services import export_service
from app.services.step_up_limiter import StepUpError
from app.services.tenant_service import TenantService
from app.services.tenant_service.deletion import delete_tenant_as_master

router = APIRouter(prefix="/tenants", tags=["tenants"])
tenant_service = TenantService()


class MasterDeleteTenantRequest(BaseModel):
    """Password step-up payload for Master tenant deletion."""

    password: str
    destructive_word: str


def _tenant_response(profile) -> TenantResponse:
    return TenantResponse(
        id=profile.id,
        full_name=profile.full_name,
        client_prefix=profile.client_prefix,
        plan=profile.plan,
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
    if profile is None or profile.is_demo:
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
    except DemoGuardrailError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=exc.code
        ) from exc
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
    try:
        profile = await tenant_service.deactivate_tenant(db, tenant_id)
    except DemoGuardrailError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=exc.code
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return _tenant_response(profile)


@router.patch("/{tenant_id}/activate", response_model=TenantResponse)
async def activate_tenant(tenant_id: UUID, db: DbDep, current_user: MasterUser):
    try:
        profile = await tenant_service.activate_tenant(db, tenant_id)
    except DemoGuardrailError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=exc.code
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return _tenant_response(profile)


@router.post("/{tenant_id}/delete", status_code=status.HTTP_200_OK)
async def master_delete_tenant(
    tenant_id: UUID,
    payload: MasterDeleteTenantRequest,
    db: DbDep,
    current_user: MasterUser,
):
    """Permanently delete an inactive Tenant as Master.

    Requires:
    - Master role.
    - Current Master password for step-up authentication.
    - Locale-aware destructive word (DELETE / ELIMINAR).
    - The target Tenant must be inactive (deactivate first).

    Uses the shared three-attempt/fifteen-minute step-up limiter.
    External cleanup (R2, Evolution) runs before database deletion
    and preserves the tenant on failure for safe retry.
    """
    # Resolve Master locale (default en)
    locale = "en"

    limiter = export_service.get_limiter()

    try:
        result = await delete_tenant_as_master(
            db=db,
            tenant_id=tenant_id,
            master_user=current_user,
            password=payload.password,
            destructive_word=payload.destructive_word,
            locale=locale,
            limiter=limiter,
        )
    except DemoGuardrailError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=exc.code
        ) from exc
    except StepUpError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return result
