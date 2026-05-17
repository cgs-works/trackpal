import secrets
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.input_validation import (
    InputValidationError,
    validate_email,
    validate_full_name,
    validate_phone,
    validate_username,
)
from app.core.database import restore_rls_context
from app.core.security import get_password_hash
from app.crud import users as user_crud
from app.models import RefreshSession, Tenant, User
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.services.evolution_client import evolution_client


class TenantService:
    async def create_tenant(
        self, db: AsyncSession, payload: TenantCreate
    ) -> tuple[Tenant, str | None]:
        # Defensive normalization at service layer (safety net)
        username = validate_username(payload.username)
        full_name = validate_full_name(payload.full_name)
        email = validate_email(payload.email)
        phone = validate_phone(payload.phone)

        existing_username = await user_crud.get_by_username(db, username)
        if existing_username:
            raise ValueError("Username already registered")

        if phone:
            existing = await user_crud.get_by_phone(db, phone)
            if existing:
                raise ValueError("Phone already registered")

        plain_password = payload.password
        auto_generated = plain_password is None
        if plain_password is None:
            plain_password = secrets.token_urlsafe(16)

        user = User(
            username=username,
            password_hash=get_password_hash(plain_password),
            role="tenant",
        )
        db.add(user)
        await db.flush()

        profile = Tenant(
            owner_user_id=user.id,
            name=full_name,
            email=email,
            whatsapp_phone=phone,
            evolution_instance_name=payload.evolution_instance_name,
            is_active=True,
        )
        db.add(profile)
        await db.flush()

        try:
            await evolution_client.create_instance(payload.evolution_instance_name)
            await evolution_client.setup_n8n_integration(payload.evolution_instance_name)
        except Exception as exc:
            await db.rollback()
            raise ValueError(f"Failed to create Evolution instance: {exc}") from exc

        await db.commit()
        await restore_rls_context(db)

        created_profile = await self.get_tenant(db, profile.id)
        if created_profile is None:
            raise ValueError("Tenant could not be created")
        return created_profile, plain_password if auto_generated else None

    async def get_tenants(self, db: AsyncSession) -> tuple[list[Tenant], dict]:
        result = await db.execute(
            select(Tenant)
            .options(selectinload(Tenant.owner))
            .order_by(Tenant.created_at.desc())
        )
        profiles = list(result.scalars().all())
        total = len(profiles)
        active = sum(1 for profile in profiles if profile.is_active)
        inactive = total - active
        return profiles, {"total": total, "active": active, "inactive": inactive}

    async def get_tenant(
        self, db: AsyncSession, tenant_id: UUID
    ) -> Tenant | None:
        result = await db.execute(
            select(Tenant)
            .options(selectinload(Tenant.owner))
            .where((Tenant.id == tenant_id) | (Tenant.owner_user_id == tenant_id))
        )
        return result.scalar_one_or_none()

    async def update_tenant(
        self, db: AsyncSession, tenant_id: UUID, payload: TenantUpdate
    ) -> Tenant | None:
        profile = await self.get_tenant(db, tenant_id)
        if profile is None:
            return None

        update_data = payload.model_dump(exclude_unset=True)

        # Defensive normalization at service layer
        if "full_name" in update_data and update_data["full_name"] is not None:
            update_data["full_name"] = validate_full_name(update_data["full_name"])
        if "email" in update_data:
            update_data["email"] = validate_email(update_data["email"])
        if "phone" in update_data:
            if update_data["phone"] is not None:
                update_data["phone"] = validate_phone(update_data["phone"])
            # phone=None is allowed (clearing optional field)

        # Changing evolution_instance_name only updates the stored value; it does not
        # recreate or rename the instance in Evolution API.
        if "phone" in update_data and update_data["phone"] != profile.phone:
            if update_data["phone"] is not None:
                existing = await user_crud.get_by_phone(db, update_data["phone"])
                if existing and existing[0].id != profile.owner_user_id:
                    raise ValueError("Phone already registered")

        for field, value in update_data.items():
            setattr(profile, field, value)

        await db.commit()
        await restore_rls_context(db)
        return await self.get_tenant(db, tenant_id)

    async def deactivate_tenant(
        self, db: AsyncSession, tenant_id: UUID
    ) -> Tenant | None:
        profile = await self.get_tenant(db, tenant_id)
        if profile is None:
            return None
        profile.is_active = False
        # Revoke all active refresh sessions for this tenant
        await db.execute(
            update(RefreshSession)
            .where(
                RefreshSession.user_id == profile.owner_user_id,
                RefreshSession.revoked == False,
            )
            .values(revoked=True)
        )
        await db.commit()
        await restore_rls_context(db)
        return await self.get_tenant(db, tenant_id)

    async def activate_tenant(
        self, db: AsyncSession, tenant_id: UUID
    ) -> Tenant | None:
        profile = await self.get_tenant(db, tenant_id)
        if profile is None:
            return None
        profile.is_active = True
        await db.commit()
        await restore_rls_context(db)
        return await self.get_tenant(db, tenant_id)

    async def delete_tenant(self, db: AsyncSession, tenant_id: UUID) -> bool:
        profile = await self.get_tenant(db, tenant_id)
        if profile is None:
            return False
        if profile.is_active:
            raise ValueError("Cannot delete active tenant. Deactivate first.")

        instance_name = profile.evolution_instance_name
        user = await user_crud.get(db, profile.owner_user_id)
        if user is None:
            return False

        await db.delete(user)
        await db.flush()

        try:
            if instance_name:
                await evolution_client.delete_instance(instance_name)
        except Exception as exc:
            await db.rollback()
            raise ValueError(f"Failed to delete Evolution instance: {exc}") from exc

        await db.commit()
        await restore_rls_context(db)
        return True
