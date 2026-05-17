from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.input_validation import (
    InputValidationError,
    validate_email,
    validate_full_name,
    validate_phone,
)
from app.core.security import get_password_hash, verify_password
from app.crud import users as user_crud
from app.models import MasterProfile, Tenant, User
from app.schemas.me import ProfileUpdate


class ProfileService:
    async def get_profile(
        self, db: AsyncSession, user: User
    ) -> MasterProfile | Tenant | None:
        if user.role == "master":
            result = await db.execute(
                select(MasterProfile).where(MasterProfile.id == user.id)
            )
            return result.scalar_one_or_none()

        result = await db.execute(
            select(Tenant).where(Tenant.owner_user_id == user.id)
        )
        return result.scalar_one_or_none()

    async def update_profile(
        self, db: AsyncSession, user: User, payload: ProfileUpdate
    ) -> MasterProfile | Tenant | None:
        profile = await self.get_profile(db, user)
        if profile is None:
            return None

        update_data = payload.model_dump(exclude_unset=True)

        # Defensive normalization at service layer
        if "full_name" in update_data and update_data["full_name"] is not None:
            update_data["full_name"] = validate_full_name(update_data["full_name"])
        if "name" in update_data and update_data["name"] is not None:
            update_data["name"] = validate_full_name(update_data["name"])
        if "email" in update_data:
            update_data["email"] = validate_email(update_data["email"])
        if "phone" in update_data:
            if update_data["phone"] is not None:
                update_data["phone"] = validate_phone(update_data["phone"])
            # phone=None is allowed (clearing optional field)

        allowed_fields = (
            {"name", "phone"}
            if user.role == "master"
            else {"full_name", "email", "phone"}
        )

        # Duplicate check using normalized phone
        if "phone" in update_data and update_data["phone"] != profile.phone:
            if update_data["phone"] is not None:
                existing = await user_crud.get_by_phone(db, update_data["phone"])
                if existing and existing[0].id != user.id:
                    raise ValueError("Phone already registered")

        for field, value in update_data.items():
            if field in allowed_fields:
                setattr(profile, field, value)

        await db.commit()
        return await self.get_profile(db, user)

    async def change_password(
        self, db: AsyncSession, user: User, old_password: str, new_password: str
    ) -> bool:
        if not verify_password(old_password, user.password_hash):
            return False

        user.password_hash = get_password_hash(new_password)
        await db.commit()
        return True
