from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "e021fe74cac1_add_service_icon.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("add_service_icon", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []

    def add_column(self, table: str, column: object) -> None:
        self.calls.append(("add_column", table, column))

    def drop_column(self, table: str, column: str) -> None:
        self.calls.append(("drop_column", table, column))


def test_upgrade_adds_nullable_icon_column(monkeypatch):
    module = _load_migration_module()
    fake = FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    _, table, column = fake.calls[0]
    assert table == "services"
    assert column.name == "icon"
    assert column.type.length == 255
    assert column.nullable is True


def test_downgrade_removes_icon_column(monkeypatch):
    module = _load_migration_module()
    fake = FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    assert fake.calls == [("drop_column", "services", "icon")]
