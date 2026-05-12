from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, DbDep
from app.schemas.me import PasswordChange, ProfileResponse, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/me", tags=["me"])
profile_service = ProfileService()


def _profile_response(user, profile) -> ProfileResponse:
    return ProfileResponse(
        role=user.role,
        username=user.username,
        name=getattr(profile, "name", None),
        full_name=getattr(profile, "full_name", None),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found"
        )
    return _profile_response(current_user, profile)


@router.put("", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate, db: DbDep, current_user: CurrentUser
):
    try:
        profile = await profile_service.update_profile(db, current_user, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found"
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect old password"
        )
    return {"message": "Password updated successfully"}
