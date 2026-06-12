import pytest
from sqlalchemy import select

from app.models import Tenant, TenantSettings

pytestmark = pytest.mark.asyncio


async def _tenant_for_user(db_session, user_id):
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user_id)
    )
    return result.scalar_one()


async def test_tenant_settings_model_defaults_persist(db_session, active_tenant_user):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)

    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    settings = result.scalar_one()

    assert settings.tenant_id == tenant.id
    assert settings.locale == "en"
    assert settings.timezone == "UTC"
    assert settings.created_at is not None
    assert settings.updated_at is not None


async def test_tenant_settings_can_store_locale_and_timezone(db_session, active_tenant_user):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    settings = result.scalar_one()

    settings.locale = "es"
    settings.timezone = "America/Santo_Domingo"
    await db_session.commit()

    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    persisted = result.scalar_one()
    assert persisted.locale == "es"
    assert persisted.timezone == "America/Santo_Domingo"
