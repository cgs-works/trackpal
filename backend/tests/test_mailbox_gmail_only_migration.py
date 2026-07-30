"""Tests for the Gmail-only mailbox migration (e019fe74cab9).

Verifies that the upgrade drops the `provider` column and that the
downgrade restores it with correct population from auth_method.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_migration_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "e019fe74cab9_make_mailbox_gmail_only.py"
    )
    spec = importlib.util.spec_from_file_location(
        "make_mailbox_gmail_only",
        path,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    """Minimal Alembic op stub that records calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def execute(self, sql: str) -> None:
        self.calls.append(("execute", (sql,), {}))

    def alter_column(
        self,
        table_name: str,
        column_name: str,
        new_column_name: str | None = None,
        **kwargs: object,
    ) -> None:
        self.calls.append(
            ("alter_column", (table_name, column_name, new_column_name), kwargs)
        )

    def drop_column(self, table_name: str, column_name: str) -> None:
        self.calls.append(("drop_column", (table_name, column_name), {}))

    def add_column(self, table_name: str, column: object) -> None:
        self.calls.append(("add_column", (table_name, column), {}))

    def create_check_constraint(
        self, constraint_name: str, table_name: str, condition: str
    ) -> None:
        self.calls.append(
            ("create_check_constraint", (constraint_name, table_name, condition), {})
        )

    def drop_constraint(
        self, constraint_name: str, table_name: str, type_: str = ""
    ) -> None:
        self.calls.append(
            ("drop_constraint", (constraint_name, table_name, type_), {})
        )


def test_upgrade_drops_provider_column(monkeypatch) -> None:
    """Upgrade must drop `provider` after data filtering."""
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    drop_calls = [
        c for c in fake.calls if c[0] == "drop_column" and c[1][0] == "tenant_mailboxes"
    ]
    dropped_columns = {c[1][1] for c in drop_calls}
    assert "provider" in dropped_columns, (
        f"upgrade must drop `provider` column; dropped: {dropped_columns}"
    )
    # Verify provider is dropped after IMAP columns (data filtering order)
    drop_order = [c[1][1] for c in drop_calls]
    provider_idx = drop_order.index("provider")
    imap_cols = {"imap_host", "imap_port", "imap_ssl"}
    for col in imap_cols:
        assert drop_order.index(col) < provider_idx, (
            f"`{col}` must be dropped before `provider`; order: {drop_order}"
        )


def test_upgrade_creates_auth_method_check_constraint(monkeypatch) -> None:
    """Upgrade must create the auth_method IN ('oauth', 'app_password') constraint."""
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    cc_calls = [c for c in fake.calls if c[0] == "create_check_constraint"]
    assert len(cc_calls) == 1, f"expected 1 check constraint, got {len(cc_calls)}"
    args = cc_calls[0][1]
    assert args[0] == "ck_tenant_mailboxes_auth_method"
    assert "oauth" in args[2]
    assert "app_password" in args[2]


def test_downgrade_restores_provider_as_non_null(monkeypatch) -> None:
    """Downgrade must add `provider` back and make it NOT NULL after populating."""
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    # Provider must be added as nullable (populated before constraint)
    add_calls = [
        c for c in fake.calls if c[0] == "add_column" and c[1][0] == "tenant_mailboxes"
    ]
    provider_adds = [c for c in add_calls if c[1][1].name == "provider"]  # type: ignore[union-attr]
    assert len(provider_adds) == 1, (
        f"downgrade must add `provider` column; found {len(provider_adds)}"
    )
    col = provider_adds[0][1][1]  # type: ignore[index]
    assert col.nullable is True, "provider starts as nullable for population"

    # After population, must alter to NOT NULL
    alter_calls = [c for c in fake.calls if c[0] == "alter_column"]
    provider_alters = [
        c for c in alter_calls if c[1][0] == "tenant_mailboxes" and c[1][1] == "provider"
    ]
    assert len(provider_alters) == 1, (
        f"downgrade must alter provider to NOT NULL; found {len(provider_alters)}"
    )
    # The last call should be alter_column with nullable=False
    kwargs = provider_alters[0][2]
    assert kwargs.get("nullable") is False, (
        f"provider must be altered to NOT NULL; got kwargs={kwargs}"
    )


def test_downgrade_populates_provider_from_auth_method(monkeypatch) -> None:
    """Downgrade must populate provider from auth_method before making it NOT NULL."""
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    exec_calls = [c for c in fake.calls if c[0] == "execute"]
    sql_texts = " ".join(c[1][0] for c in exec_calls)  # type: ignore[index]

    # Must populate google for OAuth
    assert "provider = 'google'" in sql_texts, (
        "downgrade must set provider='google' for OAuth rows"
    )
    # Must populate imap_custom for app-password
    assert "provider = 'imap_custom'" in sql_texts, (
        "downgrade must set provider='imap_custom' for app-password rows"
    )


def test_downgrade_restores_imap_columns(monkeypatch) -> None:
    """Downgrade must add imap_host, imap_port, imap_ssl back."""
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    add_calls = [
        c for c in fake.calls if c[0] == "add_column" and c[1][0] == "tenant_mailboxes"
    ]
    added_cols = {c[1][1].name for c in add_calls}  # type: ignore[union-attr]
    assert "imap_host" in added_cols, f"missing imap_host; added: {added_cols}"
    assert "imap_port" in added_cols, f"missing imap_port; added: {added_cols}"
    assert "imap_ssl" in added_cols, f"missing imap_ssl; added: {added_cols}"


def test_downgrade_drops_check_constraint_first(monkeypatch) -> None:
    """Downgrade must drop the check constraint before restoring legacy values."""
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    first_call = fake.calls[0]
    assert first_call[0] == "drop_constraint", (
        f"downgrade must drop check constraint first; got {first_call[0]}"
    )
    assert first_call[1][0] == "ck_tenant_mailboxes_auth_method"
