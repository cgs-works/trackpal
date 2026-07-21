from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DbDep, resolve_locale
from app.help import get_help_catalog
from app.repositories import tenants_repository
from app.schemas.help import (
    HelpIndexResponse,
    HelpSearchResponse,
    HelpTopicResponse,
)

router = APIRouter(prefix="/help", tags=["help"])
help_catalog = get_help_catalog()


async def _tenant_admin_context(
    db: DbDep, current_user: CurrentUser
) -> tuple[str, str]:
    if current_user.role != "tenant":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    tenant = await tenants_repository.get_active_by_owner(db, current_user.id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    locale = await resolve_locale(db, tenant.id)
    return tenant.plan, locale


@router.get("", response_model=HelpIndexResponse)
async def get_help_index(db: DbDep, current_user: CurrentUser) -> HelpIndexResponse:
    """Return the private Help navigation for the authenticated Tenant Admin."""

    plan, locale = await _tenant_admin_context(db, current_user)
    return help_catalog.index(locale, plan)


@router.get("/topics/{topic_id}", response_model=HelpTopicResponse)
async def get_help_topic(
    topic_id: str, db: DbDep, current_user: CurrentUser
) -> HelpTopicResponse:
    """Return one localized topic when its role and plan are authorized."""

    plan, locale = await _tenant_admin_context(db, current_user)
    topic = help_catalog.topic(locale, plan, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return topic


@router.get("/search", response_model=HelpSearchResponse)
async def search_help(
    db: DbDep,
    current_user: CurrentUser,
    q: str = Query(min_length=1, max_length=100),
) -> HelpSearchResponse:
    """Search only the authorized private Help corpus."""

    plan, locale = await _tenant_admin_context(db, current_user)
    return {
        "query": q,
        "locale": locale,
        "results": help_catalog.search(locale, plan, q),
    }
