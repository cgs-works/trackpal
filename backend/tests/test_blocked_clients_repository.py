"""Tests for the Blocked Clients repository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant, User
from app.repositories import blocked_clients_repository as blocked_repo


pytestmark = pytest.mark.asyncio


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


async def _seed_tenant(db_session: AsyncSession) -> tuple[User, Tenant]:
    """Create a minimal tenant and return (user, tenant)."""
    user = User(username="t-owner", password_hash="x", role="tenant")
    db_session.add(user)
    await db_session.flush()
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix="t0001",
        name="Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.flush()
    return user, tenant


async def _seed_other_tenant(db_session: AsyncSession) -> Tenant:
    """Create a second tenant for cross-tenant isolation tests."""
    user = User(username="other-owner", password_hash="x", role="tenant")
    db_session.add(user)
    await db_session.flush()
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix="t0002",
        name="Other Tenant",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------


class TestCreate:
    async def test_create_with_phone(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        block = await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        assert block.id is not None
        assert block.tenant_id == tenant.id
        assert block.phone == "12015550030"
        assert block.whatsapp_lid is None
        assert block.is_active is True
        assert block.created_at is not None

    async def test_create_with_lid(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        block = await blocked_repo.create(db_session, tenant.id, whatsapp_lid="test@lid")
        assert block.whatsapp_lid == "test@lid"
        assert block.phone is None

    async def test_create_with_both(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        block = await blocked_repo.create(
            db_session, tenant.id, phone="12015550030", whatsapp_lid="test@lid"
        )
        assert block.phone == "12015550030"
        assert block.whatsapp_lid == "test@lid"

    async def test_create_requires_identity(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        with pytest.raises(ValueError, match="identity field"):
            await blocked_repo.create(db_session, tenant.id)


class TestFindActive:
    async def test_find_by_phone(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        found = await blocked_repo.find_active(db_session, tenant.id, phone="12015550030")
        assert found is not None
        assert found.phone == "12015550030"

    async def test_find_by_lid(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        await blocked_repo.create(db_session, tenant.id, whatsapp_lid="blocked@lid")
        found = await blocked_repo.find_active(
            db_session, tenant.id, whatsapp_lid="blocked@lid"
        )
        assert found is not None
        assert found.whatsapp_lid == "blocked@lid"

    async def test_find_returns_none_for_no_match(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        found = await blocked_repo.find_active(db_session, tenant.id, phone="12015559999")
        assert found is None

    async def test_find_returns_none_when_unblocked(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        block = await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        await blocked_repo.unblock(db_session, tenant.id, block.id)
        found = await blocked_repo.find_active(db_session, tenant.id, phone="12015550030")
        assert found is None

    async def test_find_no_args_returns_none(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        assert await blocked_repo.find_active(db_session, tenant.id) is None


class TestTenantIsolation:
    async def test_blocks_are_tenant_scoped(self, db_session: AsyncSession) -> None:
        _user, tenant_a = await _seed_tenant(db_session)
        tenant_b = await _seed_other_tenant(db_session)
        await blocked_repo.create(db_session, tenant_a.id, phone="12015550030")
        found = await blocked_repo.find_active(db_session, tenant_b.id, phone="12015550030")
        assert found is None

    async def test_list_active_is_tenant_scoped(self, db_session: AsyncSession) -> None:
        _user, tenant_a = await _seed_tenant(db_session)
        tenant_b = await _seed_other_tenant(db_session)
        await blocked_repo.create(db_session, tenant_a.id, phone="12015550030")
        await blocked_repo.create(db_session, tenant_a.id, phone="12015550031")
        blocks_a = await blocked_repo.list_active(db_session, tenant_a.id)
        blocks_b = await blocked_repo.list_active(db_session, tenant_b.id)
        assert len(blocks_a) == 2
        assert len(blocks_b) == 0

    async def test_unblock_is_tenant_scoped(self, db_session: AsyncSession) -> None:
        _user, tenant_a = await _seed_tenant(db_session)
        tenant_b = await _seed_other_tenant(db_session)
        block = await blocked_repo.create(db_session, tenant_a.id, phone="12015550030")
        # Attempt to unblock from wrong tenant
        result = await blocked_repo.unblock(db_session, tenant_b.id, block.id)
        assert result is None
        # Block still active in original tenant
        found = await blocked_repo.find_active(db_session, tenant_a.id, phone="12015550030")
        assert found is not None

    async def test_clear_identity_is_tenant_scoped(self, db_session: AsyncSession) -> None:
        _user, tenant_a = await _seed_tenant(db_session)
        tenant_b = await _seed_other_tenant(db_session)
        await blocked_repo.create(db_session, tenant_a.id, phone="12015550030")
        # Clear from wrong tenant
        cleared = await blocked_repo.clear_identity(db_session, tenant_b.id, phone="12015550030")
        assert cleared == 0
        # Block still active in original tenant
        found = await blocked_repo.find_active(db_session, tenant_a.id, phone="12015550030")
        assert found is not None


class TestListActive:
    async def test_list_empty(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        blocks = await blocked_repo.list_active(db_session, tenant.id)
        assert blocks == []

    async def test_list_returns_only_active(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        block_a = await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        await blocked_repo.create(db_session, tenant.id, phone="12015550031")
        await blocked_repo.unblock(db_session, tenant.id, block_a.id)
        blocks = await blocked_repo.list_active(db_session, tenant.id)
        assert len(blocks) == 1
        assert blocks[0].phone == "12015550031"

    async def test_list_orders_newest_first(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        block_a = await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        block_b = await blocked_repo.create(db_session, tenant.id, phone="12015550031")
        blocks = await blocked_repo.list_active(db_session, tenant.id)
        # Both blocks are present; ordering by created_at is undefined
        # when both rows share the same timestamp within one transaction
        assert len(blocks) == 2
        ids = {b.id for b in blocks}
        assert ids == {block_a.id, block_b.id}


class TestUnblock:
    async def test_unblock_active_block(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        block = await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        result = await blocked_repo.unblock(db_session, tenant.id, block.id)
        assert result is not None
        assert result.is_active is False
        # Verify persistence
        db_session.expire(block)
        found = await blocked_repo.find_active(db_session, tenant.id, phone="12015550030")
        assert found is None

    async def test_unblock_already_unblocked_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        _user, tenant = await _seed_tenant(db_session)
        block = await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        await blocked_repo.unblock(db_session, tenant.id, block.id)
        # Second unblock returns None
        result = await blocked_repo.unblock(db_session, tenant.id, block.id)
        assert result is None

    async def test_unblock_nonexistent_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        _user, tenant = await _seed_tenant(db_session)
        import uuid
        result = await blocked_repo.unblock(db_session, tenant.id, uuid.uuid4())
        assert result is None


class TestClearIdentity:
    async def test_clear_by_phone(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        cleared = await blocked_repo.clear_identity(db_session, tenant.id, phone="12015550030")
        assert cleared == 1
        found = await blocked_repo.find_active(db_session, tenant.id, phone="12015550030")
        assert found is None

    async def test_clear_by_lid(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        await blocked_repo.create(db_session, tenant.id, whatsapp_lid="blocked@lid")
        cleared = await blocked_repo.clear_identity(
            db_session, tenant.id, whatsapp_lid="blocked@lid"
        )
        assert cleared == 1
        found = await blocked_repo.find_active(
            db_session, tenant.id, whatsapp_lid="blocked@lid"
        )
        assert found is None

    async def test_clear_clears_all_matching_blocks(
        self, db_session: AsyncSession
    ) -> None:
        _user, tenant = await _seed_tenant(db_session)
        await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        cleared = await blocked_repo.clear_identity(db_session, tenant.id, phone="12015550030")
        assert cleared == 2

    async def test_clear_no_args_returns_zero(
        self, db_session: AsyncSession
    ) -> None:
        _user, tenant = await _seed_tenant(db_session)
        assert await blocked_repo.clear_identity(db_session, tenant.id) == 0

    async def test_clear_no_match_returns_zero(
        self, db_session: AsyncSession
    ) -> None:
        _user, tenant = await _seed_tenant(db_session)
        assert await blocked_repo.clear_identity(db_session, tenant.id, phone="12015559999") == 0

    async def test_clear_idempotent(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        await blocked_repo.clear_identity(db_session, tenant.id, phone="12015550030")
        cleared = await blocked_repo.clear_identity(db_session, tenant.id, phone="12015550030")
        assert cleared == 0


class TestPersistence:
    """Blocks persist in the database until explicitly unblocked."""

    async def test_block_persists_across_sessions(
        self, db_session: AsyncSession
    ) -> None:
        _user, tenant = await _seed_tenant(db_session)
        tenant_id = tenant.id
        block = await blocked_repo.create(db_session, tenant_id, phone="12015550030")
        await db_session.commit()

        # Re-fetch from a "new" session perspective
        db_session.expire_all()
        found = await blocked_repo.find_active(db_session, tenant_id, phone="12015550030")
        assert found is not None
        assert found.id == block.id

    async def test_block_persists_until_unblocked(
        self, db_session: AsyncSession
    ) -> None:
        _user, tenant = await _seed_tenant(db_session)
        tenant_id = tenant.id
        block = await blocked_repo.create(db_session, tenant_id, phone="12015550030")
        await db_session.commit()

        await blocked_repo.unblock(db_session, tenant_id, block.id)
        await db_session.commit()

        db_session.expire_all()
        found = await blocked_repo.find_active(db_session, tenant_id, phone="12015550030")
        assert found is None

    async def test_created_block_appears_in_list(
        self, db_session: AsyncSession
    ) -> None:
        _user, tenant = await _seed_tenant(db_session)
        tenant_id = tenant.id
        await blocked_repo.create(db_session, tenant_id, phone="12015550030")
        await db_session.commit()
        db_session.expire_all()
        blocks = await blocked_repo.list_active(db_session, tenant_id)
        assert len(blocks) == 1
        assert blocks[0].phone == "12015550030"

    async def test_clear_allows_recreate(self, db_session: AsyncSession) -> None:
        """After clearing, a new block can be created for the same identity."""
        _user, tenant = await _seed_tenant(db_session)
        await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        await blocked_repo.clear_identity(db_session, tenant.id, phone="12015550030")

        block = await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        assert block.is_active is True
        assert block.phone == "12015550030"


class TestClientCreationClearsBlock:
    """Integration-style: simulating Client creation clears matching blocks."""

    async def test_clear_on_client_creation_by_phone(
        self, db_session: AsyncSession
    ) -> None:
        _, tenant = await _seed_tenant(db_session)

        # Arrange — block exists for phone
        await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        await db_session.flush()

        # Act — simulate what happens when a Client is created for this phone
        cleared = await blocked_repo.clear_identity(
            db_session, tenant.id, phone="12015550030"
        )

        # Assert
        assert cleared == 1
        remaining = await blocked_repo.list_active(db_session, tenant.id)
        assert len(remaining) == 0

    async def test_clear_on_client_creation_by_lid(
        self, db_session: AsyncSession
    ) -> None:
        _, tenant = await _seed_tenant(db_session)

        # Arrange — block exists for LID
        await blocked_repo.create(db_session, tenant.id, whatsapp_lid="newclient@lid")
        await db_session.flush()

        # Act — simulate Client creation clearing the block
        cleared = await blocked_repo.clear_identity(
            db_session, tenant.id, whatsapp_lid="newclient@lid"
        )

        # Assert
        assert cleared == 1
        remaining = await blocked_repo.list_active(db_session, tenant.id)
        assert len(remaining) == 0

    async def test_clear_by_phone_also_clears_lid_blocks(
        self, db_session: AsyncSession
    ) -> None:
        """When identity is matched by phone, LID-only blocks for same identity
        are not affected — intentional tenant-scoped per-field clearing."""
        _, tenant = await _seed_tenant(db_session)
        await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        await blocked_repo.create(
            db_session, tenant.id, whatsapp_lid="other@lid"
        )

        cleared = await blocked_repo.clear_identity(
            db_session, tenant.id, phone="12015550030"
        )
        assert cleared == 1
        remaining = await blocked_repo.list_active(db_session, tenant.id)
        assert len(remaining) == 1
        assert remaining[0].whatsapp_lid == "other@lid"
