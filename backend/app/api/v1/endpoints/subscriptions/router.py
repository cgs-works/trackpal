"""Shared router definitions for subscription endpoints.

Submodules import the router(s) they need and register routes directly.
This avoids FastAPI's ``include_router`` restriction on empty path + empty prefix.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
settings_router = APIRouter(
    prefix="/subscription-settings", tags=["subscription-settings"]
)
jobs_router = APIRouter(prefix="/subscriptions", tags=["subscriptions-jobs"])
reminders_router = APIRouter(
    prefix="/subscriptions/reminders", tags=["subscriptions-reminders"]
)
