"""i18n catalog endpoint.

Returns the merged translation catalog for the current user's locale.
Frontend fetches at login and refetches after locale change.
"""

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DbDep
from app.core.i18n import get_merged_catalog, LOCALE_NAMES
from app.repositories import tenant_settings_repository

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
        locale = await tenant_settings_repository.resolve_locale_by_owner(db, current_user.id)
    elif current_user.role == "client":
        locale = await tenant_settings_repository.resolve_locale_by_client(db, current_user.id)

    catalog = get_merged_catalog(locale)
    locale_name = LOCALE_NAMES.get(locale, locale)

    return {
        "locale": locale,
        "locale_name": locale_name,
        "catalog": catalog,
    }
