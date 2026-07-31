from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "e020fe74cac0_remove_mailbox_oauth.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "remove_mailbox_oauth", MIGRATION_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def execute(self, sql: str) -> None:
        self.calls.append(("execute", (sql,), {}))

    def drop_constraint(self, name: str, table: str, type_: str = "") -> None:
        self.calls.append(("drop_constraint", (name, table, type_), {}))

    def create_check_constraint(self, name: str, table: str, condition: str) -> None:
        self.calls.append(("create_check_constraint", (name, table, condition), {}))

    def drop_column(self, table: str, column: str) -> None:
        self.calls.append(("drop_column", (table, column), {}))

    def add_column(self, table: str, column: object) -> None:
        self.calls.append(("add_column", (table, column), {}))

    def alter_column(self, table: str, column: str, **kwargs: object) -> None:
        self.calls.append(("alter_column", (table, column), kwargs))


def test_upgrade_deletes_oauth_and_verification_rows_before_dropping_columns(
    monkeypatch,
):
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    assert fake.calls[0][:2] == (
        "drop_constraint",
        ("ck_tenant_mailboxes_auth_method", "tenant_mailboxes", "check"),
    )
    sql = [call[1][0] for call in fake.calls if call[0] == "execute"]
    assert "auth_method = 'oauth'" in sql[0]
    assert "tenant_code_service_selections" in sql[1]
    assert "service_key = 'trackpal_demo'" in sql[1]
    assert "code_service_global_status" in sql[2]
    first_drop = next(
        i for i, call in enumerate(fake.calls) if call[0] == "drop_column"
    )
    last_delete = max(i for i, call in enumerate(fake.calls) if call[0] == "execute")
    assert last_delete < first_drop


def test_upgrade_drops_oauth_columns_and_auth_method(monkeypatch):
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    dropped = {call[1][1] for call in fake.calls if call[0] == "drop_column"}
    assert dropped == {
        "oauth_provider_user_id",
        "oauth_provider_email",
        "oauth_access_token_encrypted",
        "oauth_refresh_token_encrypted",
        "oauth_token_expires_at",
        "oauth_scope",
        "auth_method",
    }


def test_downgrade_restores_legacy_shape_and_global_demo_service(monkeypatch):
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    added = {call[1][1].name for call in fake.calls if call[0] == "add_column"}
    assert added == {
        "auth_method",
        "oauth_provider_user_id",
        "oauth_provider_email",
        "oauth_access_token_encrypted",
        "oauth_refresh_token_encrypted",
        "oauth_token_expires_at",
        "oauth_scope",
    }
    sql = " ".join(call[1][0] for call in fake.calls if call[0] == "execute")
    assert "SET auth_method = 'app_password'" in sql
    assert "VALUES ('trackpal_demo', true)" in sql
    constraints = [call for call in fake.calls if call[0] == "create_check_constraint"]
    assert constraints[0][1][2] == "auth_method IN ('oauth', 'app_password')"
