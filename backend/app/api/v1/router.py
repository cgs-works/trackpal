from fastapi import APIRouter

from app.api.v1.endpoints import auth, dashboard, integrations, me, tenants

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(integrations.router)
api_router.include_router(tenants.router)
api_router.include_router(me.router)
api_router.include_router(dashboard.router)
