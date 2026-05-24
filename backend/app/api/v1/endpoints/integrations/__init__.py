from fastapi import APIRouter

from app.api.v1.endpoints.integrations.identify import identify_router
from app.api.v1.endpoints.integrations.console import console_router
from app.api.v1.endpoints.integrations.adapter import _TenantConsoleAdapter

router = APIRouter(prefix="/integrations", tags=["integrations"])
router.include_router(identify_router)
router.include_router(console_router)

__all__ = ["router", "_TenantConsoleAdapter"]
