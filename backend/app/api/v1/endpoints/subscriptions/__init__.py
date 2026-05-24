# Import submodules so route registrations execute at package init time.
# Each submodule imports a shared router object from .router and registers routes on it.
from app.api.v1.endpoints.subscriptions import crud  # noqa: F401
from app.api.v1.endpoints.subscriptions import lifecycle  # noqa: F401
from app.api.v1.endpoints.subscriptions import jobs  # noqa: F401
from app.api.v1.endpoints.subscriptions import settings  # noqa: F401

from app.api.v1.endpoints.subscriptions.router import (
    router,
    settings_router,
    jobs_router,
    reminders_router,
)

__all__ = ["router", "settings_router", "jobs_router", "reminders_router"]
