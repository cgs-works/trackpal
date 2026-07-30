from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_migration_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "e013fe74cab3_remove_blocked_clients_is_active.py"
    )
    spec = importlib.util.spec_from_file_location(
        "remove_blocked_clients_is_active", path
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str) -> None:
        self.calls.append(("execute", (sql,)))

    def drop_column(self, table_name: str, column_name: str) -> None:
        self.calls.append(("drop_column", (table_name, column_name)))

    def add_column(self, table_name: str, column: object) -> None:
        self.calls.append(("add_column", (table_name, column)))


def test_upgrade_deletes_inactive_rows_before_dropping_is_active(monkeypatch) -> None:
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    assert fake.calls[0] == (
        "execute",
        ("DELETE FROM blocked_clients WHERE is_active IS FALSE",),
    )
    assert fake.calls[1] == ("drop_column", ("blocked_clients", "is_active"))


def test_downgrade_restores_is_active_column(monkeypatch) -> None:
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    assert fake.calls[0][0] == "add_column"
    assert fake.calls[0][1][0] == "blocked_clients"
    column = fake.calls[0][1][1]
    assert column.name == "is_active"
    assert column.nullable is False
