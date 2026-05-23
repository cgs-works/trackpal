from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    catalog,
    clients,
    dashboard,
    i18n,
    integrations,
    me,
    tenants,
    subscriptions,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(integrations.router)
api_router.include_router(tenants.router)
api_router.include_router(clients.router)
api_router.include_router(catalog.router)
api_router.include_router(i18n.router)
api_router.include_router(me.router)
api_router.include_router(dashboard.router)
api_router.include_router(subscriptions.router)
api_router.include_router(subscriptions.settings_router)
api_router.include_router(subscriptions.jobs_router)
api_router.include_router(subscriptions.reminders_router)
