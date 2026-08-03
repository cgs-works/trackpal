from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import DbDep, MasterUser, resolve_locale
from app.core.errors import UserFacingError, translate_error
from app.models import DemoTenantStatus, Tenant
from app.schemas.demo import (
    DemoTenantCreate,
    DemoTenantCredentialsResponse,
    DemoTenantResponse,
)
from app.services.demo_lifecycle_service import server_time
from app.services.demo_management_service import (
    create_demo_tenant,
    delete_demo_tenant,
    list_demo_tenants,
    replace_demo_credentials,
)

router = APIRouter(prefix="/demos", tags=["demos"])


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _remaining_seconds(tenant: Tenant, now: datetime) -> int | None:
    if tenant.get_demo_status(now) is not DemoTenantStatus.ACTIVE:
        return None
    expires_at = _as_utc(tenant.demo_expires_at)
    if expires_at is None:
        return None
    return max(0, int((expires_at - now).total_seconds()))


def _demo_response(
    tenant: Tenant, *, now: datetime, plain_password: str | None = None
) -> DemoTenantResponse | DemoTenantCredentialsResponse:
    base = {
        "id": tenant.id,
        "name": tenant.name,
        "plan": tenant.plan,
        "locale": tenant.demo_locale or "en",
        "status": tenant.get_demo_status(now),
        "username": tenant.owner.username,
        "created_at": _as_utc(tenant.created_at),
        "demo_activated_at": _as_utc(tenant.demo_activated_at),
        "demo_expires_at": _as_utc(tenant.demo_expires_at),
        "server_time": now,
        "remaining_seconds": _remaining_seconds(tenant, now),
    }
    if plain_password is not None:
        return DemoTenantCredentialsResponse(**base, plain_password=plain_password)
    return DemoTenantResponse(**base)


@router.post(
    "/",
    response_model=DemoTenantCredentialsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_demo(payload: DemoTenantCreate, db: DbDep, current_user: MasterUser):
    locale = "en"
    try:
        tenant, plain_password = await create_demo_tenant(
            db, payload.name, payload.plan, payload.locale
        )
    except UserFacingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=translate_error(locale, exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc
    return _demo_response(tenant, now=server_time(), plain_password=plain_password)


@router.get("/", response_model=list[DemoTenantResponse])
async def list_demos(db: DbDep, current_user: MasterUser):
    now = server_time()
    return [_demo_response(tenant, now=now) for tenant in await list_demo_tenants(db)]


@router.post(
    "/{demo_id}/credentials",
    response_model=DemoTenantCredentialsResponse,
)
async def replace_credentials(demo_id: UUID, db: DbDep, current_user: MasterUser):
    locale = await resolve_locale(db, demo_id)
    try:
        result = await replace_demo_credentials(db, demo_id)
    except UserFacingError as exc:
        code_status = (
            status.HTTP_410_GONE
            if exc.code == "demo_ended"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(
            status_code=code_status,
            detail=translate_error(locale, exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Demo Tenant not found"
        )
    tenant, plain_password = result
    return _demo_response(tenant, now=server_time(), plain_password=plain_password)


@router.delete("/{demo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_demo(demo_id: UUID, db: DbDep, current_user: MasterUser):
    locale = await resolve_locale(db, demo_id)
    try:
        await delete_demo_tenant(db, demo_id)
    except UserFacingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=translate_error(locale, exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
