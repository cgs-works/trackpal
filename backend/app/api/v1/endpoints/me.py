from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, DbDep
from app.core.errors import UserFacingError, translate_error
from app.core.i18n import t as _t
from app.repositories import tenants_repository
from app.schemas.me import PasswordChange, ProfileResponse, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/me", tags=["me"])
profile_service = ProfileService()


async def _resolve_profile_locale(db: DbDep, current_user) -> str:
    if current_user.role == "tenant":
        return await tenants_repository.resolve_locale_by_owner(db, current_user.id)
    if current_user.role == "client":
        return await tenants_repository.resolve_locale_by_client(db, current_user.id)
    return "en"


def _profile_response(user, profile) -> ProfileResponse:
    tenant = getattr(profile, "tenant", None)
    return ProfileResponse(
        role=user.role,
        username=user.username,
        name=getattr(profile, "name", None),
        full_name=getattr(profile, "full_name", None),
        tenant_id=getattr(profile, "tenant_id", None),
        tenant_name=getattr(tenant, "name", None),
        client_prefix=getattr(tenant, "client_prefix", None),
        locale=getattr(tenant, "locale", None) or getattr(profile, "locale", None),
        email=getattr(profile, "email", None),
        phone=getattr(profile, "phone", None),
        is_active=getattr(profile, "is_active", None),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("", response_model=ProfileResponse)
async def get_profile(db: DbDep, current_user: CurrentUser):
    profile = await profile_service.get_profile(db, current_user)
    if profile is None:
        locale = await _resolve_profile_locale(db, current_user)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.profile_not_found")
        )
    return _profile_response(current_user, profile)


@router.put("", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate, db: DbDep, current_user: CurrentUser
):
    try:
        profile = await profile_service.update_profile(db, current_user, payload)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except UserFacingError as exc:
        locale = await _resolve_profile_locale(db, current_user)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=translate_error(locale, exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    if profile is None:
        locale = await _resolve_profile_locale(db, current_user)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.profile_not_found")
        )
    return _profile_response(current_user, profile)


@router.put("/password", response_model=dict)
async def change_password(
    payload: PasswordChange, db: DbDep, current_user: CurrentUser
):
    changed = await profile_service.change_password(
        db, current_user, payload.old_password, payload.new_password
    )
    if not changed:
        locale = await _resolve_profile_locale(db, current_user)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=_t(locale, "errors.incorrect_old_password")
        )
    return {"message": "Password updated successfully"}
