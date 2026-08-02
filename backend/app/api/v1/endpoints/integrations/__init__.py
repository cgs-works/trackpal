from fastapi import APIRouter

from app.api.v1.endpoints.integrations.identify import identify_router
from app.api.v1.endpoints.integrations.console import console_router
from app.api.v1.endpoints.integrations.mail_lookups import router as mail_lookups_router
from app.api.v1.endpoints.integrations.executor_callbacks import (
    router as executor_callbacks_router,
)
from app.api.v1.endpoints.integrations.adapter import _TenantConsoleAdapter

router = APIRouter(prefix="/integrations", tags=["integrations"])
router.include_router(identify_router)
router.include_router(console_router)
router.include_router(mail_lookups_router)
router.include_router(executor_callbacks_router)

__all__ = ["router", "_TenantConsoleAdapter"]
