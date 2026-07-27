from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import DemoTenantStatus, Tenant, TenantSettings, User
from app.repositories import tenants_repository

pytestmark = pytest.mark.asyncio


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


async def _create_tenant(
    db_session,
    *,
    username: str,
    client_prefix: str,
    is_demo: bool = False,
    demo_activated_at: datetime | None = None,
    demo_expires_at: datetime | None = None,
    demo_credentials_version: int = 1,
) -> Tenant:
    user = User(username=username, password_hash="hashed", role="tenant")
    db_session.add(user)
    await db_session.flush()

    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix=client_prefix,
        name=username,
        is_demo=is_demo,
        demo_activated_at=demo_activated_at,
        demo_expires_at=demo_expires_at,
        demo_credentials_version=demo_credentials_version,
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def test_tenant_defaults_to_production_lifecycle_values(db_session):
    tenant = await _create_tenant(
        db_session,
        username="production_defaults",
        client_prefix="pd01",
    )

    assert tenant.is_demo is False
    assert tenant.demo_activated_at is None
    assert tenant.demo_expires_at is None
    assert tenant.demo_credentials_version == 1
    assert tenant.get_demo_status(NOW) is None


async def test_demo_status_is_derived_from_lifecycle_timestamps(db_session):
    pending = await _create_tenant(
        db_session,
        username="demo_pending",
        client_prefix="dp01",
        is_demo=True,
    )
    active = await _create_tenant(
        db_session,
        username="demo_active",
        client_prefix="da01",
        is_demo=True,
        demo_activated_at=NOW - timedelta(hours=1),
        demo_expires_at=NOW + timedelta(hours=47),
    )
    expired = await _create_tenant(
        db_session,
        username="demo_expired",
        client_prefix="de01",
        is_demo=True,
        demo_activated_at=NOW - timedelta(hours=49),
        demo_expires_at=NOW - timedelta(hours=1),
    )

    assert pending.get_demo_status(NOW) is DemoTenantStatus.PENDING
    assert active.get_demo_status(NOW) is DemoTenantStatus.ACTIVE
    assert expired.get_demo_status(NOW) is DemoTenantStatus.EXPIRED
    assert active.get_demo_status(active.demo_expires_at) is DemoTenantStatus.EXPIRED


async def test_repository_separates_production_and_demo_tenants(db_session):
    production = await _create_tenant(
        db_session,
        username="production_listed",
        client_prefix="pl01",
    )
    pending = await _create_tenant(
        db_session,
        username="demo_listed_pending",
        client_prefix="dlp1",
        is_demo=True,
    )
    active = await _create_tenant(
        db_session,
        username="demo_listed_active",
        client_prefix="dla1",
        is_demo=True,
        demo_activated_at=NOW - timedelta(hours=1),
        demo_expires_at=NOW + timedelta(hours=47),
    )
    expired = await _create_tenant(
        db_session,
        username="demo_listed_expired",
        client_prefix="dle1",
        is_demo=True,
        demo_activated_at=NOW - timedelta(hours=49),
        demo_expires_at=NOW - timedelta(hours=1),
    )

    tenants, meta = await tenants_repository.get_all(db_session)
    stats = await tenants_repository.get_stats(db_session)
    demos = await tenants_repository.get_demos(db_session)
    active_demos = await tenants_repository.get_demos(
        db_session, status=DemoTenantStatus.ACTIVE, now=NOW
    )
    expired_demos = await tenants_repository.get_expired_demos(db_session, now=NOW)

    assert [tenant.id for tenant in tenants] == [production.id]
    assert meta == {"total": 1, "active": 1, "inactive": 0}
    assert stats == {"total": 1, "active": 1, "inactive": 0}
    assert {tenant.id for tenant in demos} == {pending.id, active.id, expired.id}
    assert [tenant.id for tenant in active_demos] == [active.id]
    assert [tenant.id for tenant in expired_demos] == [expired.id]


async def test_demo_identity_does_not_require_business_or_settings_rows(db_session):
    tenant = await _create_tenant(
        db_session,
        username="demo_identity_only",
        client_prefix="dio1",
        is_demo=True,
    )

    settings = await db_session.scalar(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )

    assert settings is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"is_demo": True, "demo_activated_at": NOW},
        {
            "is_demo": True,
            "demo_activated_at": NOW,
            "demo_expires_at": NOW - timedelta(seconds=1),
        },
        {
            "is_demo": False,
            "demo_activated_at": NOW,
            "demo_expires_at": NOW + timedelta(hours=48),
        },
    ],
)
async def test_demo_lifecycle_constraints_reject_invalid_values(db_session, overrides):
    user = User(
        username=f"invalid_demo_{len(overrides)}_{overrides['is_demo']}",
        password_hash="hashed",
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Tenant(
            owner_user_id=user.id,
            client_prefix=f"iv{len(overrides)}{int(overrides['is_demo'])}",
            name="Invalid demo",
            **overrides,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


def _load_migration_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "e017fe74cab7_add_demo_tenant_lifecycle.py"
    )
    spec = importlib.util.spec_from_file_location("add_demo_tenant_lifecycle", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def add_column(self, table_name: str, column: object) -> None:
        self.calls.append(("add_column", (table_name, column)))

    def create_check_constraint(
        self, name: str, table_name: str, condition: str
    ) -> None:
        self.calls.append(("create_check_constraint", (name, table_name, condition)))

    def create_index(self, name: str, table_name: str, columns: list[str]) -> None:
        self.calls.append(("create_index", (name, table_name, columns)))

    def drop_constraint(self, name: str, table_name: str, *, type_: str) -> None:
        self.calls.append(("drop_constraint", (name, table_name, type_)))

    def drop_index(self, name: str, *, table_name: str) -> None:
        self.calls.append(("drop_index", (name, table_name)))

    def drop_column(self, table_name: str, column_name: str) -> None:
        self.calls.append(("drop_column", (table_name, column_name)))


async def test_migration_adds_production_safe_demo_columns_and_constraints(monkeypatch):
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    columns = {
        call[1][1].name: call[1][1] for call in fake.calls if call[0] == "add_column"
    }
    assert set(columns) == {
        "is_demo",
        "demo_activated_at",
        "demo_expires_at",
        "demo_credentials_version",
    }
    assert columns["is_demo"].nullable is False
    assert str(columns["is_demo"].server_default.arg) == "false"
    assert columns["demo_activated_at"].nullable is True
    assert columns["demo_expires_at"].nullable is True
    assert columns["demo_credentials_version"].nullable is False
    assert str(columns["demo_credentials_version"].server_default.arg) == "1"

    constraints = [
        call[1][0] for call in fake.calls if call[0] == "create_check_constraint"
    ]
    assert constraints == [
        module.DEMO_LIFECYCLE_PAIR_CONSTRAINT,
        module.DEMO_LIFECYCLE_ORDER_CONSTRAINT,
        module.DEMO_PRODUCTION_DEFAULTS_CONSTRAINT,
        module.DEMO_CREDENTIALS_VERSION_CONSTRAINT,
    ]
    assert (
        "ix_tenants_demo_lifecycle",
        "tenants",
        ["is_demo", "demo_expires_at"],
    ) in [call[1] for call in fake.calls if call[0] == "create_index"]


async def test_migration_downgrade_removes_demo_schema_in_reverse_order(monkeypatch):
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    assert fake.calls == [
        (
            "drop_constraint",
            (module.DEMO_CREDENTIALS_VERSION_CONSTRAINT, "tenants", "check"),
        ),
        (
            "drop_constraint",
            (module.DEMO_PRODUCTION_DEFAULTS_CONSTRAINT, "tenants", "check"),
        ),
        (
            "drop_constraint",
            (module.DEMO_LIFECYCLE_ORDER_CONSTRAINT, "tenants", "check"),
        ),
        (
            "drop_constraint",
            (module.DEMO_LIFECYCLE_PAIR_CONSTRAINT, "tenants", "check"),
        ),
        ("drop_index", ("ix_tenants_demo_lifecycle", "tenants")),
        ("drop_column", ("tenants", "demo_credentials_version")),
        ("drop_column", ("tenants", "demo_expires_at")),
        ("drop_column", ("tenants", "demo_activated_at")),
        ("drop_column", ("tenants", "is_demo")),
    ]


async def test_demo_model_has_lifecycle_index_and_constraints():
    table = Tenant.__table__

    assert "ix_tenants_demo_lifecycle" in {index.name for index in table.indexes}
    assert {
        "ck_tenants_demo_lifecycle_pair",
        "ck_tenants_demo_lifecycle_order",
        "ck_tenants_demo_production_defaults",
        "ck_tenants_demo_credentials_version",
    } <= {constraint.name for constraint in table.constraints}


async def test_demo_version_cannot_be_non_positive(db_session):
    with pytest.raises(IntegrityError):
        await _create_tenant(
            db_session,
            username="demo_invalid_version",
            client_prefix="div1",
            is_demo=True,
            demo_credentials_version=0,
        )

    await db_session.rollback()


async def test_demo_status_uses_supplied_authoritative_time(db_session):
    tenant = await _create_tenant(
        db_session,
        username="demo_authoritative_time",
        client_prefix="dat1",
        is_demo=True,
        demo_activated_at=NOW,
        demo_expires_at=NOW + timedelta(hours=48),
    )

    assert tenant.get_demo_status(NOW + timedelta(hours=47)) is DemoTenantStatus.ACTIVE
    assert tenant.get_demo_status(NOW + timedelta(hours=48)) is DemoTenantStatus.EXPIRED
