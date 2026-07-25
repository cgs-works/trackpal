from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Response, status

from app.api.dependencies import DbDep
from app.core.demo_guardrail import DemoGuardrailError
from app.schemas.public_api_key import PublicCatalogResponse
from app.services.public_api_key_service import PublicApiKeyService

router = APIRouter(prefix="/public", tags=["public-catalog"])
public_api_key_service = PublicApiKeyService()


@router.get("/catalog", response_model=PublicCatalogResponse)
async def get_public_catalog(
    db: DbDep,
    response: Response,
    api_key: Annotated[str | None, Query()] = None,
    origin: Annotated[str | None, Header(alias="Origin")] = None,
):
    try:
        result = await public_api_key_service.build_public_catalog(
            db,
            api_key=api_key,
            origin=origin,
        )
    except DemoGuardrailError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.code,
        ) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    payload, allowed_origin = result
    response.headers["Access-Control-Allow-Origin"] = allowed_origin
    response.headers["Vary"] = "Origin"
    return payload
