from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import ActiveTenantId, DbDep
from app.schemas.access_control import (
    AccessControlBlockCreate,
    AccessControlBlockResponse,
)
from app.services.access_control_service import (
    AccessControlService,
    DuplicateAccessBlockError,
)

router = APIRouter(prefix="/access-control", tags=["access-control"])
service = AccessControlService()


@router.get("/blocks", response_model=list[AccessControlBlockResponse])
async def list_blocks(db: DbDep, tenant_id: ActiveTenantId):
    return await service.list_blocks(db, tenant_id)


@router.post(
    "/blocks",
    response_model=AccessControlBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_block(
    payload: AccessControlBlockCreate, db: DbDep, tenant_id: ActiveTenantId
):
    try:
        return await service.block_phone(db, tenant_id, payload.phone)
    except DuplicateAccessBlockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(block_id: UUID, db: DbDep, tenant_id: ActiveTenantId):
    block = await service.unblock(db, tenant_id, block_id)
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Block not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
