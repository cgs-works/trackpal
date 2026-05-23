"""i18n catalog endpoint.

Returns the merged translation catalog for the current user's locale.
Frontend fetches at login and refetches after locale change.
"""

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DbDep
from app.core.i18n import get_merged_catalog, LOCALE_NAMES
from app.models import Client, Tenant
from sqlalchemy import select

router = APIRouter(prefix="/i18n", tags=["i18n"])


@router.get("/catalog")
async def get_catalog(
    db: DbDep,
    current_user: CurrentUser,
):
    """Return merged translation catalog for the current user's tenant locale.

    The catalog includes all English keys as fallback.  Frontend uses this
    as the single source of translated strings.
    """
    locale = "en"  # default fallback

    if current_user.role == "tenant":
        result = await db.execute(
            select(Tenant.locale).where(Tenant.owner_user_id == current_user.id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            locale = row
    elif current_user.role == "client":
        # Client inherits locale from their tenant
        result = await db.execute(
            select(Tenant.locale).select_from(Client).join(
                Tenant, Client.tenant_id == Tenant.id
            ).where(Client.owner_user_id == current_user.id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            locale = row

    catalog = get_merged_catalog(locale)
    locale_name = LOCALE_NAMES.get(locale, locale)

    return {
        "locale": locale,
        "locale_name": locale_name,
        "catalog": catalog,
    }
