from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import ActiveTenantId, CurrentUser, DemoGuardedUser, DbDep
from app.core.database import restore_rls_context
from app.core.errors import UserFacingError, translate_error
from app.core.i18n import t as _t
from app.repositories import tenant_settings_repository
from app.schemas.me import PasswordChange, ProfileResponse, ProfileUpdate
from app.services import export_service
from app.services.profile_service import ProfileService
from app.services.step_up_limiter import StepUpError
from app.services.tenant_service.deletion import delete_tenant_account

router = APIRouter(prefix="/me", tags=["me"])
profile_service = ProfileService()


async def _resolve_profile_locale(db: DbDep, current_user) -> str:
    if current_user.role == "tenant":
        return await tenant_settings_repository.resolve_locale_by_owner(
            db, current_user.id
        )
    if current_user.role == "client":
        return await tenant_settings_repository.resolve_locale_by_client(
            db, current_user.id
        )
    return "en"


def _profile_response(
    user, profile, *, locale: str | None = None, timezone: str | None = None
) -> ProfileResponse:
    tenant = getattr(profile, "tenant", None)
    tenant_id = getattr(profile, "tenant_id", None)
    if user.role == "tenant":
        tenant_id = getattr(profile, "id", None)

    return ProfileResponse(
        role=user.role,
        username=user.username,
        name=getattr(profile, "name", None),
        full_name=getattr(profile, "full_name", None),
        tenant_id=tenant_id,
        tenant_name=getattr(tenant, "name", None),
        client_prefix=getattr(tenant, "client_prefix", None),
        locale=locale,
        timezone=timezone,
        email=getattr(profile, "email", None),
        phone=getattr(profile, "phone", None),
        is_active=getattr(profile, "is_active", None),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


async def _resolve_profile_settings(
    db: DbDep, current_user, profile
) -> tuple[str | None, str | None]:
    if current_user.role == "tenant":
        (
            settings,
            _created,
        ) = await tenant_settings_repository.get_or_create_by_tenant_id(db, profile.id)
        if _created:
            await db.commit()
            await restore_rls_context(db)
            await db.refresh(settings)
        return settings.locale, settings.timezone

    if current_user.role == "client":
        tenant_id = getattr(profile, "tenant_id", None)
        if tenant_id is None:
            return "en", "UTC"
        locale = await tenant_settings_repository.resolve_locale(db, tenant_id)
        timezone = await tenant_settings_repository.resolve_timezone(db, tenant_id)
        return locale, timezone

    return None, None


@router.get("", response_model=ProfileResponse)
async def get_profile(db: DbDep, current_user: DemoGuardedUser):
    profile = await profile_service.get_profile(db, current_user)
    if profile is None:
        locale = await _resolve_profile_locale(db, current_user)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.profile_not_found"),
        )
    locale, timezone = await _resolve_profile_settings(db, current_user, profile)
    return _profile_response(current_user, profile, locale=locale, timezone=timezone)


@router.put("", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate, db: DbDep, current_user: DemoGuardedUser
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.profile_not_found"),
        )
    locale, timezone = await _resolve_profile_settings(db, current_user, profile)
    return _profile_response(current_user, profile, locale=locale, timezone=timezone)


async def _tenant_profile_response(
    tenant, *, locale: str | None = None, timezone: str | None = None
) -> ProfileResponse:
    """Build a ProfileResponse from a Tenant model (for Master support context)."""
    owner = getattr(tenant, "owner", None)
    return ProfileResponse(
        role="tenant",
        username=owner.username if owner else "",
        name=tenant.name,
        full_name=tenant.full_name,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        client_prefix=tenant.client_prefix,
        locale=locale,
        timezone=timezone,
        email=tenant.email,
        phone=tenant.phone,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


@router.get("/tenant-profile", response_model=ProfileResponse)
async def get_tenant_profile(
    db: DbDep,
    current_user: CurrentUser,
    active_tenant_id: ActiveTenantId,
):
    """Get the active tenant's profile (Master support context only)."""
    if current_user.role != "master":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Master users can access this endpoint",
        )
    profile = await profile_service.get_tenant_profile_by_id(db, active_tenant_id)
    if profile is None:
        locale = await _resolve_profile_locale(db, current_user)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.profile_not_found"),
        )
    locale = await tenant_settings_repository.resolve_locale(db, active_tenant_id)
    timezone = await tenant_settings_repository.resolve_timezone(db, active_tenant_id)
    return _tenant_profile_response(profile, locale=locale, timezone=timezone)


@router.put("/tenant-profile", response_model=ProfileResponse)
async def update_tenant_profile(
    payload: ProfileUpdate,
    db: DbDep,
    current_user: CurrentUser,
    active_tenant_id: ActiveTenantId,
):
    """Update the active tenant's profile (Master support context only)."""
    if current_user.role != "master":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Master users can access this endpoint",
        )
    try:
        profile = await profile_service.update_tenant_profile_by_id(
            db, active_tenant_id, payload
        )
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.profile_not_found"),
        )
    locale = await tenant_settings_repository.resolve_locale(db, active_tenant_id)
    timezone = await tenant_settings_repository.resolve_timezone(db, active_tenant_id)
    return _tenant_profile_response(profile, locale=locale, timezone=timezone)


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
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_t(locale, "errors.incorrect_old_password"),
        )
    return {"message": "Password updated successfully"}


class DeleteAccountRequest(BaseModel):
    """Password step-up payload for Tenant Admin self-deletion."""

    password: str
    destructive_word: str


@router.post("/delete-account", status_code=status.HTTP_200_OK)
async def delete_account(
    payload: DeleteAccountRequest,
    db: DbDep,
    current_user: CurrentUser,
    active_tenant_id: ActiveTenantId,
):
    """Permanently delete the active Tenant and all owned data.

    Requires:
    - Tenant Admin role (Client and Master are denied).
    - Current password for step-up authentication.
    - Locale-aware destructive word (DELETE / ELIMINAR).
    - Active tenant (deactivated tenants require Master assistance).

    Uses the shared three-attempt/fifteen-minute step-up limiter.
    External cleanup (R2, Evolution) runs before database deletion
    and preserves the tenant on failure for safe retry.
    """
    if current_user.role != "tenant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Tenant Admins can delete their account",
        )

    # Resolve locale for destructive word validation
    locale = await tenant_settings_repository.resolve_locale(db, active_tenant_id)

    limiter = export_service.get_limiter()

    try:
        result = await delete_tenant_account(
            db=db,
            tenant_id=active_tenant_id,
            actor_user_id=current_user.id,
            password=payload.password,
            destructive_word=payload.destructive_word,
            locale=locale,
            limiter=limiter,
        )
    except StepUpError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except UserFacingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=translate_error(locale, exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return result
