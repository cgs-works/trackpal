import secrets
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.input_validation import (
    InputValidationError,
    validate_client_prefix,
    validate_email,
    validate_full_name,
    validate_phone,
    validate_username,
)
from app.core.database import get_rls_context, restore_rls_context, set_internal_tenant_rls_context, set_rls_context
from app.core.security import get_password_hash
from app.crud import users as user_crud
from app.models import Client, RefreshSession, Tenant, User
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.models.tenant import _default_client_prefix
from app.services.client_service import ClientService
from app.services.evolution_client import evolution_client


class TenantService:
    def __init__(self) -> None:
        self.client_service = ClientService()

    async def _client_prefix_exists(
        self, db: AsyncSession, client_prefix: str, exclude_tenant_id: UUID | None = None
    ) -> bool:
        stmt = select(Tenant.id).where(func.lower(Tenant.client_prefix) == client_prefix.lower())
        if exclude_tenant_id is not None:
            stmt = stmt.where(Tenant.id != exclude_tenant_id)
        return (await db.execute(stmt)).first() is not None

    async def _generate_unique_client_prefix(self, db: AsyncSession) -> str:
        for _ in range(20):
            candidate = _default_client_prefix()
            if not await self._client_prefix_exists(db, candidate):
                return candidate
        raise ValueError("Unable to generate unique client prefix")

    async def create_tenant(
        self, db: AsyncSession, payload: TenantCreate
    ) -> tuple[Tenant, str | None]:
        # Defensive normalization at service layer (safety net)
        username = validate_username(payload.username)
        full_name = validate_full_name(payload.full_name)
        email = validate_email(payload.email)
        phone = validate_phone(payload.phone)
        client_prefix = payload.client_prefix or await self._generate_unique_client_prefix(db)

        if payload.client_prefix and await self._client_prefix_exists(db, client_prefix):
            raise ValueError("Prefijo de cliente ya registrado")

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
            client_prefix=client_prefix,
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

        if "client_prefix" in update_data and update_data["client_prefix"] is not None:
            update_data["client_prefix"] = validate_client_prefix(
                update_data["client_prefix"]
            )

        # Changing evolution_instance_name only updates the stored value; it does not
        # recreate or rename the instance in Evolution API.
        if "phone" in update_data and update_data["phone"] != profile.phone:
            if update_data["phone"] is not None:
                existing = await user_crud.get_by_phone(db, update_data["phone"])
                if existing and existing[0].id != profile.owner_user_id:
                    raise ValueError("Phone already registered")

        if "client_prefix" in update_data and update_data["client_prefix"] != profile.client_prefix:
            if await self._client_prefix_exists(db, update_data["client_prefix"], profile.id):
                raise ValueError("Prefijo de cliente ya registrado")
            await self.client_service.sync_client_usernames_for_tenant(
                db, profile.id, update_data["client_prefix"]
            )

        for field, value in update_data.items():
            setattr(profile, field, value)

        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError("No se pudo actualizar el prefijo de cliente") from exc
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

        previous_context = get_rls_context(db)
        await set_internal_tenant_rls_context(db, str(profile.id))
        try:
            result = await db.execute(
                select(User)
                .join(Client, Client.owner_user_id == User.id)
                .where(Client.tenant_id == profile.id)
            )
            client_users = list(result.scalars().all())
            for client_user in client_users:
                await db.delete(client_user)
            await db.delete(user)
            await db.flush()
        finally:
            if previous_context is not None:
                await set_rls_context(
                    db,
                    previous_context["user_id"],
                    previous_context["role"],
                    previous_context["active_tenant_id"],
                )

        try:
            if instance_name:
                await evolution_client.delete_instance(instance_name)
        except Exception as exc:
            await db.rollback()
            raise ValueError(f"Failed to delete Evolution instance: {exc}") from exc

        await db.commit()
        await restore_rls_context(db)
        return True
