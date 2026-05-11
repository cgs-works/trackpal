from fastapi import APIRouter

from app.api.v1.endpoints import auth, integrations, tenants

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(integrations.router)
api_router.include_router(tenants.router)
