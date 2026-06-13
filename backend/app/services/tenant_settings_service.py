"""TenantSettings service — business logic for tenant i18n and timezone settings."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import VALID_LOCALES
from app.core.database import restore_rls_context
from app.models import TenantSettings
from app.repositories import tenant_settings_repository
from app.schemas.tenant_settings import TenantSettingsUpdate
from app.services.subscription_service.timezone_catalog import validate_timezone


class TenantSettingsService:
    async def get_settings(
        self, db: AsyncSession, tenant_id: uuid.UUID
    ) -> TenantSettings:
        settings, created = await tenant_settings_repository.get_or_create_by_tenant_id(
            db, tenant_id
        )
        if created:
            await db.commit()
            await restore_rls_context(db)
            await db.refresh(settings)
        return settings

    async def update_settings(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: TenantSettingsUpdate,
    ) -> TenantSettings:
        update_data = payload.model_dump(exclude_unset=True)

        locale = update_data.get("locale")
        if locale is not None and locale not in VALID_LOCALES:
            raise ValueError(f"Locale must be one of: {', '.join(VALID_LOCALES)}")

        timezone = update_data.get("timezone")
        if timezone is not None and not validate_timezone(str(timezone)):
            raise ValueError(f"'{timezone}' is not a valid IANA timezone identifier")

        settings = await tenant_settings_repository.update_settings(
            db, tenant_id, update_data
        )
        await db.commit()
        await restore_rls_context(db)
        await db.refresh(settings)
        return settings
