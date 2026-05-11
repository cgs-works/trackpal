from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_n8n_api_key
from app.schemas.auth import IdentifyResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/integrations", tags=["integrations"])
auth_service = AuthService()
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/n8n/identify", response_model=IdentifyResponse)
async def identify_n8n(
    phone: str,
    x_api_key: Annotated[str, Header(alias="X-API-Key")],
    db: DbDep,
):
    if not verify_n8n_api_key(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    result = await auth_service.identify_by_phone(db, phone)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or deactivated",
        )
    return result
