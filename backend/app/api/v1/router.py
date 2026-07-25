from fastapi import APIRouter

from app.api.v1.endpoints import (
    demos,
    access_control,
    auth,
    catalog,
    clients,
    code_services,
    dashboard,
    export,
    help,
    i18n,
    integrations,
    mailbox,
    me,
    public_api_key,
    public_catalog,
    tenants,
    tenant_export,
    tenant_settings,
    subscriptions,
    whatsapp_link,
)

api_router = APIRouter()
api_router.include_router(demos.router)
api_router.include_router(auth.router)
api_router.include_router(integrations.router)
api_router.include_router(mailbox.router)
api_router.include_router(tenants.router)
api_router.include_router(tenant_export.router)
api_router.include_router(tenant_settings.router)
api_router.include_router(access_control.router)
api_router.include_router(clients.router)
api_router.include_router(catalog.router)
api_router.include_router(code_services.router)
api_router.include_router(i18n.router)
api_router.include_router(help.router)
api_router.include_router(me.router)
api_router.include_router(export.router)

api_router.include_router(public_api_key.router)
api_router.include_router(public_catalog.router)
api_router.include_router(dashboard.router)
api_router.include_router(subscriptions.router)
api_router.include_router(subscriptions.settings_router)
api_router.include_router(subscriptions.jobs_router)
api_router.include_router(subscriptions.reminders_router)
api_router.include_router(whatsapp_link.router)
