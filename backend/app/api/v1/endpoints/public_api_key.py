from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import DbDep, ProTenantId
from app.schemas.public_api_key import PublicApiKeyResponse, PublicApiKeyUpdate
from app.services.public_api_key_service import PublicApiKeyService

router = APIRouter(prefix="/public-api-key", tags=["public-api-key"])
public_api_key_service = PublicApiKeyService()


@router.get("", response_model=PublicApiKeyResponse | None)
async def get_public_api_key(db: DbDep, tenant_id: ProTenantId):
    return await public_api_key_service.get_config(db, tenant_id)


@router.put("", response_model=PublicApiKeyResponse)
async def upsert_public_api_key(
    payload: PublicApiKeyUpdate, db: DbDep, tenant_id: ProTenantId
):
    try:
        return await public_api_key_service.upsert_origins(
            db, tenant_id, payload.allowed_origins
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.post("/regenerate", response_model=PublicApiKeyResponse)
async def regenerate_public_api_key(db: DbDep, tenant_id: ProTenantId):
    return await public_api_key_service.regenerate(db, tenant_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_public_api_key(db: DbDep, tenant_id: ProTenantId):
    await public_api_key_service.revoke(db, tenant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
