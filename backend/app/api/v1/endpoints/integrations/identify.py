from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import ApiKeyDbDep
from app.schemas.auth import IdentifyResponse
from app.services.auth_service import AuthService

identify_router = APIRouter(tags=["integrations"])
auth_service = AuthService()


@identify_router.get("/n8n/identify", response_model=IdentifyResponse)
async def identify_n8n(
    phone: str,
    db: ApiKeyDbDep,
):
    result = await auth_service.identify_by_phone(db, phone)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or deactivated",
        )
    return result
