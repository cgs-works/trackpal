import pytest

from app.models import Tenant, User
from app.repositories import tenants_repository

pytestmark = pytest.mark.asyncio


async def _create_tenant(
    db_session,
    *,
    username: str,
    client_prefix: str,
    name: str,
    phone: str | None,
    whatsapp_lid: str | None = None,
    is_active: bool = True,
):
    user = User(username=username, password_hash="x", role="tenant")
    db_session.add(user)
    await db_session.flush()

    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix=client_prefix,
        name=name,
        whatsapp_phone=phone,
        whatsapp_lid=whatsapp_lid,
        is_active=is_active,
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def test_get_active_by_whatsapp_identity_matches_normalized_phone(db_session):
    tenant = await _create_tenant(
        db_session,
        username="tenant_phone_lookup",
        client_prefix="tp01",
        name="Tenant Phone Lookup",
        phone="+584243106642",
    )

    found = await tenants_repository.get_active_by_whatsapp_identity(
        db_session,
        phone_digits="584243106642",
    )

    assert found is not None
    assert found.id == tenant.id


async def test_get_active_by_whatsapp_identity_matches_whatsapp_lid(db_session):
    tenant = await _create_tenant(
        db_session,
        username="tenant_lid_lookup",
        client_prefix="tl01",
        name="Tenant LID Lookup",
        phone=None,
        whatsapp_lid="77988435632309@lid",
    )

    found = await tenants_repository.get_active_by_whatsapp_identity(
        db_session,
        whatsapp_lid="77988435632309@lid",
    )

    assert found is not None
    assert found.id == tenant.id


async def test_get_active_by_whatsapp_identity_ignores_inactive_tenant(db_session):
    await _create_tenant(
        db_session,
        username="tenant_inactive_lookup",
        client_prefix="ti01",
        name="Tenant Inactive Lookup",
        phone="+584243106643",
        is_active=False,
    )

    found = await tenants_repository.get_active_by_whatsapp_identity(
        db_session,
        phone_digits="584243106643",
    )

    assert found is None


async def test_get_active_by_whatsapp_identity_returns_none_without_identity(db_session):
    found = await tenants_repository.get_active_by_whatsapp_identity(
        db_session,
        phone_digits=None,
        whatsapp_lid=None,
    )

    assert found is None
