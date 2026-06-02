"""Tests for WhatsApp client context shortcut behavior.

This module houses repository/model contract tests that the WhatsApp
client shortcut flow relies on. The first test guards the renamed
`blocked_clients` model so the shortcut path can confidently import
the new symbols.
"""

from __future__ import annotations


def test_blocked_clients_repository_uses_new_table_name() -> None:
    """The renamed repository's model must bind to the new table name.

    This guards the migration: the SQLAlchemy ``__tablename__`` must be
    ``blocked_clients`` so the rename migration has something to point at.
    """
    from app.models.blocked_client import BlockedClient

    assert BlockedClient.__tablename__ == "blocked_clients"


def test_blocked_clients_repository_module_is_importable() -> None:
    """The new repository module must exist and expose the expected API."""
    from app.repositories import blocked_clients_repository

    expected = {"create", "list_active", "find_active", "unblock", "clear_identity"}
    assert expected.issubset(set(dir(blocked_clients_repository)))


def test_models_package_exports_blocked_client() -> None:
    """The models package should re-export the renamed ``BlockedClient``."""
    from app import models

    assert hasattr(models, "BlockedClient")
    assert "BlockedClient" in models.__all__
    assert "ClientMessagingBlock" not in models.__all__
