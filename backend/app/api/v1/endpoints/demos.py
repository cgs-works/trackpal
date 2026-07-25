from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import DbDep, MasterUser
from app.schemas.demo import (
    DemoTenantCreate,
    DemoTenantCredentialsResponse,
    DemoTenantResponse,
)
from app.services.demo_management_service import (
    DemoManagementError,
    create_demo_tenant,
    delete_demo_tenant,
    list_demo_tenants,
    replace_demo_credentials,
)

router = APIRouter(prefix="/demos", tags=["demos"])


@router.post(
    "/",
    response_model=DemoTenantCredentialsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_demo(payload: DemoTenantCreate, db: DbDep, current_user: MasterUser):
    try:
        return await create_demo_tenant(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get("/", response_model=list[DemoTenantResponse])
async def list_demos(db: DbDep, current_user: MasterUser):
    return await list_demo_tenants(db)


@router.post(
    "/{demo_id}/credentials",
    response_model=DemoTenantCredentialsResponse,
)
async def replace_credentials(demo_id: UUID, db: DbDep, current_user: MasterUser):
    try:
        result = await replace_demo_credentials(db, demo_id)
    except DemoManagementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Demo Tenant not found"
        )
    return result


@router.delete("/{demo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_demo(demo_id: UUID, db: DbDep, current_user: MasterUser):
    try:
        await delete_demo_tenant(db, demo_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
