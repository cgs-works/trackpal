# Tenant Settings Locale Timezone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Move tenant-global `locale` and `timezone` into a dedicated `tenant_settings` table and make `/api/v1/tenant-settings` the only write owner for both settings.

**Architecture:** Add a one-to-one `TenantSettings` domain next to `Tenant`, with explicit repository/service access instead of lazy `Tenant.settings` reads. REST, WhatsApp, subscription reminders, cleanup jobs, and frontend settings will read tenant-global preferences from `tenant_settings`; reminder settings will keep only reminder-specific fields.

**Tech Stack:** FastAPI, Pydantic v2, async SQLAlchemy, Alembic, pytest/httpx ASGI tests, React 19, Zustand, Vite, TypeScript.

---

## Skills required by this plan

- Every task: `superpowers:test-driven-development`, `superpowers:verification-before-completion`.
- Backend API/schema/service tasks: `fastapi-expert`, `python-pro`.
- Frontend API/store/component tasks: `vercel-react-best-practices`, `uncodixfy`.
- Execution workflow: `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

## Non-negotiable constraints

1. Do not add `timezone` to `tenants`.
2. Do not keep `locale` on `tenants` after the migration/model refactor.
3. Do not keep `timezone` on `subscription_reminder_settings` after the migration/model refactor.
4. Do not add compatibility properties like `Tenant.locale` that hide async lazy loading.
5. Do not change n8n workflows for this issue.
6. Do not redesign the full settings page. Move ownership cleanly using the current React/Zustand UI.
7. Frontend docs are stale where they mention Vue/Pinia. Follow current code: React/TSX + Zustand.
8. The frontend package currently has no `npm test` script. Use `npm run build` and `npm run lint` for frontend verification unless a later task explicitly adds a test runner.
9. Run backend tests from `backend/`; run frontend commands from `frontend/`.
10. Commit after each task when it passes.

## Target file map

### Create

- `backend/app/models/tenant_settings.py` — ORM model for one tenant-global settings row per tenant.
- `backend/app/schemas/tenant_settings.py` — Pydantic request/response schemas.
- `backend/app/repositories/tenant_settings_repository.py` — explicit settings queries and batched lookup helpers.
- `backend/app/services/tenant_settings_service.py` — validation, get-or-create, mutation transaction boundary.
- `backend/app/api/v1/endpoints/tenant_settings.py` — `/tenant-settings` API group and timezone catalog endpoint.
- `backend/alembic/versions/d011fe74cab0_create_tenant_settings.py` — migration from existing columns into `tenant_settings`.
- `backend/tests/test_tenant_settings.py` — model, service, and API tests for tenant settings.

### Modify

- `backend/app/models/__init__.py` — export `TenantSettings`.
- `backend/app/models/tenant.py` — remove `locale`, add explicit relationship.
- `backend/app/models/subscription.py` — remove reminder-settings `timezone`.
- `backend/tests/conftest.py` — create default `TenantSettings` rows in tenant fixtures.
- `backend/tests/test_rls_policy_sql.py` — assert RLS SQL for `tenant_settings`.
- `backend/app/api/v1/router.py` — include tenant settings router.
- `backend/app/api/dependencies.py` — resolve locale through tenant settings repository.
- `backend/app/api/v1/endpoints/i18n.py` — resolve catalog locale through tenant settings repository.
- `backend/app/api/v1/endpoints/me.py` — project locale/timezone read-only from tenant settings.
- `backend/app/services/profile_service/service.py` — stop writing locale through `/me`.
- `backend/app/schemas/me.py` — remove `locale` from `ProfileUpdate`, add `timezone` to `ProfileResponse`.
- `backend/app/repositories/tenants_repository.py` — remove tenant-table locale SQL and delegate locale helpers.
- `backend/app/services/tenant_service/mutations.py` — create settings row for new tenants.
- `backend/app/api/v1/endpoints/subscriptions/settings.py` — remove old timezone catalog path and timezone write handling.
- `backend/app/schemas/subscription/create_update.py` — remove reminder update `timezone`.
- `backend/app/schemas/subscription/responses.py` — remove reminder response `timezone`.
- `backend/app/services/subscription_service/reminder_settings.py` — stop creating/updating timezone.
- `backend/app/services/subscription_job_service/reminder_schedule.py` — batch-load tenant settings.
- `backend/app/services/subscription_job_service/reminder_payloads.py` — use settings timezone/locale.
- `backend/app/services/subscription_job_service/cleanup.py` — compute tenant-local end-of-day from settings timezone.
- `backend/app/services/whatsapp_tenant_console_facade/facade.py` — resolve locale from tenant settings.
- `backend/app/services/whatsapp_tenant_console_service/profile_flow.py` — update locale through tenant settings service.
- `backend/tests/test_i18n.py`, `backend/tests/test_profile.py`, `backend/tests/test_subscriptions.py`, `backend/tests/test_tenant_console_service.py` — update behavior tests.
- `frontend/src/features/admin/services/settings-api.ts` — add tenant settings types/functions, remove profile locale write type.
- `frontend/src/features/admin/services/reminder-api.ts` — remove reminder timezone types/functions.
- `frontend/src/store/settings.ts` — split reminder settings, tenant settings, and timezone option caches.
- `frontend/src/features/admin/components/profile-section.tsx` — edit identity and tenant settings through separate APIs.
- `frontend/src/features/admin/components/reminder-settings-modal.tsx` — remove timezone picker and show read-only timezone note.
- `frontend/src/features/admin/components/settings-page.tsx` — keep current layout; make profile section load tenant settings through store.
- Architecture docs listed in Task 9.

---

## Task 1: Backend model and test fixtures foundation

**Required skills:** `python-pro`, `superpowers:test-driven-development`.

**Files:**
- Create: `backend/app/models/tenant_settings.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/tenant.py`
- Modify: `backend/app/models/subscription.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_tenant_settings.py`
- Test: `backend/tests/test_subscriptions.py`

- [x] **Step 1: Write failing model/default tests**

Create `backend/tests/test_tenant_settings.py` with:

```python
import pytest
from sqlalchemy import select

from app.models import Tenant, TenantSettings

pytestmark = pytest.mark.asyncio


async def _tenant_for_user(db_session, user_id):
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user_id)
    )
    return result.scalar_one()


async def test_tenant_settings_model_defaults_persist(db_session, active_tenant_user):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)

    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    settings = result.scalar_one()

    assert settings.tenant_id == tenant.id
    assert settings.locale == "en"
    assert settings.timezone == "UTC"
    assert settings.created_at is not None
    assert settings.updated_at is not None


async def test_tenant_settings_can_store_locale_and_timezone(db_session, active_tenant_user):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    settings = result.scalar_one()

    settings.locale = "es"
    settings.timezone = "America/Santo_Domingo"
    await db_session.commit()

    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    persisted = result.scalar_one()
    assert persisted.locale == "es"
    assert persisted.timezone == "America/Santo_Domingo"
```

Update `backend/tests/test_subscriptions.py::test_subscription_reminder_settings` so it no longer asserts `settings_obj.timezone == "UTC"`.

- [x] **Step 2: Run tests to verify RED**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_settings.py tests/test_subscriptions.py::test_subscription_reminder_settings -q
```

Expected: FAIL because `TenantSettings` does not exist/export yet and `SubscriptionReminderSettings.timezone` still exists.

- [x] **Step 3: Add TenantSettings model**

Create `backend/app/models/tenant_settings.py`:

```python
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TenantSettings(Base, TimestampMixin):
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    locale: Mapped[str] = mapped_column(
        String(10), default="en", server_default="en", nullable=False
    )
    timezone: Mapped[str] = mapped_column(
        String(100), default="UTC", server_default="UTC", nullable=False
    )

    tenant = relationship("Tenant", back_populates="settings")
```

- [x] **Step 4: Update Tenant and SubscriptionReminderSettings models**

In `backend/app/models/tenant.py`, remove:

```python
    locale: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
```

Add this relationship after `plans = relationship(...)`:

```python
    settings = relationship(
        "TenantSettings",
        back_populates="tenant",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
```

In `backend/app/models/subscription.py`, remove this field from `SubscriptionReminderSettings`:

```python
    timezone: Mapped[str] = mapped_column(
        String(100), default="UTC", server_default="UTC", nullable=False
    )
```

- [x] **Step 5: Export TenantSettings**

Modify `backend/app/models/__init__.py`:

```python
from app.models.tenant_settings import TenantSettings
```

Add `"TenantSettings"` to `__all__` immediately after `"Tenant"`.

- [x] **Step 6: Create settings rows in test fixtures**

Modify `backend/tests/conftest.py` import line:

```python
from app.models import Base, Client, MasterProfile, Tenant, TenantSettings, User
```

In `active_tenant_user`, replace the direct `db_session.add(Tenant(...))` block with:

```python
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix="tna01",
        name="Active Tenant",
        whatsapp_phone="+12015550002",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.flush()
    db_session.add(TenantSettings(tenant_id=tenant.id))
```

In `deactivated_tenant_user`, replace the direct `db_session.add(Tenant(...))` block with:

```python
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix="tnb01",
        name="Inactive Tenant",
        whatsapp_phone="+12015550003",
        is_active=False,
    )
    db_session.add(tenant)
    await db_session.flush()
    db_session.add(TenantSettings(tenant_id=tenant.id))
```

- [x] **Step 7: Run tests to verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_settings.py tests/test_subscriptions.py::test_subscription_reminder_settings -q
```

Expected: PASS.

- [x] **Step 8: Commit**

```bash
git add backend/app/models backend/tests/conftest.py backend/tests/test_tenant_settings.py backend/tests/test_subscriptions.py
git commit -m "feat: add tenant settings model"
```

---

## Task 2: Alembic migration and RLS policy SQL

**Required skills:** `python-pro`, `superpowers:test-driven-development`.

**Files:**
- Create: `backend/alembic/versions/d011fe74cab0_create_tenant_settings.py`
- Modify: `backend/tests/test_rls_policy_sql.py`

- [x] **Step 1: Write failing RLS/migration SQL tests**

Append to `backend/tests/test_rls_policy_sql.py`:

```python
def test_tenant_settings_migration_moves_locale_and_timezone_with_rls():
    text = Path(
        "alembic/versions/d011fe74cab0_create_tenant_settings.py"
    ).read_text()

    assert "CREATE TABLE" in text or "op.create_table" in text
    assert "tenant_settings" in text
    assert "INSERT INTO tenant_settings" in text
    assert "COALESCE(t.locale, 'en')" in text
    assert "COALESCE(srs.timezone, 'UTC')" in text
    assert "op.drop_column(\"subscription_reminder_settings\", \"timezone\")" in text
    assert "op.drop_column(\"tenants\", \"locale\")" in text
    assert "ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY" in text
    assert "ALTER TABLE tenant_settings FORCE ROW LEVEL SECURITY" in text
    assert "CREATE POLICY tenant_settings_select" in text
    assert "CREATE POLICY tenant_settings_insert" in text
    assert "CREATE POLICY tenant_settings_update" in text
    assert "CREATE POLICY tenant_settings_delete" in text
    assert "owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')" in text
    assert "AND t.is_active" in text
```

Also add `Path("alembic/versions/d011fe74cab0_create_tenant_settings.py").read_text()` to the combined text in `test_rls_policy_sql_uses_required_context_settings`, and assert:

```python
    assert "tenant_settings_select" in text
    assert "tenant_settings_update" in text
```

- [x] **Step 2: Run RLS tests to verify RED**

Run:

```bash
cd backend && uv run pytest tests/test_rls_policy_sql.py -q
```

Expected: FAIL because the migration file does not exist.

- [x] **Step 3: Create migration**

Create `backend/alembic/versions/d011fe74cab0_create_tenant_settings.py`:

```python
"""create tenant settings

Revision ID: d011fe74cab0
Revises: 07fa809c3ab3
Create Date: 2026-06-12 17:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d011fe74cab0"
down_revision: Union[str, Sequence[str], None] = "07fa809c3ab3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tenant_settings_select_policy() -> str:
    return """
        CREATE POLICY tenant_settings_select ON tenant_settings
        FOR SELECT
        USING (
            current_setting('app.current_role', true) = 'master'
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND EXISTS (
                    SELECT 1
                    FROM tenants t
                    WHERE t.id = tenant_settings.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                )
            )
        )
    """


def _tenant_settings_write_condition() -> str:
    return """
            current_setting('app.current_role', true) = 'master'
            OR (
                current_setting('app.current_role', true) = 'tenant'
                AND EXISTS (
                    SELECT 1
                    FROM tenants t
                    WHERE t.id = tenant_settings.tenant_id
                      AND t.owner_user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
                      AND t.is_active
                )
            )
    """


def _tenant_settings_insert_policy() -> str:
    return f"""
        CREATE POLICY tenant_settings_insert ON tenant_settings
        FOR INSERT
        WITH CHECK ({_tenant_settings_write_condition()})
    """


def _tenant_settings_update_policy() -> str:
    condition = _tenant_settings_write_condition()
    return f"""
        CREATE POLICY tenant_settings_update ON tenant_settings
        FOR UPDATE
        USING ({condition})
        WITH CHECK ({condition})
    """


def _tenant_settings_delete_policy() -> str:
    return f"""
        CREATE POLICY tenant_settings_delete ON tenant_settings
        FOR DELETE
        USING ({_tenant_settings_write_condition()})
    """


def upgrade() -> None:
    op.create_table(
        "tenant_settings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("locale", sa.String(length=10), server_default="en", nullable=False),
        sa.Column(
            "timezone", sa.String(length=100), server_default="UTC", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id"),
    )

    op.execute(
        """
        INSERT INTO tenant_settings (tenant_id, locale, timezone)
        SELECT
            t.id,
            COALESCE(t.locale, 'en'),
            COALESCE(srs.timezone, 'UTC')
        FROM tenants t
        LEFT JOIN subscription_reminder_settings srs
            ON srs.tenant_id = t.id
        """
    )

    op.drop_column("subscription_reminder_settings", "timezone")
    op.drop_column("tenants", "locale")

    op.execute("ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_settings FORCE ROW LEVEL SECURITY")
    op.execute(_tenant_settings_select_policy())
    op.execute(_tenant_settings_insert_policy())
    op.execute(_tenant_settings_update_policy())
    op.execute(_tenant_settings_delete_policy())


def downgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("locale", sa.String(length=10), nullable=True),
    )
    op.execute(
        """
        UPDATE tenants
        SET locale = COALESCE(ts.locale, 'en')
        FROM tenant_settings ts
        WHERE ts.tenant_id = tenants.id
        """
    )
    op.execute("UPDATE tenants SET locale = 'en' WHERE locale IS NULL")
    op.alter_column(
        "tenants",
        "locale",
        existing_type=sa.String(length=10),
        nullable=False,
        server_default="en",
    )

    op.add_column(
        "subscription_reminder_settings",
        sa.Column(
            "timezone",
            sa.String(length=100),
            server_default="UTC",
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE subscription_reminder_settings
        SET timezone = COALESCE(ts.timezone, 'UTC')
        FROM tenant_settings ts
        WHERE ts.tenant_id = subscription_reminder_settings.tenant_id
        """
    )

    op.execute("DROP POLICY IF EXISTS tenant_settings_delete ON tenant_settings")
    op.execute("DROP POLICY IF EXISTS tenant_settings_update ON tenant_settings")
    op.execute("DROP POLICY IF EXISTS tenant_settings_insert ON tenant_settings")
    op.execute("DROP POLICY IF EXISTS tenant_settings_select ON tenant_settings")
    op.execute("ALTER TABLE tenant_settings NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_settings DISABLE ROW LEVEL SECURITY")
    op.drop_table("tenant_settings")
```

- [x] **Step 4: Run RLS tests to verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/test_rls_policy_sql.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/alembic/versions/d011fe74cab0_create_tenant_settings.py backend/tests/test_rls_policy_sql.py
git commit -m "feat: migrate tenant settings"
```

---

## Task 3: Tenant settings repository, service, schemas, and API

**Required skills:** `fastapi-expert`, `python-pro`, `superpowers:test-driven-development`.

**Files:**
- Create: `backend/app/schemas/tenant_settings.py`
- Create: `backend/app/repositories/tenant_settings_repository.py`
- Create: `backend/app/services/tenant_settings_service.py`
- Create: `backend/app/api/v1/endpoints/tenant_settings.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/services/tenant_service/mutations.py`
- Modify: `backend/tests/test_tenant_settings.py`

- [x] **Step 1: Add failing API/service tests**

Append to `backend/tests/test_tenant_settings.py`:

```python
from app.repositories import tenant_settings_repository


async def _login(client, username: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_get_tenant_settings_returns_defaults(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/tenant-settings", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["locale"] == "en"
    assert data["timezone"] == "UTC"
    assert data["tenant_id"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


async def test_put_tenant_settings_updates_locale_and_timezone(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/tenant-settings",
        json={"locale": "es", "timezone": "America/Santo_Domingo"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["locale"] == "es"
    assert data["timezone"] == "America/Santo_Domingo"


async def test_put_tenant_settings_rejects_invalid_locale(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/tenant-settings",
        json={"locale": "fr"},
        headers=headers,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("Locale must be one of" in str(err.get("msg", "")) for err in detail)


async def test_put_tenant_settings_rejects_invalid_timezone(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/tenant-settings",
        json={"timezone": "Not/AZone"},
        headers=headers,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("valid IANA timezone" in str(err.get("msg", "")) for err in detail)


async def test_tenant_settings_timezones_endpoint(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/tenant-settings/timezones", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert any(item["value"] == "UTC" for item in data)


async def test_tenant_settings_repository_resolves_defaults_when_missing(
    db_session, active_tenant_user
):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    settings = await tenant_settings_repository.get_by_tenant_id(db_session, tenant.id)
    await db_session.delete(settings)
    await db_session.commit()

    resolved = await tenant_settings_repository.resolve_timezone(db_session, tenant.id)

    assert resolved == "UTC"
```

- [x] **Step 2: Run API tests to verify RED**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_settings.py -q
```

Expected: FAIL because `/tenant-settings` API, schemas, service, and repository do not exist.

- [x] **Step 3: Add schemas**

Create `backend/app/schemas/tenant_settings.py`:

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.core import VALID_LOCALES
from app.services.subscription_service.timezone_catalog import validate_timezone


class TenantSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    locale: str
    timezone: str
    created_at: datetime
    updated_at: datetime


class TenantSettingsUpdate(BaseModel):
    model_config = ConfigDict()

    locale: str | None = None
    timezone: str | None = None

    @field_validator("locale")
    @classmethod
    def validate_locale_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in VALID_LOCALES:
            raise ValueError(f"Locale must be one of: {', '.join(VALID_LOCALES)}")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone_field(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not validate_timezone(value):
            raise ValueError(f"'{value}' is not a valid IANA timezone identifier")
        return value
```

- [x] **Step 4: Add repository**

Create `backend/app/repositories/tenant_settings_repository.py`:

```python
import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, Tenant, TenantSettings


async def get_by_tenant_id(
    db: AsyncSession, tenant_id: uuid.UUID
) -> TenantSettings | None:
    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_by_tenant_id(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[TenantSettings, bool]:
    settings = await get_by_tenant_id(db, tenant_id)
    if settings is not None:
        return settings, False

    settings = TenantSettings(tenant_id=tenant_id, locale="en", timezone="UTC")
    db.add(settings)
    await db.flush()
    return settings, True


async def update_settings(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    values: dict[str, object],
) -> TenantSettings:
    settings, _created = await get_or_create_by_tenant_id(db, tenant_id)
    for field in ("locale", "timezone"):
        if field in values:
            setattr(settings, field, values[field])
    await db.flush()
    return settings


async def resolve_locale(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    result = await db.execute(
        select(TenantSettings.locale).where(TenantSettings.tenant_id == tenant_id)
    )
    row = result.scalar_one_or_none()
    return row or "en"


async def resolve_locale_by_owner(db: AsyncSession, owner_user_id: uuid.UUID) -> str:
    result = await db.execute(
        select(TenantSettings.locale)
        .select_from(Tenant)
        .join(TenantSettings, TenantSettings.tenant_id == Tenant.id)
        .where(Tenant.owner_user_id == owner_user_id)
    )
    row = result.scalar_one_or_none()
    return row or "en"


async def resolve_locale_by_client(
    db: AsyncSession, client_owner_user_id: uuid.UUID
) -> str:
    result = await db.execute(
        select(TenantSettings.locale)
        .select_from(Client)
        .join(TenantSettings, TenantSettings.tenant_id == Client.tenant_id)
        .where(Client.owner_user_id == client_owner_user_id)
    )
    row = result.scalar_one_or_none()
    return row or "en"


async def resolve_timezone(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    result = await db.execute(
        select(TenantSettings.timezone).where(TenantSettings.tenant_id == tenant_id)
    )
    row = result.scalar_one_or_none()
    return row or "UTC"


async def get_settings_for_tenant_ids(
    db: AsyncSession, tenant_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, TenantSettings | None]:
    ids = list(set(tenant_ids))
    settings_map: dict[uuid.UUID, TenantSettings | None] = {tenant_id: None for tenant_id in ids}
    if not ids:
        return settings_map

    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id.in_(ids))
    )
    for settings in result.scalars().all():
        settings_map[settings.tenant_id] = settings
    return settings_map
```

- [x] **Step 5: Add service**

Create `backend/app/services/tenant_settings_service.py`:

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import VALID_LOCALES
from app.core.database import restore_rls_context
from app.models import TenantSettings
from app.repositories import tenant_settings_repository
from app.schemas.tenant_settings import TenantSettingsUpdate
from app.services.subscription_service.timezone_catalog import validate_timezone


class TenantSettingsService:
    async def get_settings(
        self, db: AsyncSession, tenant_id: uuid.UUID
    ) -> TenantSettings:
        settings, created = await tenant_settings_repository.get_or_create_by_tenant_id(
            db, tenant_id
        )
        if created:
            await db.commit()
            await restore_rls_context(db)
            await db.refresh(settings)
        return settings

    async def update_settings(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: TenantSettingsUpdate,
    ) -> TenantSettings:
        update_data = payload.model_dump(exclude_unset=True)

        locale = update_data.get("locale")
        if locale is not None and locale not in VALID_LOCALES:
            raise ValueError(f"Locale must be one of: {', '.join(VALID_LOCALES)}")

        timezone = update_data.get("timezone")
        if timezone is not None and not validate_timezone(str(timezone)):
            raise ValueError(f"'{timezone}' is not a valid IANA timezone identifier")

        settings = await tenant_settings_repository.update_settings(
            db, tenant_id, update_data
        )
        await db.commit()
        await restore_rls_context(db)
        await db.refresh(settings)
        return settings
```

- [x] **Step 6: Add API endpoint**

Create `backend/app/api/v1/endpoints/tenant_settings.py`:

```python
from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import ActiveTenantId, CurrentUser, DbDep
from app.api.v1.endpoints.subscriptions._common import require_tenant_or_master
from app.schemas.tenant_settings import TenantSettingsResponse, TenantSettingsUpdate
from app.services.subscription_service.timezone_catalog import list_timezones
from app.services.tenant_settings_service import TenantSettingsService

router = APIRouter(prefix="/tenant-settings", tags=["tenant-settings"])
service = TenantSettingsService()


@router.get("", response_model=TenantSettingsResponse)
async def get_tenant_settings(
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    return await service.get_settings(db, tenant_id)


@router.put("", response_model=TenantSettingsResponse)
async def update_tenant_settings(
    payload: TenantSettingsUpdate,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    try:
        return await service.update_settings(db, tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get("/timezones")
async def list_supported_timezones(current_user: CurrentUser):
    require_tenant_or_master(current_user)
    return await list_timezones()
```

- [x] **Step 7: Include router**

Modify `backend/app/api/v1/router.py` imports to include `tenant_settings`:

```python
from app.api.v1.endpoints import (
    auth,
    catalog,
    clients,
    code_services,
    dashboard,
    i18n,
    integrations,
    mailbox,
    me,
    tenant_settings,
    tenants,
    subscriptions,
)
```

Add this before subscription routers:

```python
api_router.include_router(tenant_settings.router)
```

- [x] **Step 8: Create default settings during tenant creation**

Modify `backend/app/services/tenant_service/mutations.py` imports:

```python
from app.models import Tenant, TenantSettings, User
```

After adding/flushing `profile`, add:

```python
    db.add(TenantSettings(tenant_id=profile.id, locale="en", timezone="UTC"))
    await db.flush()
```

- [x] **Step 9: Run tests to verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_settings.py tests/test_tenants.py -q
```

Expected: PASS.

- [x] **Step 10: Commit**

```bash
git add backend/app/schemas/tenant_settings.py backend/app/repositories/tenant_settings_repository.py backend/app/services/tenant_settings_service.py backend/app/api/v1/endpoints/tenant_settings.py backend/app/api/v1/router.py backend/app/services/tenant_service/mutations.py backend/tests/test_tenant_settings.py
git commit -m "feat: add tenant settings API"
```

---

## Task 4: Move locale ownership out of Tenant and /me

**Required skills:** `fastapi-expert`, `python-pro`, `superpowers:test-driven-development`.

**Files:**
- Modify: `backend/app/api/dependencies.py`
- Modify: `backend/app/api/v1/endpoints/i18n.py`
- Modify: `backend/app/api/v1/endpoints/me.py`
- Modify: `backend/app/repositories/tenants_repository.py`
- Modify: `backend/app/schemas/me.py`
- Modify: `backend/app/services/profile_service/service.py`
- Modify: `backend/tests/test_i18n.py`
- Modify: `backend/tests/test_profile.py`

- [x] **Step 1: Update locale tests to use `/tenant-settings` as write owner**

In `backend/tests/test_i18n.py`, replace every locale mutation like:

```python
await client.put("/api/v1/me", json={"locale": "es"}, headers=headers)
```

with:

```python
await client.put("/api/v1/tenant-settings", json={"locale": "es"}, headers=headers)
```

Replace `test_update_profile_locale_valid`, `test_update_profile_locale_invalid`, and `test_update_profile_locale_case_insensitive` with:

```python
async def test_update_profile_locale_is_ignored_by_me(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/me",
        json={"locale": "es", "full_name": "Tenant Updated"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Tenant Updated"
    assert data["locale"] == "en"


async def test_update_tenant_settings_locale_valid(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/tenant-settings",
        json={"locale": "ES"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["locale"] == "es"


async def test_update_tenant_settings_locale_invalid(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/tenant-settings",
        json={"locale": "fr"},
        headers=headers,
    )

    assert response.status_code == 422
```

In `backend/tests/test_profile.py::test_change_password_client_uses_tenant_locale`, replace the `/me` locale update with `/tenant-settings`.

Append to `backend/tests/test_profile.py`:

```python
async def test_get_profile_tenant_projects_tenant_settings(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")
    await client.put(
        "/api/v1/tenant-settings",
        json={"locale": "es", "timezone": "America/Santo_Domingo"},
        headers=headers,
    )

    response = await client.get("/api/v1/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["locale"] == "es"
    assert data["timezone"] == "America/Santo_Domingo"
```

- [x] **Step 2: Run locale/profile tests to verify RED**

Run:

```bash
cd backend && uv run pytest tests/test_i18n.py tests/test_profile.py -q
```

Expected: FAIL because `/me` still reads/writes `Tenant.locale` and `ProfileResponse` has no `timezone`.

- [x] **Step 3: Delegate locale helpers from tenants repository**

Modify `backend/app/repositories/tenants_repository.py` imports:

```python
from app.repositories import tenant_settings_repository
```

Replace `resolve_locale`, `resolve_locale_by_owner`, and `resolve_locale_by_client` bodies with:

```python
async def resolve_locale(db: AsyncSession, tenant_id: UUID) -> str:
    """Resolve tenant locale from tenant settings, defaulting to ``"en"``."""
    return await tenant_settings_repository.resolve_locale(db, tenant_id)


async def resolve_locale_by_owner(db: AsyncSession, owner_user_id: UUID) -> str:
    """Resolve tenant locale by owner user id from tenant settings."""
    return await tenant_settings_repository.resolve_locale_by_owner(db, owner_user_id)


async def resolve_locale_by_client(db: AsyncSession, client_owner_user_id: UUID) -> str:
    """Resolve tenant locale from a client owner user id through tenant settings."""
    return await tenant_settings_repository.resolve_locale_by_client(
        db, client_owner_user_id
    )
```

Remove the old `select(Tenant.locale)` queries.

- [x] **Step 4: Update dependency and i18n imports**

In `backend/app/api/dependencies.py`, change imports:

```python
from app.repositories import clients_repository, tenant_settings_repository, tenants_repository, users_repository
```

Change `resolve_locale` to:

```python
async def resolve_locale(db: AsyncSession, tenant_id: UUID) -> str:
    """Resolve locale string for a tenant from tenant settings."""
    return await tenant_settings_repository.resolve_locale(db, tenant_id)
```

In `backend/app/api/v1/endpoints/i18n.py`, import `tenant_settings_repository` instead of `tenants_repository`, then use:

```python
    if current_user.role == "tenant":
        locale = await tenant_settings_repository.resolve_locale_by_owner(db, current_user.id)
    elif current_user.role == "client":
        locale = await tenant_settings_repository.resolve_locale_by_client(db, current_user.id)
```

- [x] **Step 5: Update `/me` schemas and service**

In `backend/app/schemas/me.py`, add `timezone` to `ProfileResponse`:

```python
    timezone: str | None = None
```

Remove this field from `ProfileUpdate`:

```python
    locale: str | None = None
```

Remove the `validate_locale_field` validator entirely. If `VALID_LOCALES` becomes unused in this file, remove its import.

In `backend/app/services/profile_service/service.py`, change allowed tenant fields:

```python
        allowed_fields: set[str] = (
            {"name", "phone"}
            if user.role == "master"
            else {"full_name", "email", "phone"}
        )
```

- [x] **Step 6: Update `/me` endpoint projection**

In `backend/app/api/v1/endpoints/me.py`, import:

```python
from app.repositories import tenant_settings_repository
```

Replace `_profile_response` with:

```python
def _profile_response(user, profile, *, locale: str | None = None, timezone: str | None = None) -> ProfileResponse:
    tenant = getattr(profile, "tenant", None)
    tenant_id = getattr(profile, "tenant_id", None)
    if user.role == "tenant":
        tenant_id = getattr(profile, "id", None)

    return ProfileResponse(
        role=user.role,
        username=user.username,
        name=getattr(profile, "name", None),
        full_name=getattr(profile, "full_name", None),
        tenant_id=tenant_id,
        tenant_name=getattr(tenant, "name", None),
        client_prefix=getattr(tenant, "client_prefix", None),
        locale=locale,
        timezone=timezone,
        email=getattr(profile, "email", None),
        phone=getattr(profile, "phone", None),
        is_active=getattr(profile, "is_active", None),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
```

Add helper:

```python
async def _resolve_profile_settings(db: DbDep, current_user, profile) -> tuple[str | None, str | None]:
    if current_user.role == "tenant":
        settings, _created = await tenant_settings_repository.get_or_create_by_tenant_id(
            db, profile.id
        )
        if _created:
            await db.commit()
            await db.refresh(settings)
        return settings.locale, settings.timezone

    if current_user.role == "client":
        tenant_id = getattr(profile, "tenant_id", None)
        if tenant_id is None:
            return "en", "UTC"
        locale = await tenant_settings_repository.resolve_locale(db, tenant_id)
        timezone = await tenant_settings_repository.resolve_timezone(db, tenant_id)
        return locale, timezone

    return None, None
```

In `get_profile`, before returning:

```python
    locale, timezone = await _resolve_profile_settings(db, current_user, profile)
    return _profile_response(current_user, profile, locale=locale, timezone=timezone)
```

In `update_profile`, before returning:

```python
    locale, timezone = await _resolve_profile_settings(db, current_user, profile)
    return _profile_response(current_user, profile, locale=locale, timezone=timezone)
```

- [x] **Step 7: Run tests to verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/test_i18n.py tests/test_profile.py tests/test_tenant_settings.py -q
```

Expected: PASS.

- [x] **Step 8: Commit**

```bash
git add backend/app/api/dependencies.py backend/app/api/v1/endpoints/i18n.py backend/app/api/v1/endpoints/me.py backend/app/repositories/tenants_repository.py backend/app/schemas/me.py backend/app/services/profile_service/service.py backend/tests/test_i18n.py backend/tests/test_profile.py
git commit -m "refactor: move locale writes to tenant settings"
```

---

## Task 5: Remove timezone from subscription settings API

**Required skills:** `fastapi-expert`, `python-pro`, `superpowers:test-driven-development`.

**Files:**
- Modify: `backend/app/api/v1/endpoints/subscriptions/settings.py`
- Modify: `backend/app/schemas/subscription/create_update.py`
- Modify: `backend/app/schemas/subscription/responses.py`
- Modify: `backend/app/services/subscription_service/reminder_settings.py`
- Modify: `backend/tests/test_subscriptions.py`

- [x] **Step 1: Add/update failing subscription settings contract tests**

In `backend/tests/test_subscriptions.py`, update reminder settings API tests so expected payloads omit `timezone`. Add these tests near existing subscription reminder settings endpoint tests:

```python
@pytest.mark.asyncio
async def test_get_subscription_settings_does_not_return_timezone(client, active_tenant_user):
    headers = await _login_headers(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/subscription-settings", headers=headers)

    assert response.status_code == 200
    assert "timezone" not in response.json()


@pytest.mark.asyncio
async def test_put_subscription_settings_ignores_timezone_field(client, active_tenant_user):
    headers = await _login_headers(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/subscription-settings",
        json={"timezone": "America/Santo_Domingo", "reminder_time": "10:30"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["reminder_time"] == "10:30"
    assert "timezone" not in data


@pytest.mark.asyncio
async def test_old_subscription_timezones_endpoint_is_removed(client, active_tenant_user):
    headers = await _login_headers(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/subscription-settings/timezones", headers=headers)

    assert response.status_code == 405 or response.status_code == 404
```

- [x] **Step 2: Run subscription tests to verify RED**

Run:

```bash
cd backend && uv run pytest tests/test_subscriptions.py -q
```

Expected: FAIL because subscription settings still return and accept `timezone`, and old timezones endpoint still exists.

- [x] **Step 3: Remove timezone from schemas**

In `backend/app/schemas/subscription/create_update.py`, remove:

```python
from app.services.subscription_service.timezone_catalog import validate_timezone
```

Remove `timezone` from `SubscriptionReminderSettingsUpdate`:

```python
    timezone: Optional[str] = None
```

Remove `validate_timezone_field` entirely.

In `backend/app/schemas/subscription/responses.py`, remove this from `SubscriptionReminderSettingsResponse`:

```python
    timezone: str
```

- [x] **Step 4: Remove timezone from reminder settings service**

In `backend/app/services/subscription_service/reminder_settings.py`, remove `timezone="UTC"` from the `SubscriptionReminderSettings(...)` constructor.

Remove this update block:

```python
    if "timezone" in update_data:
        settings.timezone = update_data["timezone"]
```

- [x] **Step 5: Remove old timezone catalog endpoint**

In `backend/app/api/v1/endpoints/subscriptions/settings.py`, remove:

```python
from app.services.subscription_service.timezone_catalog import list_timezones
```

Remove the whole function:

```python
@settings_router.get("/timezones")
async def list_supported_timezones(...):
    ...
```

- [x] **Step 6: Run tests to verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/test_subscriptions.py tests/test_tenant_settings.py -q
```

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add backend/app/api/v1/endpoints/subscriptions/settings.py backend/app/schemas/subscription/create_update.py backend/app/schemas/subscription/responses.py backend/app/services/subscription_service/reminder_settings.py backend/tests/test_subscriptions.py
git commit -m "refactor: remove timezone from reminder settings"
```

---

## Task 6: Update reminder jobs, cleanup, and WhatsApp locale consumers

**Required skills:** `python-pro`, `superpowers:test-driven-development`.

**Files:**
- Modify: `backend/app/services/subscription_job_service/reminder_schedule.py`
- Modify: `backend/app/services/subscription_job_service/reminder_payloads.py`
- Modify: `backend/app/services/subscription_job_service/cleanup.py`
- Modify: `backend/app/services/whatsapp_tenant_console_facade/facade.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/profile_flow.py`
- Modify: `backend/tests/test_subscriptions.py`
- Modify: `backend/tests/test_tenant_console_service.py`

- [x] **Step 1: Add failing reminder payload tests for tenant settings timezone/locale**

In `backend/tests/test_subscriptions.py`, update existing reminder payload setup so tenant timezone/locale are set through `TenantSettings`, not `SubscriptionReminderSettings`. Add this test near reminder payload generation tests:

```python
@pytest.mark.asyncio
async def test_reminder_payload_uses_tenant_settings_timezone_and_locale(
    db_session, active_tenant_user
):
    from sqlalchemy import select
    from app.models import TenantSettings
    from app.services.subscription_job_service import reminder_payloads

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    settings = (
        await db_session.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        )
    ).scalar_one()
    settings.locale = "es"
    settings.timezone = "America/Santo_Domingo"

    # Reuse the existing local helpers in this file to create an active subscription
    # expiring on a warning day and enabled reminder settings.
    subscription = await _create_subscription_fixture(
        db_session,
        tenant,
        expires_at=datetime(2026, 7, 15, 13, 0, tzinfo=timezone.utc),
    )
    reminder_settings = SubscriptionReminderSettings(
        tenant_id=tenant.id,
        warning_days=[7],
        reminder_time="09:00",
        recipient_mode="tenant_only",
        reminders_enabled=True,
    )
    db_session.add(reminder_settings)
    await db_session.commit()

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 8, 14, 0, tzinfo=timezone.utc)

    with patch.object(reminder_payloads, "datetime", FixedDateTime):
        result = await reminder_payloads.generate_reminder_payloads(db_session)

    assert len(result["items"]) == 1
    assert "días" in result["items"][0]["message"]
    assert result["items"][0]["tenant_id"] == str(tenant.id)
```

If `_create_subscription_fixture` does not exist, extract the existing repeated setup in `test_subscriptions.py` into a helper before adding this test. The helper must return a persisted `Subscription` with client/service/plan relationships populated.

- [x] **Step 2: Add failing cleanup timezone boundary test**

Append to `backend/tests/test_subscriptions.py` near cleanup tests:

```python
@pytest.mark.asyncio
async def test_cleanup_uses_tenant_settings_timezone_for_end_of_day(
    db_session, active_tenant_user
):
    from sqlalchemy import select
    from app.models import TenantSettings
    from app.services.subscription_job_service.cleanup import _get_tenant_end_of_day

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    settings = (
        await db_session.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        )
    ).scalar_one()
    settings.timezone = "America/New_York"
    await db_session.commit()

    now = datetime(2026, 1, 2, 15, 0, tzinfo=timezone.utc)

    eod = await _get_tenant_end_of_day(db_session, tenant.id, now)

    assert eod == datetime(2026, 1, 3, 4, 59, 59, tzinfo=timezone.utc)
```

- [x] **Step 3: Add failing WhatsApp locale update test**

In `backend/tests/test_tenant_console_service.py`, add a focused test for profile locale flow persistence:

```python
@pytest.mark.asyncio
async def test_tenant_console_profile_locale_updates_tenant_settings(db_session, active_tenant_user):
    from sqlalchemy import select
    from app.models import Tenant, TenantSettings
    from app.services.whatsapp_tenant_console_service import WhatsAppTenantConsoleService

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    settings = (
        await db_session.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        )
    ).scalar_one()
    assert settings.locale == "en"

    service = WhatsAppTenantConsoleService()
    session_service = WhatsAppSessionService(FakeManager())
    session = await session_service.create_session("admin:12015550002")
    session.flow = service.PROFILE_FLOW
    session.step = service.PROFILE_STEP_CHANGE_LOCALE_SELECT
    await session_service.save_session(session)

    response = await service.process_message(
        phone="12015550002",
        message="2",
        tenant_id=tenant.id,
        user_id=active_tenant_user.id,
        db=db_session,
        session_service=session_service,
        locale="en",
    )

    refreshed = (
        await db_session.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        )
    ).scalar_one()
    assert refreshed.locale == "es"
    assert "Español" in response
```

- [x] **Step 4: Run targeted tests to verify RED**

Run:

```bash
cd backend && uv run pytest tests/test_subscriptions.py tests/test_tenant_console_service.py -q
```

Expected: FAIL because reminder jobs, cleanup, and WhatsApp still use old fields.

- [x] **Step 5: Batch-load tenant settings in reminder schedule**

Modify `backend/app/services/subscription_job_service/reminder_schedule.py` imports:

```python
from app.models import TenantSettings
from app.repositories import tenant_settings_repository
```

Change `load_batched_reminder_data` return type to:

```python
) -> tuple[
    dict[Any, SubscriptionReminderSettings | None],
    dict[Any, Tenant | None],
    dict[Any, TenantSettings | None],
]:
```

Before `return`, add:

```python
    tenant_settings_map = await tenant_settings_repository.get_settings_for_tenant_ids(
        db, tenant_ids
    )

    return settings_map, tenants_map, tenant_settings_map
```

Remove the old two-map return.

- [x] **Step 6: Use tenant settings in reminder payloads**

In `backend/app/services/subscription_job_service/reminder_payloads.py`, change:

```python
    settings_map, tenants_map = await load_batched_reminder_data(db, subs)
```

to:

```python
    settings_map, tenants_map, tenant_settings_map = await load_batched_reminder_data(db, subs)
```

Inside the loop after `tenant = tenants_map.get(...)`, add:

```python
            tenant_settings = tenant_settings_map.get(sub.tenant_id)
```

Replace timezone resolution:

```python
            tz_name = settings.timezone or "UTC"
```

with:

```python
            tz_name = getattr(tenant_settings, "timezone", None) or "UTC"
```

Replace locale resolution:

```python
                    locale = getattr(tenant, "locale", "en") or "en"
```

with:

```python
                    locale = getattr(tenant_settings, "locale", None) or "en"
```

Do not skip reminder generation only because `tenant_settings` is missing. The fallback is `locale='en'`, `timezone='UTC'`.

- [x] **Step 7: Use tenant settings timezone in cleanup**

In `backend/app/services/subscription_job_service/cleanup.py`, import:

```python
from datetime import time
from zoneinfo import ZoneInfo
from app.repositories import tenant_settings_repository
```

Remove `SubscriptionReminderSettings` from imports.

Replace `_get_tenant_timezone_map` with:

```python
async def _get_tenant_timezone_map(db: AsyncSession) -> dict[uuid.UUID, str]:
    res = await db.execute(select(Subscription.tenant_id).distinct())
    tenant_ids = list(res.scalars().all())
    settings_map = await tenant_settings_repository.get_settings_for_tenant_ids(
        db, tenant_ids
    )
    return {
        tenant_id: (getattr(settings, "timezone", None) or "UTC")
        for tenant_id, settings in settings_map.items()
    }
```

Replace `_get_tenant_end_of_day` signature and body with:

```python
async def _get_tenant_end_of_day(
    db: AsyncSession, tenant_id: uuid.UUID, now: datetime
) -> datetime:
    tz_name = await tenant_settings_repository.resolve_timezone(db, tenant_id)
    try:
        tz = ZoneInfo(tz_name)
    except (KeyError, TypeError, ValueError):
        tz = timezone.utc

    local_now = now.astimezone(tz)
    local_eod = datetime.combine(
        local_now.date(), time(23, 59, 59), tzinfo=tz
    )
    return local_eod.astimezone(timezone.utc)
```

Update caller in `_expire_active_subs`:

```python
            eod = await _get_tenant_end_of_day(db, sub.tenant_id, now)
```

- [x] **Step 8: Update WhatsApp facade locale resolution**

In `backend/app/services/whatsapp_tenant_console_facade/facade.py`, import:

```python
from app.repositories import tenant_settings_repository
```

Replace inactive/active locale resolution block with:

```python
            locale = await tenant_settings_repository.resolve_locale_by_owner(
                db, tenant.owner_user_id
            )
            if not tenant.is_active:
                return _t(locale, "wa.tenant.facade.inactive_tenant")
            tenant_id = tenant.id
```

This keeps inactive-account responses localized from `tenant_settings`.

- [x] **Step 9: Update WhatsApp profile locale flow**

In `backend/app/services/whatsapp_tenant_console_service/profile_flow.py`, remove:

```python
from sqlalchemy import update as sa_update
from app.models import Tenant
```

Add imports:

```python
from app.repositories import tenants_repository
from app.schemas.tenant_settings import TenantSettingsUpdate
from app.services.tenant_settings_service import TenantSettingsService
```

Replace the direct SQL update block in `_handle_profile_change_locale_select`:

```python
    if user_id is not None and db is not None:
        await db.execute(
            sa_update(Tenant)
            .where(Tenant.owner_user_id == user_id)
            .values(locale=new_locale)
        )
        await db.commit()
```

with:

```python
    if user_id is not None and db is not None:
        tenant = await tenants_repository.get_by_owner(db, user_id)
        if tenant is not None:
            service = TenantSettingsService()
            await service.update_settings(
                db,
                tenant.id,
                TenantSettingsUpdate(locale=new_locale),
            )
```

- [x] **Step 10: Run targeted tests to verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/test_subscriptions.py tests/test_tenant_console_service.py -q
```

Expected: PASS.

- [x] **Step 11: Commit**

```bash
git add backend/app/services/subscription_job_service/reminder_schedule.py backend/app/services/subscription_job_service/reminder_payloads.py backend/app/services/subscription_job_service/cleanup.py backend/app/services/whatsapp_tenant_console_facade/facade.py backend/app/services/whatsapp_tenant_console_service/profile_flow.py backend/tests/test_subscriptions.py backend/tests/test_tenant_console_service.py
git commit -m "refactor: use tenant settings in jobs and whatsapp"
```

---

## Task 7: Frontend API and Zustand store split

**Required skills:** `vercel-react-best-practices`, `uncodixfy`, `superpowers:test-driven-development`.

**Files:**
- Modify: `frontend/src/features/admin/services/settings-api.ts`
- Modify: `frontend/src/features/admin/services/reminder-api.ts`
- Modify: `frontend/src/store/settings.ts`

- [x] **Step 1: Run frontend baseline typecheck/build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS before frontend changes. If it fails, stop and record the pre-existing error before editing.

- [x] **Step 2: Update settings API types/functions**

Modify `frontend/src/features/admin/services/settings-api.ts`.

Add `timezone` to `Profile`:

```ts
  timezone: string | null;
```

Remove `locale?: string;` from `ProfileUpdate`.

Add tenant settings types below `PasswordChange`:

```ts
export interface TenantSettings {
  tenant_id: string;
  locale: string;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface TenantSettingsUpdate {
  locale?: string;
  timezone?: string;
}

export interface TimezoneOption {
  value: string;
  label: string;
  group: string;
}
```

Add API functions after profile functions:

```ts
export async function getTenantSettings(): Promise<TenantSettings> {
  const { data } = await api.get("/tenant-settings");
  return data;
}

export async function updateTenantSettings(
  payload: TenantSettingsUpdate
): Promise<TenantSettings> {
  const { data } = await api.put("/tenant-settings", payload);
  return data;
}

export async function getTimezones(): Promise<TimezoneOption[]> {
  const { data } = await api.get("/tenant-settings/timezones");
  return data;
}
```

- [x] **Step 3: Update reminder API types/functions**

Modify `frontend/src/features/admin/services/reminder-api.ts`:

Remove `timezone` from `ReminderSettings` and `ReminderSettingsUpdate`.

Remove the `TimezoneOption` interface.

Remove `getTimezones()`.

The file should still export only:

```ts
export interface ReminderSettings { ... }
export interface ReminderSettingsUpdate { ... }
export async function getReminderSettings(): Promise<ReminderSettings> { ... }
export async function updateReminderSettings(payload: ReminderSettingsUpdate): Promise<ReminderSettings> { ... }
```

- [x] **Step 4: Replace Zustand store with separated caches**

Rewrite `frontend/src/store/settings.ts` to this structure:

```ts
import { create } from "zustand";
import {
  getReminderSettings,
  updateReminderSettings as apiUpdateReminderSettings,
  type ReminderSettings,
  type ReminderSettingsUpdate,
} from "@/features/admin/services/reminder-api";
import {
  getTenantSettings,
  updateTenantSettings as apiUpdateTenantSettings,
  getTimezones,
  type TenantSettings,
  type TenantSettingsUpdate,
  type TimezoneOption,
} from "@/features/admin/services/settings-api";

interface SettingsState {
  reminderSettings: ReminderSettings | null;
  tenantSettings: TenantSettings | null;
  timezoneOptions: TimezoneOption[];
  reminderSettingsLoaded: boolean;
  tenantSettingsLoaded: boolean;
  timezonesLoaded: boolean;
  reminderSettingsInFlight: Promise<ReminderSettings | null> | null;
  tenantSettingsInFlight: Promise<TenantSettings | null> | null;
  timezonesInFlight: Promise<TimezoneOption[]> | null;
  settingsLoadError: string | null;

  loadReminderSettings: () => Promise<ReminderSettings | null>;
  loadTenantSettings: () => Promise<TenantSettings | null>;
  loadTimezoneOptions: () => Promise<TimezoneOption[]>;
  updateReminderSettings: (
    settings: ReminderSettingsUpdate
  ) => Promise<ReminderSettings>;
  updateTenantSettings: (
    settings: TenantSettingsUpdate
  ) => Promise<TenantSettings>;
  clearSettingsCache: () => void;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  reminderSettings: null,
  tenantSettings: null,
  timezoneOptions: [],
  reminderSettingsLoaded: false,
  tenantSettingsLoaded: false,
  timezonesLoaded: false,
  reminderSettingsInFlight: null,
  tenantSettingsInFlight: null,
  timezonesInFlight: null,
  settingsLoadError: null,

  loadReminderSettings: async () => {
    const state = get();
    if (state.reminderSettingsLoaded) return state.reminderSettings;
    const promise = state.reminderSettingsInFlight || loadReminderSettings(set);
    if (!state.reminderSettingsInFlight) {
      set({ reminderSettingsInFlight: promise });
    }
    return promise;
  },

  loadTenantSettings: async () => {
    const state = get();
    if (state.tenantSettingsLoaded) return state.tenantSettings;
    const promise = state.tenantSettingsInFlight || loadTenantSettings(set);
    if (!state.tenantSettingsInFlight) {
      set({ tenantSettingsInFlight: promise });
    }
    return promise;
  },

  loadTimezoneOptions: async () => {
    const state = get();
    if (state.timezonesLoaded) return state.timezoneOptions;
    const promise = state.timezonesInFlight || loadTimezones(set);
    if (!state.timezonesInFlight) {
      set({ timezonesInFlight: promise });
    }
    return promise;
  },

  updateReminderSettings: async (payload) => {
    const data = await apiUpdateReminderSettings(payload);
    set({ reminderSettings: data, reminderSettingsLoaded: true });
    return data;
  },

  updateTenantSettings: async (payload) => {
    const data = await apiUpdateTenantSettings(payload);
    set({ tenantSettings: data, tenantSettingsLoaded: true });
    return data;
  },

  clearSettingsCache: () => {
    set({
      reminderSettings: null,
      tenantSettings: null,
      timezoneOptions: [],
      reminderSettingsLoaded: false,
      tenantSettingsLoaded: false,
      timezonesLoaded: false,
      reminderSettingsInFlight: null,
      tenantSettingsInFlight: null,
      timezonesInFlight: null,
      settingsLoadError: null,
    });
  },
}));

async function loadReminderSettings(
  set: (partial: Partial<SettingsState>) => void
): Promise<ReminderSettings | null> {
  try {
    const data = await getReminderSettings();
    set({
      reminderSettings: data,
      reminderSettingsLoaded: true,
      settingsLoadError: null,
      reminderSettingsInFlight: null,
    });
    return data;
  } catch (error: any) {
    const detail = error?.response?.data?.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg || "Unknown error").join("; ")
          : "Failed to load reminder settings";
    set({ settingsLoadError: msg, reminderSettingsInFlight: null });
    throw error;
  }
}

async function loadTenantSettings(
  set: (partial: Partial<SettingsState>) => void
): Promise<TenantSettings | null> {
  try {
    const data = await getTenantSettings();
    set({
      tenantSettings: data,
      tenantSettingsLoaded: true,
      settingsLoadError: null,
      tenantSettingsInFlight: null,
    });
    return data;
  } catch (error: any) {
    const detail = error?.response?.data?.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg || "Unknown error").join("; ")
          : "Failed to load tenant settings";
    set({ settingsLoadError: msg, tenantSettingsInFlight: null });
    throw error;
  }
}

async function loadTimezones(
  set: (partial: Partial<SettingsState>) => void
): Promise<TimezoneOption[]> {
  try {
    const data = await getTimezones();
    set({
      timezoneOptions: data,
      timezonesLoaded: true,
      timezonesInFlight: null,
    });
    return data;
  } catch (error) {
    console.warn("[settings] Failed to load timezone options:", error);
    set({
      timezoneOptions: [],
      timezonesLoaded: false,
      timezonesInFlight: null,
    });
    return [];
  }
}
```

- [x] **Step 5: Run frontend build to verify GREEN for API/store**

Run:

```bash
cd frontend && npm run build
```

Expected: FAIL for components still using the old store shape. This is acceptable at this point. Do not commit until Task 8 fixes components.

---

## Task 8: Frontend settings UI ownership move

**Required skills:** `vercel-react-best-practices`, `uncodixfy`, `superpowers:test-driven-development`.

**Files:**
- Modify: `frontend/src/features/admin/components/profile-section.tsx`
- Modify: `frontend/src/features/admin/components/reminder-settings-modal.tsx`
- Modify: `frontend/src/features/admin/components/settings-page.tsx`
- Modify: `frontend/src/store/settings.ts` if Task 7 build exposed missed types

- [x] **Step 1: Update ProfileSection imports and state**

In `frontend/src/features/admin/components/profile-section.tsx`, update imports:

```ts
import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { t, loadCatalog } from "@/i18n";
import { useSettingsStore } from "@/store/settings";
import {
  type Profile,
  type ProfileUpdate,
  updateProfile,
} from "../services/settings-api";
import { TimezonePicker } from "./timezone-picker";
```

Keep existing Button/Input/Label/Select imports.

Inside `ProfileSection`, add store selectors:

```ts
  const {
    tenantSettings,
    timezoneOptions,
    loadTenantSettings,
    loadTimezoneOptions,
    updateTenantSettings,
  } = useSettingsStore();
```

Add timezone state:

```ts
  const [timezone, setTimezone] = useState(profile.timezone || "UTC");
```

- [x] **Step 2: Load tenant settings/timezones from ProfileSection**

Add after state declarations:

```ts
  const loadSettings = useCallback(async () => {
    await Promise.all([loadTenantSettings(), loadTimezoneOptions()]);
  }, [loadTenantSettings, loadTimezoneOptions]);

  useEffect(() => {
    loadSettings().catch(() => {
      toast.error(t("frontend.profile.error_update"));
    });
  }, [loadSettings]);
```

Update the existing `useEffect` that syncs profile state:

```ts
  useEffect(() => {
    setFullName(profile.full_name || "");
    setEmail(profile.email || "");
    setPhone(profile.phone || "");
    setLocale(tenantSettings?.locale || profile.locale || "en");
    setTimezone(tenantSettings?.timezone || profile.timezone || "UTC");
  }, [profile, tenantSettings]);
```

- [x] **Step 3: Save identity and tenant settings through separate APIs**

Replace `handleSubmit` body with:

```ts
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const profilePayload: ProfileUpdate = {
        full_name: fullName || undefined,
        email: email || undefined,
        phone: phone || undefined,
      };
      const settingsPayload = {
        locale: locale || undefined,
        timezone: timezone || undefined,
      };
      const previousLocale = tenantSettings?.locale || profile.locale || "en";

      const [updatedProfile, updatedSettings] = await Promise.all([
        updateProfile(profilePayload),
        updateTenantSettings(settingsPayload),
      ]);

      onProfileUpdate({
        ...updatedProfile,
        locale: updatedSettings.locale,
        timezone: updatedSettings.timezone,
      });

      if (updatedSettings.locale !== previousLocale) {
        await loadCatalog();
      }

      toast.success(t("frontend.profile.saved"));
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.profile.error_update")
      );
    } finally {
      setSaving(false);
    }
  }
```

- [x] **Step 4: Render TimezonePicker in profile section**

In the second grid of `profile-section.tsx`, keep phone and language fields. Add a third field below that grid:

```tsx
      <div className="space-y-2">
        <Label>{t("frontend.subscriptions.timezone")}</Label>
        <TimezonePicker
          value={timezone}
          onChange={(value) => setTimezone(value ?? "")}
          timezones={timezoneOptions}
        />
      </div>
```

Do not add decorative cards, gradients, or hero text. Keep the existing simple form style.

- [x] **Step 5: Update ReminderSettingsModal store usage and local state**

In `frontend/src/features/admin/components/reminder-settings-modal.tsx`, remove:

```ts
import { TimezonePicker } from "./timezone-picker";
```

Change store destructuring to:

```ts
  const {
    reminderSettings,
    tenantSettings,
    reminderSettingsLoaded,
    loadReminderSettings,
    loadTenantSettings,
    updateReminderSettings,
  } = useSettingsStore();
```

Remove `timezone` from local `settings` state:

```ts
  const [settings, setSettings] = useState({
    reminders_enabled: false,
    warning_days: [7, 3, 1] as number[],
    reminder_time: "09:00",
    recipient_mode: "tenant_only" as "tenant_only" | "client_only" | "both",
    custom_message_tenant: null as string | null,
    custom_message_client: null as string | null,
  });
```

In `loadData`, replace `await loadTenantSettings();` with:

```ts
      await Promise.all([loadReminderSettings(), loadTenantSettings()]);
```

Update callback dependencies to include `loadReminderSettings` and `loadTenantSettings`.

Change sync effect condition:

```ts
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
```

- [x] **Step 6: Remove timezone validation and picker from reminder modal**

In `validate`, remove this block:

```ts
      if (!settings.timezone) {
        errors.timezone = t("frontend.subscriptions.error_timezone_required");
      }
```

Remove `hasTimezoneError` constant.

Remove the entire timezone picker JSX block between the first `<Separator />` and the warning-days section.

In its place, add a read-only note:

```tsx
                  <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
                    {t("frontend.subscriptions.reminder_time_help")} {tenantSettings?.timezone || "UTC"}
                  </div>
```

Do not send `timezone` in `updateReminderSettings(settings)` because `settings` no longer contains it.

- [x] **Step 7: Check SettingsPage does not need visual redesign**

Open `frontend/src/features/admin/components/settings-page.tsx`. No layout redesign is required. Only adjust imports/types if `Profile` now requires `timezone` and the build reports an error.

- [x] **Step 8: Run frontend verification**

Run:

```bash
cd frontend && npm run build
cd frontend && npm run lint
```

Expected: both PASS. If `npm run lint` reports pre-existing style issues unrelated to touched files, record them in the execution report and still fix all lint errors in touched files.

- [x] **Step 9: Commit frontend changes**

```bash
git add frontend/src/features/admin/services/settings-api.ts frontend/src/features/admin/services/reminder-api.ts frontend/src/store/settings.ts frontend/src/features/admin/components/profile-section.tsx frontend/src/features/admin/components/reminder-settings-modal.tsx frontend/src/features/admin/components/settings-page.tsx
git commit -m "refactor: move timezone UI to tenant settings"
```

---

## Task 9: Documentation updates [x]

**Required skills:** `stop-slop` if editing prose heavily, `superpowers:verification-before-completion`.

**Files:**
- Modify: `docs/architecture/database-schema.md`
- Modify: `docs/architecture/i18n-system.md`
- Modify: `docs/architecture/subscriptions.md`
- Modify: `docs/architecture/api-layer.md`
- Modify: `docs/architecture/frontend-architecture.md`
- Modify: `docs/SUMMARY.md` only if current entries become misleading

- [x] **Step 1: Update database schema docs**

In `docs/architecture/database-schema.md`:

- Add `TenantSettings` with columns `tenant_id`, `locale`, `timezone`, `created_at`, `updated_at`.
- Remove `Tenant.locale` from tenant fields.
- Remove `SubscriptionReminderSettings.timezone` from reminder settings fields.
- State that `tenant_settings.tenant_id` is the primary key and FK to `tenants.id`.

- [x] **Step 2: Update i18n docs**

In `docs/architecture/i18n-system.md`:

- Replace references to `Tenant.locale` with `TenantSettings.locale`.
- Document `/tenant-settings` as the write path for locale.
- Document `/me` as a read-only projection for tenant/client locale.
- Document WhatsApp tenant console locale resolution from tenant settings.

- [x] **Step 3: Update subscription docs**

In `docs/architecture/subscriptions.md`:

- State that reminder timezone comes from `tenant_settings.timezone`.
- Keep `reminder_time` documented as tenant-local time.
- Remove timezone from `/subscription-settings` request/response examples.
- Add `/tenant-settings/timezones` as the timezone catalog path.

- [x] **Step 4: Update API layer docs**

In `docs/architecture/api-layer.md`:

- Add endpoint group `/api/v1/tenant-settings` with GET, PUT, and `/timezones`.
- Update `/api/v1/me` docs: locale/timezone are projections, not write-owned fields.
- Update `/api/v1/subscription-settings` docs to omit timezone.

- [x] **Step 5: Update frontend architecture docs**

In `docs/architecture/frontend-architecture.md`:

- Correct settings area description to React/TSX + Zustand if it still says Vue/Pinia in touched sections.
- State that Profile section saves identity through `/me` and locale/timezone through `/tenant-settings`.
- State that reminder modal no longer owns timezone edits.

- [x] **Step 6: Verify docs contain no old owner claims**

Run:

```bash
rg -n "Tenant\.locale|tenants\.locale|subscription_reminder_settings\.timezone|/subscription-settings/timezones|PUT /api/v1/me.*locale|Vue|Pinia" docs
```

Expected: No stale ownership claims. Vue/Pinia may remain only if a doc intentionally describes old historical state; prefer updating stale current-architecture references.

- [x] **Step 7: Commit docs**

```bash
git add docs/architecture/database-schema.md docs/architecture/i18n-system.md docs/architecture/subscriptions.md docs/architecture/api-layer.md docs/architecture/frontend-architecture.md docs/SUMMARY.md
git commit -m "docs: document tenant settings ownership"
```

---

## Task 10: Full verification and cleanup

**Required skills:** `superpowers:verification-before-completion`, `requesting-code-review` before merge.

**Files:**
- Inspect all modified files.
- No new feature files unless prior tasks required them.

- [x] **Step 1: Check for forbidden stale code references**

Run:

```bash
rg -n "Tenant\.locale|tenant\.locale|getattr\(tenant, \"locale\"|SubscriptionReminderSettings\([^\n]*timezone|settings\.timezone|subscription-settings/timezones|locale\?: string|ProfileUpdate.*locale" backend frontend
```

Expected:

- No backend use of `Tenant.locale` or `tenant.locale`.
- No frontend call to `/subscription-settings/timezones`.
- No reminder settings API type has `timezone`.
- `settings.timezone` may appear only when the variable is tenant settings, not reminder settings. Inspect every hit.

- [x] **Step 2: Run backend tests**

Run:

```bash
cd backend && uv run pytest
```

Expected: PASS.

- [x] **Step 3: Run backend lint/format checks**

Run:

```bash
cd backend && uv run ruff check .
cd backend && uv run ruff format . --check
```

Expected: PASS. If `ruff format . --check` fails only because files need formatting, run `uv run ruff format .`, review diff, then rerun both commands.

- [x] **Step 4: Run frontend verification**

Run:

```bash
cd frontend && npm run build
cd frontend && npm run lint
```

Expected: PASS.

Do not run `npm test` unless a `test` script is added later. Current `frontend/package.json` has no `test` script.

- [x] **Step 5: Inspect git diff**

Run:

```bash
git diff --stat
git diff -- backend/app/models/tenant.py backend/app/models/subscription.py backend/app/api/v1/endpoints/me.py backend/app/services/subscription_job_service/reminder_payloads.py frontend/src/features/admin/components/profile-section.tsx frontend/src/features/admin/components/reminder-settings-modal.tsx
```

Expected:

- Changes are scoped to tenant settings ownership.
- No unrelated UI redesign.
- No n8n workflow changes.
- No broad cleanup outside touched files.

- [x] **Step 6: Request code review**

Use `superpowers:requesting-code-review` or a `code-reviewer` subagent. Ask the reviewer to check:

- migration safety and downgrade data preservation;
- RLS policy shape, especially inactive tenant SELECT and active-only tenant writes;
- no hidden async lazy loading reliance;
- `/me` locale/timezone read-only projection semantics;
- reminder timezone/locale behavior;
- frontend store/component ownership split.

- [x] **Step 7: Final commit if verification changed formatting/docs**

If Step 3 formatting or Step 6 review fixes changed files, commit them:

```bash
git add -A
git commit -m "chore: finalize tenant settings refactor"
```

If there are no changes, do not create an empty commit.

---

## Plan self-review

### Spec coverage

- New `tenant_settings` table/model/repository/service/API: Tasks 1-3.
- Data migration from `tenants.locale` and `subscription_reminder_settings.timezone`: Task 2.
- RLS policy coverage: Task 2.
- Remove old model fields: Tasks 1 and 5.
- `/tenant-settings` owns locale/timezone writes: Tasks 3-4.
- `/me` read-only projections: Task 4.
- Subscription settings API without timezone: Task 5.
- Reminder scheduling timezone/locale source: Task 6.
- Cleanup timezone boundary fix: Task 6.
- WhatsApp locale resolution/profile locale flow: Task 6.
- Frontend API/store/UI changes: Tasks 7-8.
- Docs and verification: Tasks 9-10.

### Placeholder scan

This plan intentionally avoids unfinished markers and vague placeholders. One test step references extracting `_create_subscription_fixture` only if the current test file lacks a reusable helper; the instruction includes the exact required behavior of that helper.

### Type/name consistency

- Backend model/schema/service consistently use `TenantSettings`, `TenantSettingsUpdate`, `TenantSettingsResponse`.
- Frontend types consistently use `TenantSettings`, `TenantSettingsUpdate`, `TimezoneOption` from `settings-api.ts`.
- Store names distinguish `reminderSettings` from `tenantSettings` and `timezoneOptions`.
