from __future__ import annotations

import importlib.util
from pathlib import Path

from app.models import Tenant


def _load_migration_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "e026fe74cac6_remove_tenant_email.py"
    )
    spec = importlib.util.spec_from_file_location("remove_tenant_email", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def drop_column(self, table_name: str, column_name: str) -> None:
        self.calls.append(("drop_column", (table_name, column_name)))

    def add_column(self, table_name: str, column: object) -> None:
        self.calls.append(("add_column", (table_name, column)))


def test_tenant_model_has_no_legacy_email_column():
    assert "email" not in Tenant.__table__.columns


def test_upgrade_drops_tenant_email(monkeypatch):
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    assert fake.calls == [("drop_column", ("tenants", "email"))]


def test_downgrade_restores_nullable_tenant_email(monkeypatch):
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    assert len(fake.calls) == 1
    operation, (table_name, column) = fake.calls[0]
    assert operation == "add_column"
    assert table_name == "tenants"
    assert column.name == "email"
    assert column.nullable is True
    assert str(column.type) == "VARCHAR(255)"
