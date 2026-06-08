"""Tenant management — CRUD, lifecycle."""

from app.services.tenant_service.helpers import generate_unique_client_prefix
from app.services.tenant_service.queries import get_tenants, get_tenant
from app.services.tenant_service.mutations import (
    create_tenant,
    update_tenant,
    delete_tenant,
)
from app.services.tenant_service.lifecycle import deactivate_tenant, activate_tenant


class TenantService:
    """Tenant management — delegates to focused modules."""

    _generate_unique_client_prefix = staticmethod(generate_unique_client_prefix)
    get_tenants = staticmethod(get_tenants)
    get_tenant = staticmethod(get_tenant)
    create_tenant = staticmethod(create_tenant)
    update_tenant = staticmethod(update_tenant)
    delete_tenant = staticmethod(delete_tenant)
    deactivate_tenant = staticmethod(deactivate_tenant)
    activate_tenant = staticmethod(activate_tenant)
