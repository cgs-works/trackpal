from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UserFacingError
from app.core.input_validation import (
    validate_email,
    validate_full_name,
    validate_phone,
    validate_password_policy,
)
from app.core.security import get_password_hash, verify_password
from app.repositories import (
    profiles_repository,
    sessions_repository,
    tenants_repository,
    users_repository,
)
from app.models import Client, MasterProfile, Tenant, User
from app.schemas.me import ProfileUpdate


class ProfileService:
    async def get_profile(
        self, db: AsyncSession, user: User
    ) -> MasterProfile | Tenant | Client | None:
        if user.role == "master":
            return await profiles_repository.get_master_profile(db, user.id)

        if user.role == "client":
            return await profiles_repository.get_client_profile(db, user.id)

        return await profiles_repository.get_tenant_profile(db, user.id)

    async def update_profile(
        self, db: AsyncSession, user: User, payload: ProfileUpdate
    ) -> MasterProfile | Tenant | None:
        profile = await self.get_profile(db, user)
        if profile is None:
            return None

        if user.role == "client":
            raise PermissionError("Client profile is read-only")

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

        allowed_fields: set[str] = (
            {"name", "phone"}
            if user.role == "master"
            else {"full_name", "email", "phone"}
        )

        # Duplicate check using normalized phone
        if "phone" in update_data and update_data["phone"] != profile.phone:
            if update_data["phone"] is not None:
                existing = await users_repository.get_by_phone(db, update_data["phone"])
                if existing and existing[0].id != user.id:
                    raise UserFacingError("profile_phone_registered")

        for field, value in update_data.items():
            if field in allowed_fields:
                setattr(profile, field, value)

        await db.commit()
        return await self.get_profile(db, user)

    async def get_tenant_profile_by_id(
        self, db: AsyncSession, tenant_id: UUID
    ) -> Tenant | None:
        """Get a tenant profile by its id (for Master support context)."""
        return await tenants_repository.get(db, tenant_id)

    async def update_tenant_profile_by_id(
        self, db: AsyncSession, tenant_id: UUID, payload: ProfileUpdate
    ) -> Tenant | None:
        """Update a tenant profile by its id (for Master support context)."""
        profile = await self.get_tenant_profile_by_id(db, tenant_id)
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

        # Duplicate phone check (skip if same value)
        if "phone" in update_data and update_data["phone"] != profile.phone:
            if update_data["phone"] is not None:
                existing = await users_repository.get_by_phone(db, update_data["phone"])
                if existing and existing[0].id != profile.owner_user_id:
                    raise UserFacingError("profile_phone_registered")

        # Map frontend field names to Tenant model fields
        field_mapping = {
            "full_name": "name",
            "email": "email",
            "phone": "whatsapp_phone",
        }
        for frontend_field, model_field in field_mapping.items():
            if frontend_field in update_data:
                setattr(profile, model_field, update_data[frontend_field])

        await db.commit()
        return await self.get_tenant_profile_by_id(db, tenant_id)

    async def change_password(
        self, db: AsyncSession, user: User, old_password: str, new_password: str
    ) -> bool:
        new_password = validate_password_policy(new_password)
        if not verify_password(old_password, user.password_hash):
            return False

        user.password_hash = get_password_hash(new_password)
        if user.role == "tenant":
            tenant = await tenants_repository.get_by_owner(db, user.id)
            if tenant is not None and tenant.is_demo:
                await db.execute(
                    update(Tenant)
                    .where(Tenant.id == tenant.id, Tenant.is_demo.is_(True))
                    .values(
                        demo_credentials_version=Tenant.demo_credentials_version + 1
                    )
                )
                await sessions_repository.revoke_all_for_user(db, user.id)
        await db.commit()
        return True
