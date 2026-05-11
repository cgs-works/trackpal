from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models import MasterProfile, TenantProfile, User
from app.schemas.me import ProfileUpdate


class ProfileService:
    async def get_profile(
        self, db: AsyncSession, user: User
    ) -> MasterProfile | TenantProfile | None:
        if user.role == "master":
            result = await db.execute(
                select(MasterProfile).where(MasterProfile.id == user.id)
            )
            return result.scalar_one_or_none()

        result = await db.execute(
            select(TenantProfile).where(TenantProfile.id == user.id)
        )
        return result.scalar_one_or_none()

    async def update_profile(
        self, db: AsyncSession, user: User, payload: ProfileUpdate
    ) -> MasterProfile | TenantProfile | None:
        profile = await self.get_profile(db, user)
        if profile is None:
            return None

        update_data = payload.model_dump(exclude_unset=True)
        allowed_fields = (
            {"name", "phone"}
            if user.role == "master"
            else {"full_name", "email", "phone"}
        )
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
