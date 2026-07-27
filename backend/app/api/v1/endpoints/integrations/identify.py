from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import ApiKeyDbDep
from app.core.demo_guardrail import DemoGuardrailError, assert_demo_operation_allowed
from app.repositories import tenants_repository
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
    if result and result["role"] == "tenant":
        tenant = await tenants_repository.get_by_owner(db, result["user_id"])
        if tenant is not None:
            try:
                assert_demo_operation_allowed(tenant, operation="n8n_identify")
            except DemoGuardrailError as exc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=exc.code,
                ) from exc
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or deactivated",
        )
    return result
