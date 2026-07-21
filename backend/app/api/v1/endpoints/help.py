from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DbDep, resolve_locale
from app.help import get_help_catalog
from app.models import TenantHelpAcknowledgement
from app.repositories import clients_repository, tenant_help_repository
from app.repositories import tenant_settings_repository, tenants_repository
from app.schemas.help import (
    HelpIndexResponse,
    HelpSearchResponse,
    HelpTopicResponse,
    HelpTourAcknowledgementRequest,
    HelpTourAcknowledgementResponse,
    HelpTourRelease,
)

router = APIRouter(prefix="/help", tags=["help"])
help_catalog = get_help_catalog()
STARTER_RELEASE_ID = "tenant-admin-starter-1"
INITIAL_PRO_RELEASE_ID = "tenant-admin-pro-1"


async def _tenant_admin_context(
    db: DbDep, current_user: CurrentUser
) -> tuple[UUID, str, str]:
    if current_user.role != "tenant":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    tenant = await tenants_repository.get_active_by_owner(db, current_user.id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    locale = await resolve_locale(db, tenant.id)
    return tenant.id, tenant.plan, locale


async def _help_context(db: DbDep, current_user: CurrentUser) -> tuple[str, str, str]:
    if current_user.role == "tenant":
        tenant = await tenants_repository.get_active_by_owner(db, current_user.id)
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
            )
        locale = await resolve_locale(db, tenant.id)
        return "tenant_admin", tenant.plan, locale

    if current_user.role == "client":
        client_tenant = await clients_repository.get_active_client_tenant_join(
            db, current_user.id
        )
        if client_tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
            )
        _client, tenant = client_tenant
        if tenant.plan != "pro":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
            )
        locale = await tenant_settings_repository.resolve_locale(db, tenant.id)
        return "client", tenant.plan, locale

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _initial_pro_release_is_suppressed(
    db: DbDep, tenant_id: UUID, plan: str, release_id: str
) -> bool:
    if plan != "pro" or release_id != INITIAL_PRO_RELEASE_ID:
        return False
    return (
        await tenant_help_repository.get_acknowledgement(
            db, tenant_id, STARTER_RELEASE_ID
        )
    ) is not None


@router.get("", response_model=HelpIndexResponse)
async def get_help_index(db: DbDep, current_user: CurrentUser) -> HelpIndexResponse:
    """Return the private Help navigation for the authenticated audience."""

    audience, plan, locale = await _help_context(db, current_user)
    return help_catalog.index(locale, plan, audience)


@router.get("/topics/{topic_id}", response_model=HelpTopicResponse)
async def get_help_topic(
    topic_id: str, db: DbDep, current_user: CurrentUser
) -> HelpTopicResponse:
    """Return one localized topic when its audience and plan are authorized."""

    audience, plan, locale = await _help_context(db, current_user)
    topic = help_catalog.topic(locale, plan, topic_id, audience)
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

    audience, plan, locale = await _help_context(db, current_user)
    return {
        "query": q,
        "locale": locale,
        "results": help_catalog.search(locale, plan, q, audience),
    }


def _tour_response(
    release: dict,
    locale: str,
    plan: str,
    acknowledgement: TenantHelpAcknowledgement | None = None,
) -> HelpTourRelease:
    return HelpTourRelease(
        release_id=release["release_id"],
        status=acknowledgement.status if acknowledgement else None,
        acknowledged_at=(
            acknowledgement.acknowledged_at.isoformat() if acknowledgement else None
        ),
        locale=locale,
        plan=plan,
        frontend_target_contract_version=help_catalog.artifact[
            "frontend_target_contract_version"
        ],
        steps=release["steps"],
    )


@router.get("/tour", response_model=HelpTourRelease)
async def get_unseen_tour(db: DbDep, current_user: CurrentUser) -> HelpTourRelease:
    """Return the first eligible, unseen Tenant Admin tour release."""

    tenant_id, plan, locale = await _tenant_admin_context(db, current_user)
    for release in help_catalog.tour_releases(locale, plan):
        if await _initial_pro_release_is_suppressed(
            db, tenant_id, plan, release["release_id"]
        ):
            continue
        acknowledgement = await tenant_help_repository.get_acknowledgement(
            db, tenant_id, release["release_id"]
        )
        if acknowledgement is None:
            eligible_release = help_catalog.tour_release(
                locale, plan, release["release_id"]
            )
            if eligible_release is not None:
                return _tour_response(eligible_release, locale, plan)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.get("/tour/{release_id}/replay", response_model=HelpTourRelease)
async def replay_tour(
    release_id: str, db: DbDep, current_user: CurrentUser
) -> HelpTourRelease:
    """Return an eligible tour release regardless of acknowledgement state."""

    tenant_id, plan, locale = await _tenant_admin_context(db, current_user)
    if await _initial_pro_release_is_suppressed(db, tenant_id, plan, release_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    release = help_catalog.tour_release(locale, plan, release_id)
    if release is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    acknowledgement = await tenant_help_repository.get_acknowledgement(
        db, tenant_id, release_id
    )
    return _tour_response(release, locale, plan, acknowledgement)


@router.post(
    "/tour/{release_id}/acknowledge",
    response_model=HelpTourAcknowledgementResponse,
)
async def acknowledge_tour(
    release_id: str,
    payload: HelpTourAcknowledgementRequest,
    db: DbDep,
    current_user: CurrentUser,
) -> HelpTourAcknowledgementResponse:
    """Persist one immutable, Tenant-scoped tour acknowledgement."""

    tenant_id, plan, locale = await _tenant_admin_context(db, current_user)
    if await _initial_pro_release_is_suppressed(db, tenant_id, plan, release_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if help_catalog.tour_release(locale, plan, release_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    acknowledgement = await tenant_help_repository.acknowledge(
        db, tenant_id, release_id, payload.status
    )
    return HelpTourAcknowledgementResponse(
        release_id=acknowledgement.release_id,
        status=acknowledgement.status,
        acknowledged_at=acknowledgement.acknowledged_at.isoformat(),
    )
