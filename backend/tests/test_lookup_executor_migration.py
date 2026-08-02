"""Offline SQL contracts for the lookup executor migration."""

import importlib.util
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


_MIGRATION_PATH = Path("alembic/versions/e023fe74cac3_add_lookup_executors.py")
_spec = importlib.util.spec_from_file_location(
    "lookup_executor_migration", _MIGRATION_PATH
)
assert _spec is not None and _spec.loader is not None
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def _render_migration(operation) -> str:
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    with Operations.context(context):
        operation()
    return output.getvalue()


def test_upgrade_creates_master_only_rls_executor_registry_and_job_metadata():
    sql = _render_migration(migration.upgrade)

    assert "CREATE TABLE lookup_executors" in sql
    assert "ALTER TABLE mail_lookup_jobs ADD COLUMN executor_id" in sql
    assert (
        "FOREIGN KEY(executor_id) REFERENCES lookup_executors (id) ON DELETE SET NULL"
        in sql
    )
    assert "ALTER TABLE lookup_executors ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE lookup_executors FORCE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY lookup_executors_master_only ON lookup_executors" in sql
    assert "current_setting('app.current_role', true) = 'master'" in sql
    assert "DROP COLUMN result_value_encrypted" in sql


def test_downgrade_restores_result_column_and_removes_executor_registry():
    sql = _render_migration(migration.downgrade)

    assert "ADD COLUMN result_value_encrypted" in sql
    assert "DROP TABLE lookup_executors" in sql
    assert "DROP COLUMN executor_id" in sql
    assert "DROP COLUMN execution_attempts" in sql
    assert "DROP COLUMN last_dispatch_error_safe" in sql


def test_migration_file_has_expected_revision_chain():
    text = _MIGRATION_PATH.read_text()

    assert migration.revision == "e023fe74cac3"
    assert migration.down_revision == "e022fe74cac2"
    assert "lookup_executors_master_only" in text
