from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_migration_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "e016fe74cab6_add_export_job_lifecycle_columns.py"
    )
    spec = importlib.util.spec_from_file_location(
        "add_export_job_lifecycle_columns",
        path,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []

    def add_column(self, table_name: str, column: object) -> None:
        self.calls.append(("add_column", table_name, column))

    def drop_column(self, table_name: str, column_name: str) -> None:
        self.calls.append(("drop_column", table_name, column_name))


def test_upgrade_adds_export_job_lifecycle_columns(monkeypatch) -> None:
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    assert [call[2].name for call in fake.calls] == [
        "failed_at",
        "cooldown_until",
        "actor_role",
    ]
    assert all(call[0] == "add_column" for call in fake.calls)
    assert all(call[1] == "export_jobs" for call in fake.calls)
    assert all(call[2].nullable is True for call in fake.calls)


def test_downgrade_removes_export_job_lifecycle_columns(monkeypatch) -> None:
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    assert fake.calls == [
        ("drop_column", "export_jobs", "actor_role"),
        ("drop_column", "export_jobs", "cooldown_until"),
        ("drop_column", "export_jobs", "failed_at"),
    ]
