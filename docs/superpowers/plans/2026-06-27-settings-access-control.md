# Settings and Access Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign tenant Configuración into category navigation with one active panel, add client-side pagination to Control de acceso, and change BlockedClient unblock semantics from soft-delete to row deletion everywhere.

**Architecture:** Keep the existing API contract shape except for removing `is_active`; row existence in `blocked_clients` is now the only active-block signal. On the frontend, keep settings state local to the active section and rely on unmount-on-cancel to discard unsaved edits. Use existing shadcn/ui primitives (`Card`, `Button`, `Sheet`, `Skeleton`, `Badge`) and no new dependencies.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy async, Alembic, pytest/pytest-asyncio, React 19, TypeScript strict, Zustand, Vitest, Testing Library, Tailwind CSS v4, shadcn/ui.

## Global Constraints

- Work in Spanish-visible UI through backend i18n catalogs; do not hardcode translated frontend strings.
- No new dependencies.
- Keep Control de acceso pagination frontend-only: load all current blocks and render 10 rows per page.
- BlockedClient semantics: create block = insert row; unblock = delete row; blocked = matching row exists.
- Remove `is_active` from the BlockedClient model, response schema, frontend type, repository filters, and database schema.
- Existing inactive block rows must be deleted by migration before dropping `blocked_clients.is_active`.
- Preserve current flat settings category order.
- No settings category opens by default.
- Cancelar in the active settings panel closes the section and discards unsaved local edits by unmounting the section.
- Do not touch unrelated dirty files. Current working tree already has `frontend/CONTEXT.md` modified before this plan.

---

## File Structure

- `backend/app/models/blocked_client.py` — remove the `is_active` column from the ORM model.
- `backend/app/repositories/blocked_clients_repository.py` — make list/find query by row existence and make `unblock`/`clear_identity` delete rows.
- `backend/app/schemas/access_control.py` — remove `is_active` from the private access-control response schema.
- `backend/app/services/dashboard_service/__init__.py` — count all `BlockedClient` rows for the tenant.
- `backend/alembic/versions/e013fe74cab3_remove_blocked_clients_is_active.py` — delete inactive rows, drop `is_active`, and restore it on downgrade.
- `backend/tests/test_blocked_clients_repository.py` — update repository behavior tests from soft-delete to hard-delete.
- `backend/tests/test_access_control_api.py` — assert DELETE removes the row and the response no longer exposes `is_active`.
- `backend/tests/test_blocked_clients_migration.py` — static Alembic migration coverage for delete-before-drop order and downgrade.
- `backend/tests/test_whatsapp_endpoint.py`, `backend/tests/test_tenant_plan.py`, `backend/tests/test_whatsapp_client_context_shortcut.py` — remove BlockedClient `is_active` constructor usage and assert unblock paths delete rows.
- `frontend/src/features/admin/services/access-control-api.ts` — remove `is_active` from `AccessControlBlock`.
- `frontend/src/features/admin/components/access-control-section.tsx` — paginate loaded blocks client-side in pages of 10.
- `frontend/src/features/admin/components/__tests__/access-control-section.spec.tsx` — verify page size, numbered navigation, previous/next, and refresh after unblock.
- `frontend/src/features/admin/components/reminder-settings-section.tsx` — inline reminder settings panel extracted from the existing modal behavior.
- `frontend/src/features/admin/components/settings-page.tsx` — category navigation, neutral guide state, desktop side nav, mobile Sheet, active panel scroll, common Cancelar.
- `frontend/src/features/admin/components/__tests__/settings-page.spec.tsx` — verify neutral state, category selection, Cancelar, and mobile category Sheet trigger.
- `backend/app/core/i18n/catalogs_en_frontend.py` and `backend/app/core/i18n/catalogs_es_frontend.py` — add frontend keys for guide, mobile selection, cancel, and pagination.
- `docs/architecture/database-schema.md`, `docs/architecture/whatsapp-console-flow.md`, `docs/architecture/frontend-architecture.md`, `docs/codebase/frontend-components.md`, `frontend/CONTEXT.md`, `backend/CONTEXT.md` — sync docs with row-existence blocking and new settings layout.

---

### Task 1: BlockedClient hard-delete storage and REST contract

**Files:**
- Create: `backend/alembic/versions/e013fe74cab3_remove_blocked_clients_is_active.py`
- Create: `backend/tests/test_blocked_clients_migration.py`
- Modify: `backend/app/models/blocked_client.py`
- Modify: `backend/app/repositories/blocked_clients_repository.py`
- Modify: `backend/app/schemas/access_control.py`
- Modify: `backend/app/services/dashboard_service/__init__.py`
- Modify: `backend/tests/test_blocked_clients_repository.py`
- Modify: `backend/tests/test_access_control_api.py`

**Interfaces:**
- Consumes: existing `BlockedClient(id, tenant_id, phone, whatsapp_lid, created_at, updated_at)` table/model fields.
- Produces: `blocked_clients_repository.unblock(db, tenant_id, block_id) -> BlockedClient | None` deletes the matching row and returns the deleted ORM object for caller status checks; `blocked_clients_repository.clear_identity(...) -> int` deletes matching rows; `AccessControlBlockResponse` no longer contains `is_active`.

- [ ] **Step 1: Update repository tests to describe row-existence semantics**

Replace these test bodies in `backend/tests/test_blocked_clients_repository.py`:

```python
class TestUnblock:
    async def test_unblock_active_block(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        block = await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        block_id = block.id

        result = await blocked_repo.unblock(db_session, tenant.id, block_id)

        assert result is not None
        assert result.id == block_id
        found = await blocked_repo.find_active(
            db_session, tenant.id, phone="12015550030"
        )
        assert found is None
        assert await db_session.get(type(block), block_id) is None

    async def test_unblock_already_unblocked_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        _user, tenant = await _seed_tenant(db_session)
        block = await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        block_id = block.id
        await blocked_repo.unblock(db_session, tenant.id, block_id)

        result = await blocked_repo.unblock(db_session, tenant.id, block_id)

        assert result is None

    async def test_unblock_nonexistent_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        _user, tenant = await _seed_tenant(db_session)
        import uuid

        result = await blocked_repo.unblock(db_session, tenant.id, uuid.uuid4())
        assert result is None
```

Replace `TestListActive.test_list_returns_only_active` with:

```python
    async def test_list_returns_existing_rows(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        block_a = await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        await blocked_repo.create(db_session, tenant.id, phone="12015550031")
        await blocked_repo.unblock(db_session, tenant.id, block_a.id)

        blocks = await blocked_repo.list_active(db_session, tenant.id)

        assert len(blocks) == 1
        assert blocks[0].phone == "12015550031"
```

Replace `TestPersistence.test_block_persists_until_unblocked` with:

```python
    async def test_block_row_is_deleted_when_unblocked(
        self, db_session: AsyncSession
    ) -> None:
        _user, tenant = await _seed_tenant(db_session)
        tenant_id = tenant.id
        block = await blocked_repo.create(db_session, tenant_id, phone="12015550030")
        block_id = block.id
        await db_session.commit()

        await blocked_repo.unblock(db_session, tenant_id, block_id)
        await db_session.commit()

        db_session.expire_all()
        found = await blocked_repo.find_active(
            db_session, tenant_id, phone="12015550030"
        )
        assert found is None
        assert await db_session.get(type(block), block_id) is None
```

Replace `TestPersistence.test_clear_allows_recreate` with:

```python
    async def test_clear_deletes_then_allows_recreate(self, db_session: AsyncSession) -> None:
        _user, tenant = await _seed_tenant(db_session)
        first = await blocked_repo.create(db_session, tenant.id, phone="12015550030")
        first_id = first.id

        cleared = await blocked_repo.clear_identity(db_session, tenant.id, phone="12015550030")
        second = await blocked_repo.create(db_session, tenant.id, phone="12015550030")

        assert cleared == 1
        assert await db_session.get(type(first), first_id) is None
        assert second.id != first_id
        assert second.phone == "12015550030"
```

In every repository test that currently asserts `block.is_active is True`, remove that assertion. Do not replace it with another flag assertion.

- [ ] **Step 2: Run repository tests and verify they fail for the expected reason**

Run:

```bash
cd backend && uv run pytest tests/test_blocked_clients_repository.py -q
```

Expected: FAIL with errors referencing `BlockedClient.is_active` or assertions expecting deleted rows while current code soft-deletes.

- [ ] **Step 3: Update REST API contract test**

Replace `test_access_control_list_block_duplicate_and_unblock` in `backend/tests/test_access_control_api.py` with:

```python
async def test_access_control_list_block_duplicate_and_unblock(client, db_session, active_tenant_user):
    headers = await _tenant_headers(client)

    created = await client.post("/api/v1/access-control/blocks", json={"phone": "+12015550222"}, headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["phone"] == "12015550222"
    assert "is_active" not in body

    tenant = await _tenant(db_session, active_tenant_user)
    row = await db_session.get(BlockedClient, body["id"])
    assert row is not None
    assert row.tenant_id == tenant.id

    duplicate = await client.post("/api/v1/access-control/blocks", json={"phone": "+12015550222"}, headers=headers)
    assert duplicate.status_code == 409

    listed = await client.get("/api/v1/access-control/blocks", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [row["phone"] for row in listed.json()] == ["12015550222"]
    assert "is_active" not in listed.json()[0]

    deleted = await client.delete(f"/api/v1/access-control/blocks/{body['id']}", headers=headers)
    assert deleted.status_code == 204

    listed_again = await client.get("/api/v1/access-control/blocks", headers=headers)
    assert listed_again.status_code == 200
    assert listed_again.json() == []
    assert await db_session.get(BlockedClient, body["id"]) is None
```

- [ ] **Step 4: Add migration coverage test**

Create `backend/tests/test_blocked_clients_migration.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_migration_module():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "e013fe74cab3_remove_blocked_clients_is_active.py"
    spec = importlib.util.spec_from_file_location("remove_blocked_clients_is_active", path)
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
```

- [ ] **Step 5: Run API and migration tests and verify they fail for expected reasons**

Run:

```bash
cd backend && uv run pytest tests/test_access_control_api.py tests/test_blocked_clients_migration.py -q
```

Expected: FAIL because the migration file does not exist yet and API responses still include `is_active`.

- [ ] **Step 6: Create the Alembic migration**

Create `backend/alembic/versions/e013fe74cab3_remove_blocked_clients_is_active.py`:

```python
"""Remove is_active from blocked_clients.

Revision ID: e013fe74cab3
Revises: e012fe74cab2
Create Date: 2026-06-27 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "e013fe74cab3"
down_revision: str | None = "e012fe74cab2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM blocked_clients WHERE is_active IS FALSE")
    op.drop_column("blocked_clients", "is_active")


def downgrade() -> None:
    op.add_column(
        "blocked_clients",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
```

- [ ] **Step 7: Update `BlockedClient` model**

Replace `backend/app/models/blocked_client.py` with:

```python
import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BlockedClient(Base, TimestampMixin):
    """Tenant-scoped block for unregistered WhatsApp identities.

    At least one identity field (phone or whatsapp_lid) must be
    provided at creation — enforced by the repository layer.
    A row represents an active block; unblocking deletes the row.
    """

    __tablename__ = "blocked_clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    whatsapp_lid: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_blocked_clients_tenant_phone", "tenant_id", "phone"),
        Index("ix_blocked_clients_tenant_lid", "tenant_id", "whatsapp_lid"),
    )
```

- [ ] **Step 8: Update the repository implementation**

Replace `backend/app/repositories/blocked_clients_repository.py` with:

```python
"""Blocked Client repository — blocked_clients table queries."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blocked_client import BlockedClient


async def create(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    phone: str | None = None,
    whatsapp_lid: str | None = None,
) -> BlockedClient:
    """Create a block for a tenant-scoped identity.

    At least one of *phone* or *whatsapp_lid* must be provided.
    """
    if not phone and not whatsapp_lid:
        raise ValueError(
            "At least one identity field (phone or whatsapp_lid) is required"
        )

    block = BlockedClient(
        tenant_id=tenant_id,
        phone=phone,
        whatsapp_lid=whatsapp_lid,
    )
    db.add(block)
    await db.flush()
    return block


async def list_active(db: AsyncSession, tenant_id: UUID) -> list[BlockedClient]:
    """List all existing blocks for a tenant, newest first."""
    result = await db.execute(
        select(BlockedClient)
        .where(BlockedClient.tenant_id == tenant_id)
        .order_by(BlockedClient.created_at.desc())
    )
    return list(result.scalars().all())


async def find_active(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    phone: str | None = None,
    whatsapp_lid: str | None = None,
) -> BlockedClient | None:
    """Find a block by phone or LID within a tenant."""
    if not phone and not whatsapp_lid:
        return None
    stmt = select(BlockedClient).where(BlockedClient.tenant_id == tenant_id)
    if phone and whatsapp_lid:
        stmt = stmt.where(
            or_(
                BlockedClient.phone == phone,
                BlockedClient.whatsapp_lid == whatsapp_lid,
            )
        )
    elif phone:
        stmt = stmt.where(BlockedClient.phone == phone)
    else:
        stmt = stmt.where(BlockedClient.whatsapp_lid == whatsapp_lid)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def unblock(
    db: AsyncSession,
    tenant_id: UUID,
    block_id: UUID,
) -> BlockedClient | None:
    """Delete a specific block. Returns the deleted row or None."""
    result = await db.execute(
        select(BlockedClient).where(
            BlockedClient.id == block_id,
            BlockedClient.tenant_id == tenant_id,
        )
    )
    block = result.scalar_one_or_none()
    if block is not None:
        await db.delete(block)
        await db.flush()
    return block


async def clear_identity(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    phone: str | None = None,
    whatsapp_lid: str | None = None,
) -> int:
    """Delete all blocks for an identity when a Client is created.

    Returns the number of blocks deleted.
    """
    if not phone and not whatsapp_lid:
        return 0
    stmt = select(BlockedClient).where(BlockedClient.tenant_id == tenant_id)
    if phone and whatsapp_lid:
        stmt = stmt.where(
            or_(
                BlockedClient.phone == phone,
                BlockedClient.whatsapp_lid == whatsapp_lid,
            )
        )
    elif phone:
        stmt = stmt.where(BlockedClient.phone == phone)
    else:
        stmt = stmt.where(BlockedClient.whatsapp_lid == whatsapp_lid)
    result = await db.execute(stmt)
    blocks = list(result.scalars().all())
    for block in blocks:
        await db.delete(block)
    await db.flush()
    return len(blocks)


__all__ = [
    "create",
    "list_active",
    "find_active",
    "unblock",
    "clear_identity",
]
```

- [ ] **Step 9: Update schema and dashboard count**

In `backend/app/schemas/access_control.py`, remove the `is_active: bool` line from `AccessControlBlockResponse` so the response is:

```python
class AccessControlBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    phone: str | None
    whatsapp_lid: str | None
    created_at: datetime
    updated_at: datetime
```

In `backend/app/services/dashboard_service/__init__.py`, replace the blocked count query with:

```python
row = await db.execute(
    select(func.count()).select_from(BlockedClient).where(BlockedClient.tenant_id == tenant_id)
)
```

- [ ] **Step 10: Run focused backend tests**

Run:

```bash
cd backend && uv run pytest tests/test_blocked_clients_repository.py tests/test_access_control_api.py tests/test_blocked_clients_migration.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit Task 1**

```bash
git add backend/app/models/blocked_client.py backend/app/repositories/blocked_clients_repository.py backend/app/schemas/access_control.py backend/app/services/dashboard_service/__init__.py backend/alembic/versions/e013fe74cab3_remove_blocked_clients_is_active.py backend/tests/test_blocked_clients_repository.py backend/tests/test_access_control_api.py backend/tests/test_blocked_clients_migration.py
git commit -m "feat(access-control): hard-delete blocked clients"
```

---

### Task 2: WhatsApp unblock path consistency

**Files:**
- Modify: `backend/tests/test_whatsapp_endpoint.py`
- Modify: `backend/tests/test_tenant_plan.py`
- Modify: `backend/tests/test_whatsapp_client_context_shortcut.py` if `rg "BlockedClient\(" backend/tests/test_whatsapp_client_context_shortcut.py` finds constructors after Task 1
- No production code expected unless tests reveal a direct `BlockedClient.is_active` reference missed by Task 1.

**Interfaces:**
- Consumes: `blocked_clients_repository.find_active`, `unblock`, and `clear_identity` from Task 1.
- Produces: all WhatsApp unblock surfaces delete `blocked_clients` rows through the repository: web API, tenant WhatsApp console, Client Context Shortcut, and automatic clearing when a Client is created.

- [ ] **Step 1: Remove BlockedClient constructor flags from tests**

Run:

```bash
rg "BlockedClient\(" backend/tests
```

For every `BlockedClient(...)` constructor, remove `is_active=True` and do not add a replacement field. For example, in `backend/tests/test_tenant_plan.py` replace:

```python
db_session.add(BlockedClient(tenant_id=tenant.id, phone="12015550999", is_active=True))
```

with:

```python
db_session.add(BlockedClient(tenant_id=tenant.id, phone="12015550999"))
```

In `backend/tests/test_whatsapp_endpoint.py`, replace every block creation shaped like:

```python
block = BlockedClient(
    tenant_id=tenant.id,
    phone="12015559999",
    is_active=True,
)
```

with:

```python
block = BlockedClient(
    tenant_id=tenant.id,
    phone="12015559999",
)
```

- [ ] **Step 2: Update context shortcut unblock assertion**

In `backend/tests/test_whatsapp_endpoint.py`, replace the soft-delete assertion near the context shortcut unblock test with:

```python
    result = await db_session.execute(
        select(BlockedClient).where(BlockedClient.id == block_id)
    )
    db_block = result.scalar_one_or_none()
    assert db_block is None
```

Do not call `db_session.expire(block)` before this query; the row should no longer exist.

- [ ] **Step 3: Update any active-block query predicates in tests**

In `backend/tests/test_whatsapp_endpoint.py`, replace this query predicate:

```python
select(BlockedClient).where(
    BlockedClient.tenant_id == tenant.id,
    BlockedClient.phone == "12015559999",
    BlockedClient.is_active,
)
```

with:

```python
select(BlockedClient).where(
    BlockedClient.tenant_id == tenant.id,
    BlockedClient.phone == "12015559999",
)
```

- [ ] **Step 4: Add an explicit Client Context Shortcut deletion regression if missing**

If `backend/tests/test_whatsapp_endpoint.py` does not already have a `test_context_shortcut_desbloquear_unblocks` after edits, add this test next to the other context shortcut block tests:

```python
async def test_context_shortcut_desbloquear_deletes_block_row(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"
    block = BlockedClient(tenant_id=tenant.id, phone="12015559999")
    db_session.add(block)
    await db_session.commit()
    block_id = block.id

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "1",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert "Acceso desbloqueado" in body["reply"]
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"
    assert await db_session.get(BlockedClient, block_id) is None
```

- [ ] **Step 5: Run WhatsApp and tenant-plan regression tests**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_endpoint.py tests/test_whatsapp_client_context_shortcut.py tests/test_tenant_plan.py -q
```

Expected: PASS. If any failure references `BlockedClient.is_active`, remove that direct field reference and assert row existence/deletion instead.

- [ ] **Step 6: Run all backend tests**

Run:

```bash
cd backend && uv run pytest
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add backend/tests/test_whatsapp_endpoint.py backend/tests/test_tenant_plan.py backend/tests/test_whatsapp_client_context_shortcut.py
git commit -m "test(access-control): verify whatsapp unblocks delete rows"
```

---

### Task 3: Inline reminders section and Settings category panel

**Files:**
- Create: `frontend/src/features/admin/components/reminder-settings-section.tsx`
- Create: `frontend/src/features/admin/components/__tests__/settings-page.spec.tsx`
- Modify: `frontend/src/features/admin/components/settings-page.tsx`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py`

**Interfaces:**
- Consumes: existing setting section components and `getProfile(): Promise<Profile>`.
- Produces: `SettingsPage` starts with `activeSection === null`, renders a guide message, uses a desktop category nav, opens mobile category selection in `Sheet`, renders one active panel at a time, and provides a common Cancelar button that sets `activeSection` back to `null`.

- [ ] **Step 1: Add settings layout i18n keys**

In `backend/app/core/i18n/catalogs_en_frontend.py`, add these entries next to the existing `frontend.settings.*` keys:

```python
    "frontend.settings.guide_title": "Choose a settings category",
    "frontend.settings.guide_description": "Select a category to edit its settings. No changes are made until you save inside a section.",
    "frontend.settings.select_category": "Select category",
    "frontend.settings.active_panel": "Active settings panel",
    "frontend.settings.cancel": "Cancel",
```

In `backend/app/core/i18n/catalogs_es_frontend.py`, add:

```python
    "frontend.settings.guide_title": "Elige una categoría de configuración",
    "frontend.settings.guide_description": "Selecciona una categoría para editarla. No se aplican cambios hasta que guardes dentro de una sección.",
    "frontend.settings.select_category": "Seleccionar categoría",
    "frontend.settings.active_panel": "Panel de configuración activo",
    "frontend.settings.cancel": "Cancelar",
```

- [ ] **Step 2: Create inline reminder section by reusing the modal logic**

Create `frontend/src/features/admin/components/reminder-settings-section.tsx` by copying the state, loading, validation, and save logic from `reminder-settings-modal.tsx`, then changing only the outer wrapper:

```tsx
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertCircle, Plus, X } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { getLocale, t } from "@/i18n";
import { useSettingsStore } from "@/store/settings";

const PREVIEW_PLACEHOLDERS = {
  client_name: "María Pérez",
  service_name: "Netflix",
  days: "3",
  streaming_email: "cliente@example.com",
  expires_at: "2026-07-01",
};

const DEFAULT_MESSAGES = {
  en: {
    tenant: "Reminder: {{client_name}}'s {{service_name}} subscription expires in {{days}} days.",
    client: "Your {{service_name}} subscription expires in {{days}} days.",
  },
  es: {
    tenant: "Recordatorio: la suscripción de {{client_name}} a {{service_name}} vence en {{days}} días.",
    client: "Tu suscripción de {{service_name}} vence en {{days}} días.",
  },
};

function getDefaultMessages(locale: string) {
  return DEFAULT_MESSAGES[locale as "en" | "es"] || DEFAULT_MESSAGES.en;
}

function renderPreview(template: string): string {
  let result = template;
  for (const [key, value] of Object.entries(PREVIEW_PLACEHOLDERS)) {
    result = result.replace(new RegExp(`\\{\\{${key}\\}\\}`, "g"), value);
  }
  return result;
}

export function ReminderSettingsSection() {
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [locale, setLocale] = useState(getLocale());
  const defaults = getDefaultMessages(locale);
  const {
    reminderSettings,
    tenantSettings,
    reminderSettingsLoaded,
    loadReminderSettings,
    loadTenantSettings,
    updateReminderSettings,
  } = useSettingsStore();
  const [settings, setSettings] = useState({
    reminders_enabled: false,
    warning_days: [7, 3, 1] as number[],
    reminder_time: "09:00",
    recipient_mode: "tenant_only" as "tenant_only" | "client_only" | "both",
    custom_message_tenant: null as string | null,
    custom_message_client: null as string | null,
  });
  const [customDay, setCustomDay] = useState("");
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  const loadData = useCallback(async () => {
    setError("");
    setIsLoading(true);
    setLocale(getLocale());
    try {
      await Promise.all([loadReminderSettings(), loadTenantSettings()]);
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string | Array<{ msg?: string }> } } };
      const detail = apiErr.response?.data?.detail;
      let msg = t("frontend.subscriptions.error_reminder_settings");
      if (typeof detail === "string") msg = detail;
      else if (Array.isArray(detail) && detail.length > 0) msg = detail.map((d) => d.msg || "Unknown error").join("; ");
      else if (err instanceof Error) msg = err.message;
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [loadReminderSettings, loadTenantSettings]);

  useEffect(() => {
    if (reminderSettingsLoaded && reminderSettings) {
      setSettings({
        reminders_enabled: reminderSettings.reminders_enabled,
        warning_days: reminderSettings.warning_days || [7, 3, 1],
        reminder_time: reminderSettings.reminder_time || "09:00",
        recipient_mode: reminderSettings.recipient_mode || "tenant_only",
        custom_message_tenant: reminderSettings.custom_message_tenant,
        custom_message_client: reminderSettings.custom_message_client,
      });
    }
  }, [reminderSettingsLoaded, reminderSettings]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const validate = useCallback(() => {
    const errors: Record<string, string> = {};
    if (settings.reminders_enabled) {
      if (settings.warning_days.length === 0) errors.warning_days = t("frontend.subscriptions.error_warning_days_required");
      if (!/^\\d{2}:\\d{2}$/.test(settings.reminder_time) || !/^([01]\\d|2[0-3]):[0-5]\\d$/.test(settings.reminder_time)) {
        errors.reminder_time = t("frontend.subscriptions.error_invalid_time");
      }
    }
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  }, [settings]);

  useEffect(() => {
    validate();
  }, [settings, validate]);

  function toggleWarningDay(day: number) {
    setSettings((prev) => {
      const days = prev.warning_days.includes(day)
        ? prev.warning_days.filter((d) => d !== day)
        : [...prev.warning_days, day].sort((a, b) => a - b);
      return { ...prev, warning_days: days };
    });
  }

  function addCustomDay() {
    const day = parseInt(customDay, 10);
    if (!Number.isNaN(day) && day > 0 && !settings.warning_days.includes(day)) {
      setSettings((prev) => ({ ...prev, warning_days: [...prev.warning_days, day].sort((a, b) => a - b) }));
      setCustomDay("");
    }
  }

  function removeWarningDay(day: number) {
    setSettings((prev) => ({ ...prev, warning_days: prev.warning_days.filter((d) => d !== day) }));
  }

  async function handleSave() {
    if (!validate()) return;
    setIsSaving(true);
    setError("");
    try {
      await updateReminderSettings(settings);
      toast.success(t("frontend.subscriptions.reminder_saved"));
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string | Array<{ msg?: string }> } } };
      const detail = apiErr.response?.data?.detail;
      let msg = t("frontend.subscriptions.error_reminder_settings");
      if (typeof detail === "string") msg = detail;
      else if (Array.isArray(detail) && detail.length > 0) msg = detail.map((d) => d.msg || "Unknown error").join("; ");
      else if (err instanceof Error) msg = err.message;
      setError(msg);
    } finally {
      setIsSaving(false);
    }
  }

  const hasWarningDaysError = !!(validationErrors.warning_days && settings.reminders_enabled);
  const hasTimeError = !!(validationErrors.reminder_time && settings.reminders_enabled);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-5">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-7">
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </Alert>
      )}

      <div className="flex items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <Label className="text-base font-medium">{t("frontend.subscriptions.reminders_enabled")}</Label>
          <p className="text-sm text-muted-foreground">{t("frontend.subscriptions.reminders_desc")}</p>
        </div>
        <Switch checked={settings.reminders_enabled} onCheckedChange={(checked) => setSettings((prev) => ({ ...prev, reminders_enabled: checked }))} />
      </div>

      {settings.reminders_enabled && (
        <>
          <Separator />
          <div className="flex flex-col gap-2.5">
            <Label className="text-sm font-medium">{t("frontend.subscriptions.timezone")}</Label>
            <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
              {t("frontend.subscriptions.reminder_time_help")} {tenantSettings?.timezone || "UTC"}
            </div>
          </div>

          <div className="flex flex-col gap-2.5">
            <Label className={hasWarningDaysError ? "text-sm font-medium text-destructive" : "text-sm font-medium"}>
              {t("frontend.subscriptions.warning_days")}
            </Label>
            <div className="flex flex-wrap items-center gap-2">
              {[7, 3, 1].map((day) => (
                <label key={day} className="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 transition-colors hover:bg-accent">
                  <input type="checkbox" checked={settings.warning_days.includes(day)} onChange={() => toggleWarningDay(day)} className="rounded" />
                  <span className="text-sm">{day} {day === 1 ? "day" : "days"}</span>
                </label>
              ))}
              <div className="flex items-center gap-1.5">
                <Input type="number" min={1} value={customDay} onChange={(e) => setCustomDay(e.target.value)} placeholder="Custom" className="h-9 w-20 text-sm" onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCustomDay(); } }} />
                <Button type="button" variant="outline" size="icon" className="h-9 w-9 shrink-0" onClick={addCustomDay} disabled={!customDay}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>
            {settings.warning_days.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {settings.warning_days.map((day) => (
                  <span key={day} className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary">
                    {day} {day === 1 ? "day" : "days"}
                    <button type="button" onClick={() => removeWarningDay(day)} className="transition-colors hover:text-destructive">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            {hasWarningDaysError && <p className="text-xs text-destructive">{validationErrors.warning_days}</p>}
          </div>

          <div className="flex flex-col gap-2.5">
            <Label className={hasTimeError ? "text-sm font-medium text-destructive" : "text-sm font-medium"}>{t("frontend.subscriptions.reminder_time")}</Label>
            <p className="text-sm text-muted-foreground">{t("frontend.subscriptions.reminder_time_help")}</p>
            <Input type="time" value={settings.reminder_time} onChange={(e) => setSettings((prev) => ({ ...prev, reminder_time: e.target.value }))} className={hasTimeError ? "w-40 border-destructive" : "w-40"} />
            {hasTimeError && <p className="text-xs text-destructive">{validationErrors.reminder_time}</p>}
          </div>

          <div className="flex flex-col gap-2.5">
            <Label className="text-sm font-medium">{t("frontend.subscriptions.recipients")}</Label>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {[
                { value: "tenant_only", label: t("frontend.subscriptions.recipient_mode_tenant_only"), desc: "Admin only" },
                { value: "client_only", label: t("frontend.subscriptions.recipient_mode_client_only"), desc: "Client only" },
                { value: "both", label: t("frontend.subscriptions.recipient_mode_both"), desc: "Both" },
              ].map((opt) => (
                <label key={opt.value} className={settings.recipient_mode === opt.value ? "flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border border-primary bg-primary/5 p-3 transition-colors" : "flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border border-border p-3 transition-colors hover:bg-accent"}>
                  <input type="radio" name="recipient_mode" value={opt.value} checked={settings.recipient_mode === opt.value} onChange={(e) => setSettings((prev) => ({ ...prev, recipient_mode: e.target.value as "tenant_only" | "client_only" | "both" }))} className="sr-only" />
                  <span className="text-sm font-medium">{opt.desc}</span>
                  <span className="text-center text-xs text-muted-foreground">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          <Separator />
          <div className="flex flex-col gap-4">
            <div>
              <Label className="text-sm font-medium">Custom messages</Label>
              <p className="mt-1 text-sm text-muted-foreground">
                Use <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{"{{placeholder}}"}</code> for dynamic values: client_name, service_name, days, streaming_email, expires_at
              </p>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label>{t("frontend.subscriptions.custom_message_tenant")}</Label>
                <textarea className="min-h-28 rounded-md border bg-background p-3 text-sm" value={settings.custom_message_tenant ?? defaults.tenant} onChange={(e) => setSettings((prev) => ({ ...prev, custom_message_tenant: e.target.value }))} />
                <p className="rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">{renderPreview(settings.custom_message_tenant ?? defaults.tenant)}</p>
              </div>
              <div className="flex flex-col gap-2">
                <Label>{t("frontend.subscriptions.custom_message_client")}</Label>
                <textarea className="min-h-28 rounded-md border bg-background p-3 text-sm" value={settings.custom_message_client ?? defaults.client} onChange={(e) => setSettings((prev) => ({ ...prev, custom_message_client: e.target.value }))} />
                <p className="rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">{renderPreview(settings.custom_message_client ?? defaults.client)}</p>
              </div>
            </div>
          </div>
        </>
      )}

      <Button type="button" className="self-start" onClick={() => void handleSave()} disabled={isSaving || Object.keys(validationErrors).length > 0}>
        {isSaving ? t("frontend.common.saving") : t("frontend.common.save")}
      </Button>
    </div>
  );
}
```

- [ ] **Step 3: Replace SettingsPage with category navigation**

Replace `frontend/src/features/admin/components/settings-page.tsx` with:

```tsx
import { useCallback, useEffect, useState } from "react";
import { Ban, Bell, Clock, Globe, KeyRound, Lock, Mail, Shield, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { t } from "@/i18n";
import { useAuthStore } from "@/store/auth";
import { AccessControlSection } from "../components/access-control-section";
import { CodeServicesSection } from "../components/code-services-section";
import { LocaleSection } from "../components/locale-section";
import { MailboxSection } from "../components/mailbox-section";
import { PasswordSection } from "../components/password-section";
import { ProfileSection } from "../components/profile-section";
import { PublicApiSection } from "../components/public-api-section";
import { ReminderSettingsSection } from "../components/reminder-settings-section";
import { TimezoneSection } from "../components/timezone-section";
import { getProfile, type Profile } from "../services/settings-api";

type SectionId = "reminders" | "locale" | "timezone" | "public-api" | "code-services" | "mailbox" | "access-control" | "profile" | "password";

type SettingsSection = {
  id: SectionId;
  title: string;
  description: string;
  icon: typeof Bell;
};

function buildSections(showProSettings: boolean): SettingsSection[] {
  return [
    ...(showProSettings ? [{ id: "reminders" as const, title: t("frontend.subscriptions.reminder_settings_title"), description: t("frontend.subscriptions.reminders_desc"), icon: Bell }] : []),
    { id: "locale", title: t("frontend.profile.language"), description: t("frontend.profile.language"), icon: Globe },
    ...(showProSettings ? [{ id: "timezone" as const, title: t("frontend.subscriptions.timezone"), description: t("frontend.subscriptions.timezone_description"), icon: Clock }] : []),
    ...(showProSettings ? [{ id: "public-api" as const, title: t("frontend.public_api.section_title"), description: t("frontend.public_api.description"), icon: KeyRound }] : []),
    { id: "code-services", title: t("frontend.code_services.tenant_section_title"), description: t("frontend.code_services.product_description"), icon: Shield },
    { id: "mailbox", title: t("frontend.mailbox.section_title"), description: t("frontend.mailbox.section_heading"), icon: Mail },
    { id: "access-control", title: t("frontend.access_control.section_title"), description: t("frontend.access_control.section_description"), icon: Ban },
    { id: "profile", title: t("frontend.profile.section_title"), description: t("frontend.profile.section_heading"), icon: User },
    { id: "password", title: t("frontend.dashboard.client.change_password"), description: t("frontend.dashboard.client.change_password"), icon: Lock },
  ];
}

function CategoryList({ sections, activeSection, onSelect }: { sections: SettingsSection[]; activeSection: SectionId | null; onSelect: (sectionId: SectionId) => void }) {
  return (
    <nav aria-label={t("frontend.settings.select_category")} className="flex flex-col gap-2">
      {sections.map((section) => {
        const Icon = section.icon;
        const active = activeSection === section.id;
        return (
          <button
            key={section.id}
            type="button"
            aria-current={active ? "page" : undefined}
            onClick={() => onSelect(section.id)}
            className={cn(
              "flex w-full items-start gap-3 rounded-lg border px-3 py-3 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active ? "border-primary bg-primary/5" : "border-transparent bg-background",
            )}
          >
            <Icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
            <span className="flex min-w-0 flex-col gap-1">
              <span className="text-sm font-medium leading-none">{section.title}</span>
              <span className="line-clamp-2 text-xs text-muted-foreground">{section.description}</span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}

export function SettingsPage() {
  const { role, tenantPlan, isMasterSupportContext } = useAuthStore();
  const isStarterTenantAdmin = role === "tenant" && tenantPlan === "starter";
  const showProSettings = !isStarterTenantAdmin || isMasterSupportContext;
  const sections = buildSections(showProSettings);
  const [activeSection, setActiveSection] = useState<SectionId | null>(null);
  const [categoryDrawerOpen, setCategoryDrawerOpen] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  const activeConfig = sections.find((section) => section.id === activeSection) ?? null;

  const loadProfile = useCallback(async () => {
    try {
      const data = await getProfile();
      setProfile(data);
    } catch {
      // Non-critical: profile section can render empty until retry via page reload.
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  function selectSection(sectionId: SectionId) {
    setActiveSection(sectionId);
    setCategoryDrawerOpen(false);
  }

  function renderSection(sectionId: SectionId) {
    switch (sectionId) {
      case "reminders":
        return <ReminderSettingsSection />;
      case "locale":
        return <LocaleSection />;
      case "timezone":
        return <TimezoneSection />;
      case "profile":
        return profile ? <ProfileSection profile={profile} onProfileUpdate={setProfile} /> : null;
      case "password":
        return <PasswordSection />;
      case "mailbox":
        return <MailboxSection />;
      case "access-control":
        return <AccessControlSection />;
      case "code-services":
        return <CodeServicesSection />;
      case "public-api":
        return <PublicApiSection />;
    }
  }

  return (
    <div className="flex-1 p-4 md:p-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{t("frontend.settings.title")}</h1>
            <p className="text-muted-foreground">{t("frontend.settings.description")}</p>
          </div>
          <Sheet open={categoryDrawerOpen} onOpenChange={setCategoryDrawerOpen}>
            <SheetTrigger
              render={
                <Button type="button" variant="outline" className="md:hidden">
                  {activeConfig?.title ?? t("frontend.settings.select_category")}
                </Button>
              }
            />
            <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto">
              <SheetHeader>
                <SheetTitle>{t("frontend.settings.select_category")}</SheetTitle>
              </SheetHeader>
              <div className="mt-4">
                <CategoryList sections={sections} activeSection={activeSection} onSelect={selectSection} />
              </div>
            </SheetContent>
          </Sheet>
        </div>

        <div className="grid gap-6 md:grid-cols-[18rem_minmax(0,1fr)]">
          <aside className="hidden md:block">
            <Card className="sticky top-6">
              <CardContent className="p-3">
                <CategoryList sections={sections} activeSection={activeSection} onSelect={selectSection} />
              </CardContent>
            </Card>
          </aside>

          <Card className="min-h-[32rem] overflow-hidden" aria-label={t("frontend.settings.active_panel")}>
            {activeConfig ? (
              <>
                <CardHeader className="border-b">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <CardTitle>{activeConfig.title}</CardTitle>
                      <CardDescription>{activeConfig.description}</CardDescription>
                    </div>
                    <Button type="button" variant="outline" onClick={() => setActiveSection(null)}>
                      {t("frontend.settings.cancel")}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="max-h-[calc(100dvh-16rem)] overflow-y-auto p-4 md:p-6">
                  {renderSection(activeConfig.id)}
                </CardContent>
              </>
            ) : (
              <CardContent className="flex min-h-[32rem] items-center justify-center p-6 text-center">
                <div className="mx-auto flex max-w-md flex-col gap-2">
                  <h2 className="text-lg font-semibold">{t("frontend.settings.guide_title")}</h2>
                  <p className="text-sm text-muted-foreground">{t("frontend.settings.guide_description")}</p>
                </div>
              </CardContent>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add SettingsPage component tests**

Create `frontend/src/features/admin/components/__tests__/settings-page.spec.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SettingsPage } from "../settings-page";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

vi.mock("@/store/auth", () => ({
  useAuthStore: () => ({
    role: "tenant",
    tenantPlan: "pro",
    isMasterSupportContext: false,
  }),
}));

vi.mock("../../services/settings-api", () => ({
  getProfile: vi.fn().mockResolvedValue({
    id: "tenant-1",
    full_name: "Demo Tenant",
    email: "demo@example.com",
    phone: "12015550000",
  }),
}));

vi.mock("../reminder-settings-section", () => ({ ReminderSettingsSection: () => <div>reminders section</div> }));
vi.mock("../locale-section", () => ({ LocaleSection: () => <div>locale section</div> }));
vi.mock("../timezone-section", () => ({ TimezoneSection: () => <div>timezone section</div> }));
vi.mock("../public-api-section", () => ({ PublicApiSection: () => <div>public api section</div> }));
vi.mock("../code-services-section", () => ({ CodeServicesSection: () => <div>code services section</div> }));
vi.mock("../mailbox-section", () => ({ MailboxSection: () => <div>mailbox section</div> }));
vi.mock("../access-control-section", () => ({ AccessControlSection: () => <div>access control section</div> }));
vi.mock("../profile-section", () => ({ ProfileSection: () => <div>profile section</div> }));
vi.mock("../password-section", () => ({ PasswordSection: () => <div>password section</div> }));

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts with no selected category and shows the guide message", async () => {
    render(<SettingsPage />);

    expect(screen.getByText("frontend.settings.guide_title")).toBeInTheDocument();
    expect(screen.getByText("frontend.settings.guide_description")).toBeInTheDocument();
    expect(screen.queryByText("access control section")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("frontend.settings.title")).toBeInTheDocument());
  });

  it("opens one category in the active panel and cancel closes it", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    await user.click(screen.getAllByText("frontend.access_control.section_title")[0]);
    expect(screen.getByText("access control section")).toBeInTheDocument();
    expect(screen.queryByText("frontend.settings.guide_title")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.settings.cancel" }));
    expect(screen.getByText("frontend.settings.guide_title")).toBeInTheDocument();
    expect(screen.queryByText("access control section")).not.toBeInTheDocument();
  });

  it("opens category selection from the mobile sheet trigger", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    await user.click(screen.getByRole("button", { name: "frontend.settings.select_category" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getAllByText("frontend.profile.language").length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 5: Run SettingsPage tests and fix only direct failures**

Run:

```bash
cd frontend && npm test -- src/features/admin/components/__tests__/settings-page.spec.tsx --run
```

Expected: PASS. If a mock path fails, adjust only the `vi.mock()` path to resolve the already-existing component file; do not change production imports for test convenience.

- [ ] **Step 6: Commit Task 3**

```bash
git add frontend/src/features/admin/components/settings-page.tsx frontend/src/features/admin/components/reminder-settings-section.tsx frontend/src/features/admin/components/__tests__/settings-page.spec.tsx backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py
git commit -m "feat(settings): add category panel layout"
```

---

### Task 4: Access Control client-side pagination

**Files:**
- Modify: `frontend/src/features/admin/services/access-control-api.ts`
- Modify: `frontend/src/features/admin/components/access-control-section.tsx`
- Create: `frontend/src/features/admin/components/__tests__/access-control-section.spec.tsx`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py`

**Interfaces:**
- Consumes: `listAccessBlocks(): Promise<AccessControlBlock[]>`, `createAccessBlock(phone)`, `deleteAccessBlock(id)`.
- Produces: `AccessControlSection` renders at most 10 blocks per page, numbered page controls, Anterior/Siguiente, clamps the page after list refresh, and removes `is_active` from TypeScript types.

- [ ] **Step 1: Add pagination i18n keys**

In `backend/app/core/i18n/catalogs_en_frontend.py`, add:

```python
    "frontend.access_control.pagination_summary": "Showing {from_item}-{to_item} of {total}",
    "frontend.access_control.pagination_previous": "Previous",
    "frontend.access_control.pagination_next": "Next",
    "frontend.access_control.pagination_page": "Page {page}",
```

In `backend/app/core/i18n/catalogs_es_frontend.py`, add:

```python
    "frontend.access_control.pagination_summary": "Mostrando {from_item}-{to_item} de {total}",
    "frontend.access_control.pagination_previous": "Anterior",
    "frontend.access_control.pagination_next": "Siguiente",
    "frontend.access_control.pagination_page": "Página {page}",
```

- [ ] **Step 2: Remove `is_active` from frontend type**

In `frontend/src/features/admin/services/access-control-api.ts`, replace `AccessControlBlock` with:

```ts
export interface AccessControlBlock {
  id: string;
  tenant_id: string;
  phone: string | null;
  whatsapp_lid: string | null;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 3: Add component tests for pagination and refresh**

Create `frontend/src/features/admin/components/__tests__/access-control-section.spec.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccessControlSection } from "../access-control-section";
import { createAccessBlock, deleteAccessBlock, listAccessBlocks } from "../../services/access-control-api";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, unknown>) => {
    if (!params) return key;
    return `${key} ${Object.values(params).join(" ")}`;
  },
}));

vi.mock("../../services/access-control-api", () => ({
  listAccessBlocks: vi.fn(),
  createAccessBlock: vi.fn(),
  deleteAccessBlock: vi.fn(),
}));

function block(id: number) {
  return {
    id: `block-${id}`,
    tenant_id: "tenant-1",
    phone: `12015550${String(id).padStart(3, "0")}`,
    whatsapp_lid: null,
    created_at: "2026-06-27T00:00:00Z",
    updated_at: "2026-06-27T00:00:00Z",
  };
}

describe("AccessControlSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders only 10 blocked identities on the first page", async () => {
    vi.mocked(listAccessBlocks).mockResolvedValue(Array.from({ length: 12 }, (_, index) => block(index + 1)));

    render(<AccessControlSection />);

    expect(await screen.findByText("12015550001")).toBeInTheDocument();
    expect(screen.getByText("12015550010")).toBeInTheDocument();
    expect(screen.queryByText("12015550011")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "frontend.access_control.pagination_page 2" })).toBeInTheDocument();
  });

  it("uses page numbers and previous-next controls", async () => {
    const user = userEvent.setup();
    vi.mocked(listAccessBlocks).mockResolvedValue(Array.from({ length: 12 }, (_, index) => block(index + 1)));

    render(<AccessControlSection />);

    await screen.findByText("12015550001");
    await user.click(screen.getByRole("button", { name: "frontend.access_control.pagination_next" }));
    expect(screen.queryByText("12015550001")).not.toBeInTheDocument();
    expect(screen.getByText("12015550011")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.access_control.pagination_previous" }));
    expect(screen.getByText("12015550001")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.access_control.pagination_page 2" }));
    expect(screen.getByText("12015550012")).toBeInTheDocument();
  });

  it("refreshes and removes an unblocked item from the visible list", async () => {
    const user = userEvent.setup();
    vi.mocked(listAccessBlocks)
      .mockResolvedValueOnce([block(1), block(2)])
      .mockResolvedValueOnce([block(2)]);
    vi.mocked(deleteAccessBlock).mockResolvedValue(undefined);

    render(<AccessControlSection />);

    expect(await screen.findByText("12015550001")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "frontend.access_control.unblock" })[0]);

    await waitFor(() => expect(deleteAccessBlock).toHaveBeenCalledWith("block-1"));
    await waitFor(() => expect(screen.queryByText("12015550001")).not.toBeInTheDocument());
    expect(screen.getByText("12015550002")).toBeInTheDocument();
  });

  it("refreshes after blocking without breaking pagination", async () => {
    const user = userEvent.setup();
    vi.mocked(listAccessBlocks)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([block(1)]);
    vi.mocked(createAccessBlock).mockResolvedValue(block(1));

    render(<AccessControlSection />);

    await screen.findByText("frontend.access_control.empty");
    await user.type(screen.getByPlaceholderText("frontend.access_control.phone_placeholder"), "+12015550001");
    await user.click(screen.getByRole("button", { name: "frontend.access_control.block" }));

    await waitFor(() => expect(createAccessBlock).toHaveBeenCalledWith("+12015550001"));
    expect(await screen.findByText("12015550001")).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Replace AccessControlSection implementation**

Replace `frontend/src/features/admin/components/access-control-section.tsx` with:

```tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Ban, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/i18n";
import { getApiError } from "@/lib/api-errors";
import { createAccessBlock, deleteAccessBlock, listAccessBlocks, type AccessControlBlock } from "../services/access-control-api";

const PAGE_SIZE = 10;

export function AccessControlSection() {
  const [blocks, setBlocks] = useState<AccessControlBlock[]>([]);
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [unblockingId, setUnblockingId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const trimmedPhone = phone.trim();
  const pageCount = Math.max(1, Math.ceil(blocks.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const visibleBlocks = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return blocks.slice(start, start + PAGE_SIZE);
  }, [blocks, safePage]);
  const fromItem = blocks.length === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const toItem = Math.min(blocks.length, safePage * PAGE_SIZE);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const nextBlocks = await listAccessBlocks();
      setBlocks(nextBlocks);
      setPage((current) => Math.min(current, Math.max(1, Math.ceil(nextBlocks.length / PAGE_SIZE))));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_load")));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleBlock(e: React.FormEvent) {
    e.preventDefault();
    if (!trimmedPhone) return;
    setSaving(true);
    try {
      await createAccessBlock(trimmedPhone);
      setPhone("");
      setPage(1);
      await load();
      toast.success(t("frontend.access_control.saved"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_save")));
    } finally {
      setSaving(false);
    }
  }

  async function handleUnblock(id: string) {
    setUnblockingId(id);
    try {
      await deleteAccessBlock(id);
      await load();
      toast.success(t("frontend.access_control.saved"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_save")));
    } finally {
      setUnblockingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleBlock} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex flex-1 flex-col gap-2">
          <Label htmlFor="access-control-phone">{t("frontend.access_control.block")}</Label>
          <Input id="access-control-phone" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder={t("frontend.access_control.phone_placeholder")} />
        </div>
        <Button type="submit" disabled={saving || !trimmedPhone}>
          <Ban data-icon="inline-start" />
          {t("frontend.access_control.block")}
        </Button>
      </form>

      {loading ? (
        <div className="h-16 rounded-lg bg-muted" />
      ) : blocks.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("frontend.access_control.empty")}</p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            {t("frontend.access_control.pagination_summary", { from_item: fromItem, to_item: toItem, total: blocks.length })}
          </p>
          <div className="flex flex-col gap-2">
            {visibleBlocks.map((block) => (
              <div key={block.id} className="flex items-center justify-between gap-3 rounded-lg border p-3">
                <Badge variant="secondary" className="min-w-0 truncate">
                  {block.phone || block.whatsapp_lid || "—"}
                </Badge>
                <Button variant="ghost" size="sm" disabled={unblockingId === block.id} onClick={() => void handleUnblock(block.id)}>
                  <Trash2 data-icon="inline-start" />
                  {t("frontend.access_control.unblock")}
                </Button>
              </div>
            ))}
          </div>

          {pageCount > 1 && (
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" size="sm" disabled={safePage === 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
                {t("frontend.access_control.pagination_previous")}
              </Button>
              {Array.from({ length: pageCount }, (_, index) => index + 1).map((pageNumber) => (
                <Button key={pageNumber} type="button" variant={safePage === pageNumber ? "default" : "outline"} size="sm" aria-current={safePage === pageNumber ? "page" : undefined} onClick={() => setPage(pageNumber)}>
                  {t("frontend.access_control.pagination_page", { page: pageNumber })}
                </Button>
              ))}
              <Button type="button" variant="outline" size="sm" disabled={safePage === pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}>
                {t("frontend.access_control.pagination_next")}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run AccessControlSection tests**

Run:

```bash
cd frontend && npm test -- src/features/admin/components/__tests__/access-control-section.spec.tsx --run
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add frontend/src/features/admin/services/access-control-api.ts frontend/src/features/admin/components/access-control-section.tsx frontend/src/features/admin/components/__tests__/access-control-section.spec.tsx backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py
git commit -m "feat(access-control): paginate blocked identities"
```

---

### Task 5: Documentation sync and full verification

**Files:**
- Modify: `docs/architecture/database-schema.md`
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Modify: `docs/architecture/frontend-architecture.md`
- Modify: `docs/codebase/frontend-components.md`
- Modify: `frontend/CONTEXT.md`
- Modify: `backend/CONTEXT.md`

**Interfaces:**
- Consumes: implemented behavior from Tasks 1-4.
- Produces: documentation that no longer describes BlockedClient soft-delete and describes SettingsPage as category nav + active panel.

- [ ] **Step 1: Update database schema docs**

In `docs/architecture/database-schema.md`, replace the `BlockedClient` column table with:

```markdown
### `BlockedClient` — `blocked_clients` table

Tenant-scoped block for unregistered WhatsApp identities that should not receive console replies. A row represents an active block; unblocking deletes the row.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, auto-generated |
| tenant_id | UUID | FK → tenants.id CASCADE, not null |
| phone | VARCHAR(50) | Nullable, canonical digits-only |
| whatsapp_lid | VARCHAR(100) | Nullable, `@lid` identity |
| created_at | TIMESTAMPTZ | From TimestampMixin |
| updated_at | TIMESTAMPTZ | From TimestampMixin |

Constraints: at least one identity field required (phone or whatsapp_lid) enforced at the repository layer. Indexes: `(tenant_id, phone)` and `(tenant_id, whatsapp_lid)`.
```

Add migration row 24 to the migration list:

```markdown
24. `e013fe74cab3` — Delete inactive `blocked_clients` rows and drop `blocked_clients.is_active`; row existence now represents an active block
```

- [ ] **Step 2: Update WhatsApp block docs**

In `docs/architecture/whatsapp-console-flow.md`, replace the Blocked Clients storage and repository sections with:

```markdown
### Storage

- Table: `blocked_clients`
- At least one identity field required (`phone` or `whatsapp_lid`)
- A row represents an active block
- Unblocking deletes the row
- No inactive block rows are kept
- Tenant-scoped indexes on `(tenant_id, phone)` and `(tenant_id, whatsapp_lid)`

### Repository operations (`blocked_clients_repository.py`)

| Operation | Description |
|-----------|-------------|
| `create(db, tenant_id, phone=, whatsapp_lid=)` | Create a block row |
| `list_active(db, tenant_id)` | List existing block rows, newest first |
| `find_active(db, tenant_id, phone=, whatsapp_lid=)` | Find a block by identity; matches by either identifier when both are provided |
| `unblock(db, tenant_id, block_id)` | Delete a specific block row |
| `clear_identity(db, tenant_id, phone=, whatsapp_lid=)` | Delete all blocks for an identity |
```

- [ ] **Step 3: Update frontend docs**

In `docs/architecture/frontend-architecture.md` and `docs/codebase/frontend-components.md`, add or update the Settings Page description to this exact wording:

```markdown
`SettingsPage` renders tenant settings as a flat category list plus a single active detail panel. No category opens by default; the panel shows a guide message until the user selects a category. Desktop uses a lateral category menu, mobile uses a `Sheet` category picker, long sections scroll inside the detail panel, and the common Cancelar action closes the active section so unsaved local edits are discarded by unmounting the section component.
```

- [ ] **Step 4: Update context docs**

In `backend/CONTEXT.md`, replace the `BlockedClient` definition with:

```markdown
| **BlockedClient** | Identidad de WhatsApp bloqueada. Model: `BlockedClient`. Una fila en `blocked_clients` representa un bloqueo activo; desbloquear elimina la fila. Al bloquear, se cancelan sesiones activas de código y jobs pendientes/processing para esa identidad. |
```

In `frontend/CONTEXT.md`, ensure the `Settings Page` and `AccessControlSection` rows state:

```markdown
| **Settings Page** | Superficie de configuración del tenant admin. Usa navegación por categorías con un único panel activo para editar una sección a la vez; en móvil la selección de categoría se abre desde un drawer. El panel activo usa scroll interno para secciones largas e incluye una acción común de Cancelar que cierra la sección y descarta cambios locales no guardados. |
| **AccessControlSection** | Sección en Settings para listar/bloquear/desbloquear identidades de WhatsApp. Disponible tanto para Starter como Pro. La lista visible se pagina en grupos de 10 bloqueos. |
```

- [ ] **Step 5: Run full frontend verification**

Run:

```bash
cd frontend && npm test -- --run
cd frontend && npm run build
```

Expected: PASS for both commands.

- [ ] **Step 6: Run full backend verification**

Run:

```bash
cd backend && uv run pytest
cd backend && uv run ruff check .
```

Expected: PASS for both commands.

- [ ] **Step 7: Grep for removed contract leaks**

Run:

```bash
rg "BlockedClient\.is_active|blocked_clients.*is_active|is_active.*blocked_clients|\"is_active\"" backend/app backend/tests frontend/src/features/admin/services/access-control-api.ts frontend/src/features/admin/components/access-control-section.tsx docs backend/CONTEXT.md frontend/CONTEXT.md
```

Expected: no results related to `BlockedClient`, `blocked_clients`, or `AccessControlBlock`. Results for tenants/clients are allowed only if they do not mention blocked clients.

- [ ] **Step 8: Commit Task 5**

```bash
git add docs/architecture/database-schema.md docs/architecture/whatsapp-console-flow.md docs/architecture/frontend-architecture.md docs/codebase/frontend-components.md frontend/CONTEXT.md backend/CONTEXT.md
git commit -m "docs(access-control): document row-existence blocks"
```

---

## Self-Review

**Spec coverage:**
- Settings category navigation, no default section, guide message, desktop lateral menu, mobile drawer, internal panel scroll, inline reminders, common Cancelar, and local edit discard are covered by Task 3.
- Access Control frontend pagination with 10 rows, previous/next, numbered pages, block/unblock refresh, and no server pagination are covered by Task 4.
- BlockedClient row-existence semantics, removal of `is_active`, migration cleanup, API contract removal, web DELETE hard-delete, tenant WhatsApp console, Client Context Shortcut, and client creation clearing are covered by Tasks 1 and 2.
- Documentation sync is covered by Task 5.

**Placeholder scan:** No placeholder markers, incomplete implementation steps, or unspecified test commands remain in this plan.

**Type consistency:** `SectionId`, `SettingsSection`, `AccessControlBlock`, `blocked_clients_repository.unblock`, and `clear_identity` signatures are consistent across tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-27-settings-access-control.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.
