import secrets
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_password_hash
from app.crud import users as user_crud
from app.models import TenantProfile, User
from app.schemas.tenant import TenantCreate, TenantUpdate


class TenantService:
    async def create_tenant(
        self, db: AsyncSession, payload: TenantCreate
    ) -> tuple[TenantProfile, str | None]:
        if payload.phone:
            existing = await user_crud.get_by_phone(db, payload.phone)
            if existing:
                raise ValueError("Phone already registered")

        plain_password = payload.password
        auto_generated = plain_password is None
        if plain_password is None:
            plain_password = secrets.token_urlsafe(16)

        user = User(
            username=payload.username,
            password_hash=get_password_hash(plain_password),
            role="tenant",
        )
        db.add(user)
        await db.flush()

        profile = TenantProfile(
            id=user.id,
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            evolution_instance_name=payload.evolution_instance_name,
            is_active=True,
        )
        db.add(profile)
        await db.commit()

        created_profile = await self.get_tenant(db, user.id)
        if created_profile is None:
            raise ValueError("Tenant could not be created")
        return created_profile, plain_password if auto_generated else None

    async def get_tenants(self, db: AsyncSession) -> tuple[list[TenantProfile], dict]:
        result = await db.execute(
            select(TenantProfile)
            .options(selectinload(TenantProfile.user))
            .order_by(TenantProfile.created_at.desc())
        )
        profiles = list(result.scalars().all())
        total = len(profiles)
        active = sum(1 for profile in profiles if profile.is_active)
        inactive = total - active
        return profiles, {"total": total, "active": active, "inactive": inactive}

    async def get_tenant(
        self, db: AsyncSession, tenant_id: UUID
    ) -> TenantProfile | None:
        result = await db.execute(
            select(TenantProfile)
            .options(selectinload(TenantProfile.user))
            .where(TenantProfile.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def update_tenant(
        self, db: AsyncSession, tenant_id: UUID, payload: TenantUpdate
    ) -> TenantProfile | None:
        profile = await self.get_tenant(db, tenant_id)
        if profile is None:
            return None

        update_data = payload.model_dump(exclude_unset=True)
        if "phone" in update_data and update_data["phone"] != profile.phone:
            existing = await user_crud.get_by_phone(db, update_data["phone"])
            if existing and existing[0].id != tenant_id:
                raise ValueError("Phone already registered")

        for field, value in update_data.items():
            setattr(profile, field, value)

        await db.commit()
        return await self.get_tenant(db, tenant_id)

    async def deactivate_tenant(
        self, db: AsyncSession, tenant_id: UUID
    ) -> TenantProfile | None:
        profile = await self.get_tenant(db, tenant_id)
        if profile is None:
            return None
        profile.is_active = False
        await db.commit()
        return await self.get_tenant(db, tenant_id)

    async def activate_tenant(
        self, db: AsyncSession, tenant_id: UUID
    ) -> TenantProfile | None:
        profile = await self.get_tenant(db, tenant_id)
        if profile is None:
            return None
        profile.is_active = True
        await db.commit()
        return await self.get_tenant(db, tenant_id)

    async def delete_tenant(self, db: AsyncSession, tenant_id: UUID) -> bool:
        profile = await self.get_tenant(db, tenant_id)
        if profile is None:
            return False
        if profile.is_active:
            raise ValueError("Cannot delete active tenant. Deactivate first.")

        user = await user_crud.get(db, tenant_id)
        if user is None:
            return False
        await db.delete(user)
        await db.commit()
        return True
