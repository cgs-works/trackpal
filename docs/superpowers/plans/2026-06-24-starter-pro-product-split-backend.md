# Starter/Pro Product Split Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the backend source of truth and enforcement for Starter vs Pro tenant packaging without deleting preserved Pro data.

**Architecture:** Keep one deep backend seam: `tenants.plan` is the source of truth, and FastAPI dependencies enforce plan access before endpoint code runs. Starter keeps code lookup, mailbox, code-service selection, locale, profile, dashboard, and access-control; Pro-only modules are blocked by a reusable Pro gate. Downgrade side effects live in `tenant_service`, where plan changes already happen.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy async, Alembic, Redis session service, pytest/httpx ASGITransport.

## Global Constraints

- Tenant plan lives directly on `tenants`, not in a separate entitlement table.
- Allowed plans: `starter`, `pro`.
- Existing tenants migrate to `pro`.
- New tenant creation requires an explicit plan.
- Tenant update preserves plan if omitted.
- Only Master can change tenant plan.
- Backend authorization must read plan from the database; frontend `tenant_plan` is only a UI hint.
- Tenant admin Starter access to Pro-only backend endpoints returns 404.
- Master switched into a Starter tenant bypasses plan gates.
- Client users under Starter fail auth with generic 401, but their data is preserved.
- Downgrade Pro → Starter preserves clients, catalog, subscriptions, history, and reminder settings.
- Downgrade Pro → Starter revokes client refresh sessions, keeps tenant admin access, clears WhatsApp admin Redis session, and attempts Evolution close best-effort.
- Subscription jobs/reminders/cleanup ignore Starter tenants entirely.
- Correo central de búsqueda must be `connected` for code lookup to start.
- Existing no-platform i18n messages should be reused.
- Internal names stay as-is where specified: `code_services`, `blocked_clients`, `BlockedClient`, etc.
- Duplicate active phone block returns 409.
- Blocking a phone immediately cancels active code lookup sessions and pending/processing lookup jobs for that identity.
- Blocked WhatsApp identities receive `no_reply`.

---

## File Structure

### Create
- `backend/alembic/versions/e011fe74cab1_add_tenant_plan.py` — adds `tenants.plan`, backfills `pro`, constrains allowed values.
- `backend/app/core/tenant_plan.py` — tiny plan constants/type helpers shared by schemas/dependencies/services.
- `backend/app/schemas/access_control.py` — public API schema for Control de acceso while persistence remains `BlockedClient`.
- `backend/app/services/access_control_service.py` — block/unblock/list plus immediate codigo-session/job cleanup.
- `backend/app/api/v1/endpoints/access_control.py` — `/access-control/blocks` REST API.
- `backend/tests/test_tenant_plan.py` — tenant plan create/update/auth/gate/downgrade behavior.
- `backend/tests/test_access_control_api.py` — HTTP tests for Control de acceso.

### Modify
- `backend/app/models/tenant.py` — `plan` column.
- `backend/app/schemas/tenant.py` — create/update/response plan fields.
- `backend/app/api/v1/endpoints/tenants.py` — include plan in responses.
- `backend/app/services/tenant_service/mutations.py` — persist plan and run downgrade effects.
- `backend/app/services/tenant_service/lifecycle.py` — no plan change here; keep active/deactivate behavior unchanged.
- `backend/app/repositories/tenants_repository.py` — plan helpers and optional counts.
- `backend/app/repositories/sessions_repository.py` — revoke all refresh sessions for client users in a tenant.
- `backend/app/repositories/mailbox_lookup_repository.py` — cancel active jobs for IDs found in Redis sessions.
- `backend/app/api/dependencies.py` — `ProTenantId`, `get_effective_tenant`, `get_tenant_plan`.
- `backend/app/schemas/auth.py` and `backend/app/services/auth_service/service.py` — `tenant_plan` in token responses and client auth blocked for Starter.
- `backend/app/api/v1/endpoints/clients.py` — Pro gate.
- `backend/app/api/v1/endpoints/catalog.py` — Pro gate.
- `backend/app/api/v1/endpoints/subscriptions/*.py` — Pro gate for tenant-facing routes; API-key jobs handled separately.
- `backend/app/api/v1/endpoints/tenant_settings.py` and `backend/app/schemas/tenant_settings.py` — Starter timezone read/mutation rules.
- `backend/app/services/dashboard_service/__init__.py` and `backend/app/schemas/dashboard.py` — Starter/Pro dashboard widgets and `tenant_plan`.
- `backend/app/api/v1/router.py` — include access-control router.
- `backend/app/services/whatsapp_tenant_console_service/constants.py` — menu keys/flow constants for Starter/Pro and Control de acceso.
- `backend/app/services/whatsapp_tenant_console_service/service.py` — plan-aware menu routing.
- `backend/app/services/whatsapp_tenant_console_service/clients_flow.py` — remove public “Bloqueos de mensajes” from Clients menu; move implementation behind access-control flow.
- `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py` — require mailbox status exactly `connected`.
- `backend/app/api/v1/endpoints/integrations/console.py` — Starter client routing, blocked check before all messages, plan passed to tenant console.
- `backend/app/api/v1/endpoints/integrations/console_handlers.py` — unauth codigo mailbox exact `connected`; block cleanup helper reuse.
- `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py` — use Control de acceso language and shared block cleanup after block creation.
- `backend/app/core/i18n/catalogs_en_wa.py`, `backend/app/core/i18n/catalogs_es_wa.py`, `backend/app/core/i18n/catalogs_en_frontend.py`, `backend/app/core/i18n/catalogs_es_frontend.py` — product labels and new messages.
- `backend/app/services/subscription_job_service/cleanup.py` — skip Starter subscriptions.
- `backend/app/services/subscription_job_service/reminder_schedule.py` — load tenant plan.
- `backend/app/services/subscription_job_service/reminder_payloads.py` — skip Starter tenants.
- `docs/architecture/api-layer.md`, `docs/architecture/database-schema.md`, `docs/architecture/whatsapp-console-flow.md`, `docs/architecture/subscriptions.md`, `docs/codebase/backend-structure.md` — sync docs after behavior changes.

---

### Task 1: Tenant plan schema, migration, and tenant CRUD contract

**Files:**
- Create: `backend/app/core/tenant_plan.py`
- Create: `backend/alembic/versions/e011fe74cab1_add_tenant_plan.py`
- Modify: `backend/app/models/tenant.py:5-48`
- Modify: `backend/app/schemas/tenant.py:1-118`
- Modify: `backend/app/api/v1/endpoints/tenants.py:19-30`
- Modify: `backend/app/services/tenant_service/mutations.py:33-157`
- Test: `backend/tests/test_tenant_plan.py`

**Interfaces:**
- Produces: `TenantPlan = Literal["starter", "pro"]`, `TENANT_PLAN_STARTER`, `TENANT_PLAN_PRO`, `VALID_TENANT_PLANS` from `app.core.tenant_plan`.
- Produces: `Tenant.plan: Mapped[str]` and API field `plan: "starter" | "pro"`.
- Consumes: existing `TenantService.create_tenant(db, payload)` and `TenantService.update_tenant(db, tenant_id, payload)`.

- [ ] **Step 1: Write failing tenant plan tests**

Add this file:

```python
# backend/tests/test_tenant_plan.py
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Tenant

pytestmark = pytest.mark.asyncio


async def _create_tenant(client, auth_headers, **overrides):
    payload = {
        "full_name": "Plan Tenant",
        "email": "plan@example.com",
        "phone": "+12015550100",
        "username": "plan_tenant",
        "password": "tenant-password",
        "evolution_instance_name": "plan-tenant-instance",
        "plan": "starter",
    }
    payload.update(overrides)
    return await client.post("/api/v1/tenants/", json=payload, headers=auth_headers)


async def test_create_tenant_requires_plan(client, auth_headers):
    response = await _create_tenant(client, auth_headers, plan=None)
    assert response.status_code == 422
    assert "plan" in response.text.lower()


async def test_create_tenant_accepts_starter_plan(client, auth_headers, db_session):
    response = await _create_tenant(client, auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["plan"] == "starter"

    row = await db_session.execute(select(Tenant).where(Tenant.id == body["id"]))
    tenant = row.scalar_one()
    assert tenant.plan == "starter"


async def test_update_tenant_preserves_plan_when_omitted(client, auth_headers):
    created = await _create_tenant(client, auth_headers, username="preserve_plan", phone="+12015550101", plan="pro")
    assert created.status_code == 201, created.text
    tenant_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/tenants/{tenant_id}",
        json={"full_name": "Renamed Tenant"},
        headers=auth_headers,
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["full_name"] == "Renamed Tenant"
    assert updated.json()["plan"] == "pro"


async def test_update_tenant_can_change_plan(client, auth_headers):
    created = await _create_tenant(client, auth_headers, username="change_plan", phone="+12015550102", plan="pro")
    assert created.status_code == 201, created.text

    updated = await client.put(
        f"/api/v1/tenants/{created.json()['id']}",
        json={"plan": "starter"},
        headers=auth_headers,
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["plan"] == "starter"


async def test_list_tenants_includes_plan(client, auth_headers, active_tenant_user):
    response = await client.get("/api/v1/tenants/", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"][0]["plan"] == "pro"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_plan.py -q
```

Expected: FAIL because `TenantCreate.plan`, `Tenant.plan`, and response `plan` do not exist yet.

- [ ] **Step 3: Add plan constants**

Create `backend/app/core/tenant_plan.py`:

```python
from __future__ import annotations

from typing import Final, Literal

TenantPlan = Literal["starter", "pro"]
TENANT_PLAN_STARTER: Final[TenantPlan] = "starter"
TENANT_PLAN_PRO: Final[TenantPlan] = "pro"
VALID_TENANT_PLANS: Final[tuple[TenantPlan, TenantPlan]] = (
    TENANT_PLAN_STARTER,
    TENANT_PLAN_PRO,
)


def normalize_tenant_plan(value: str) -> TenantPlan:
    normalized = value.strip().lower()
    if normalized not in VALID_TENANT_PLANS:
        raise ValueError("Plan must be one of: starter, pro")
    return normalized  # type: ignore[return-value]
```

- [ ] **Step 4: Add the migration**

Create `backend/alembic/versions/e011fe74cab1_add_tenant_plan.py`:

```python
"""add tenant plan

Revision ID: e011fe74cab1
Revises: d011fe74cab0
Create Date: 2026-06-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "e011fe74cab1"
down_revision: str | Sequence[str] | None = "d011fe74cab0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CHECK_NAME = "ck_tenants_plan_allowed"


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("plan", sa.String(length=20), server_default="pro", nullable=False),
    )
    op.execute("UPDATE tenants SET plan = 'pro' WHERE plan IS NULL")
    op.create_check_constraint(
        CHECK_NAME,
        "tenants",
        "plan IN ('starter', 'pro')",
    )


def downgrade() -> None:
    op.drop_constraint(CHECK_NAME, "tenants", type_="check")
    op.drop_column("tenants", "plan")
```

- [ ] **Step 5: Add model and schema fields**

In `backend/app/models/tenant.py`, add `plan` after `client_prefix`:

```python
    plan: Mapped[str] = mapped_column(String(20), default="pro", nullable=False)
```

In `backend/app/schemas/tenant.py`:

```python
from app.core.tenant_plan import TenantPlan, normalize_tenant_plan
```

Add to `TenantCreate`:

```python
    plan: TenantPlan
```

Add to `TenantUpdate`:

```python
    plan: TenantPlan | None = None
```

Add validators to both schema classes:

```python
    @field_validator("plan")
    @classmethod
    def validate_plan_field(cls, v: str) -> TenantPlan:
        return normalize_tenant_plan(v)
```

For `TenantUpdate`, use the nullable version:

```python
    @field_validator("plan")
    @classmethod
    def validate_plan_field(cls, v: str | None) -> TenantPlan | None:
        if v is None:
            return None
        return normalize_tenant_plan(v)
```

Add to `TenantResponse`:

```python
    plan: TenantPlan
```

- [ ] **Step 6: Persist and return plan**

In `backend/app/services/tenant_service/mutations.py`, add `plan=payload.plan` to `Tenant(...)` creation:

```python
    profile = Tenant(
        owner_user_id=user.id,
        client_prefix=client_prefix,
        plan=payload.plan,
        name=full_name,
        email=email,
        whatsapp_phone=phone,
        evolution_instance_name=payload.evolution_instance_name,
        is_active=True,
    )
```

Leave `update_data = payload.model_dump(exclude_unset=True)` unchanged; it already preserves omitted fields.

In `backend/app/api/v1/endpoints/tenants.py`, add `plan=profile.plan` to `_tenant_response()`:

```python
def _tenant_response(profile) -> TenantResponse:
    return TenantResponse(
        id=profile.id,
        full_name=profile.full_name,
        client_prefix=profile.client_prefix,
        plan=profile.plan,
        email=profile.email,
        phone=profile.phone,
        evolution_instance_name=profile.evolution_instance_name,
        is_active=profile.is_active,
        username=profile.owner.username,
        created_at=profile.created_at,
    )
```

- [ ] **Step 7: Keep fixtures backward-compatible**

No fixture needs explicit plan because `Tenant.plan` defaults to `pro`. If any fixture later asserts JSON shape, expect `"plan": "pro"` for pre-existing fixture tenants.

- [ ] **Step 8: Run tests**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_plan.py tests/test_tenants.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/tenant_plan.py backend/alembic/versions/e011fe74cab1_add_tenant_plan.py backend/app/models/tenant.py backend/app/schemas/tenant.py backend/app/api/v1/endpoints/tenants.py backend/app/services/tenant_service/mutations.py backend/tests/test_tenant_plan.py
git commit -m "feat: add tenant plan source of truth"
```

---

### Task 2: Auth responses, client auth block, and reusable Pro gate

**Files:**
- Modify: `backend/app/api/dependencies.py:1-157`
- Modify: `backend/app/schemas/auth.py:13-29`
- Modify: `backend/app/services/auth_service/service.py:35-147`
- Modify: `backend/app/api/v1/endpoints/clients.py:1-168`
- Modify: `backend/app/api/v1/endpoints/catalog.py:1-264`
- Modify: `backend/app/api/v1/endpoints/subscriptions/crud.py:1-169`
- Modify: `backend/app/api/v1/endpoints/subscriptions/lifecycle.py:1-149`
- Modify: `backend/app/api/v1/endpoints/subscriptions/settings.py:1-47`
- Test: `backend/tests/test_tenant_plan.py`

**Interfaces:**
- Produces: `TenantPlanDep = Annotated[str | None, Depends(get_current_tenant_plan)]`.
- Produces: `ProTenantId = Annotated[UUID, Depends(get_pro_tenant_id)]`.
- Produces: `TokenResponse.tenant_plan: TenantPlan | None`.
- Consumes: `Tenant.plan` from Task 1.

- [ ] **Step 1: Add failing auth and Pro gate tests**

Append to `backend/tests/test_tenant_plan.py`:

```python
from app.core.security import get_password_hash
from app.models import Client, TenantSettings, User


async def _login(client, username: str, password: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_auth_responses_include_tenant_plan(client, auth_headers, active_tenant_user):
    tenant_login = await _login(client, "tenant", "tenant-password")
    assert tenant_login["tenant_plan"] == "pro"

    master_login = await _login(client, "master", "master-password")
    assert master_login["tenant_plan"] is None

    switch = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": tenant_login["active_tenant_id"]},
        headers={"Authorization": f"Bearer {master_login['access_token']}"},
    )
    assert switch.status_code == 200, switch.text
    assert switch.json()["tenant_plan"] == "pro"


async def test_starter_tenant_gets_404_for_pro_endpoints(client, auth_headers, active_tenant_user):
    tenant = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert tenant.status_code == 200, tenant.text

    login = await _login(client, "tenant", "tenant-password")
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    for path in ("/api/v1/clients", "/api/v1/catalog/services", "/api/v1/subscriptions", "/api/v1/subscription-settings"):
        response = await client.get(path, headers=headers)
        assert response.status_code == 404, path + response.text


async def test_master_switched_into_starter_bypasses_pro_gate(client, auth_headers, active_tenant_user):
    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    switched = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": response.json()["id"]},
        headers=auth_headers,
    )
    assert switched.status_code == 200, switched.text
    headers = {"Authorization": f"Bearer {switched.json()['access_token']}"}

    pro_endpoint = await client.get("/api/v1/clients", headers=headers)
    assert pro_endpoint.status_code == 200, pro_endpoint.text


async def test_client_login_under_starter_returns_generic_401(client, db_session, auth_headers, active_tenant_user):
    result = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = result.scalar_one()
    client_user = User(
        username=f"{tenant.client_prefix}_starter_client",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(client_user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="Starter Client",
            username=client_user.username,
            phone="12015550199",
            is_active=True,
        )
    )
    await db_session.commit()

    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": client_user.username, "password": "client-password"},
    )
    assert login.status_code == 401
    assert login.json()["detail"] == "Invalid credentials or account deactivated"
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py -q
```

Expected: FAIL because `tenant_plan` and `ProTenantId` do not exist.

- [ ] **Step 3: Add dependency helpers**

In `backend/app/api/dependencies.py`, import plan constants and add helpers above aliases:

```python
from app.core.tenant_plan import TENANT_PLAN_PRO, TenantPlan
```

Add:

```python
async def get_current_tenant_plan(
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantPlan | None:
    payload = decode_token(token)
    if current_user.role == "tenant":
        tenant = await tenants_repository.get_active_by_owner(db, current_user.id)
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is deactivated")
        return tenant.plan  # type: ignore[return-value]
    if current_user.role == "master":
        raw = payload.get("active_tenant_id")
        if not raw:
            return None
        try:
            tenant_id = UUID(raw)
        except (ValueError, TypeError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid tenant context") from None
        tenant = await tenants_repository.get_active(db, tenant_id)
        return tenant.plan if tenant else None  # type: ignore[return-value]
    return None


async def get_pro_tenant_id(
    tenant_id: Annotated[UUID, Depends(get_active_tenant_id)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UUID:
    if current_user.role == "master":
        return tenant_id
    tenant = await tenants_repository.get_active(db, tenant_id)
    if tenant is None or tenant.plan != TENANT_PLAN_PRO:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return tenant_id
```

Update aliases:

```python
TenantPlanDep = Annotated[TenantPlan | None, Depends(get_current_tenant_plan)]
ProTenantId = Annotated[UUID, Depends(get_pro_tenant_id)]
```

- [ ] **Step 4: Add `tenant_plan` to token response**

In `backend/app/schemas/auth.py`:

```python
from app.core.tenant_plan import TenantPlan
```

Add to `TokenResponse`:

```python
    tenant_plan: TenantPlan | None = None
```

In `backend/app/services/auth_service/service.py`, add a private helper inside `AuthService`:

```python
    async def _tenant_plan_for_user(
        self, db: AsyncSession, user: User, active_tenant_id: UUID | None
    ) -> str | None:
        if user.role == "tenant":
            await set_internal_rls_context(db)
            tenant = await tenants_repository.get_active_by_owner(db, user.id)
            return tenant.plan if tenant else None
        if user.role == "master" and active_tenant_id is not None:
            await set_internal_rls_context(db)
            tenant = await tenants_repository.get_active(db, active_tenant_id)
            return tenant.plan if tenant else None
        if user.role == "client" and active_tenant_id is not None:
            await set_internal_rls_context(db)
            tenant = await tenants_repository.get_active(db, active_tenant_id)
            return tenant.plan if tenant else None
        return None
```

In `create_tokens()`, compute before return:

```python
        tenant_plan = await self._tenant_plan_for_user(db, user, active_tenant_id)
```

Add to returned dict:

```python
            "tenant_plan": tenant_plan,
```

- [ ] **Step 5: Block client auth under Starter**

In `AuthService._active_tenant_id_for_user()`, replace the client branch return:

```python
        if user.role != "client":
            return None
        await set_internal_rls_context(db)
        row = await clients_repository.get_active_client_tenant_join(db, user.id)
        if not row:
            return None
        tenant = row[0].tenant
        if tenant.plan != "pro":
            return None
        return row[0].tenant_id
```

If `row[0].tenant` is not eagerly loaded in this repository function, update `clients_repository.get_active_client_tenant_join()` to select/load `Client.tenant`. Verify by running the tests in this task.

- [ ] **Step 6: Apply Pro gate to endpoint modules**

In `backend/app/api/v1/endpoints/clients.py`, import `ProTenantId` and change every `tenant_id: ActiveTenantId` to `tenant_id: ProTenantId`.

In `backend/app/api/v1/endpoints/catalog.py`, import `ProTenantId` and change every `tenant_id: ActiveTenantId` to `tenant_id: ProTenantId`.

In `backend/app/api/v1/endpoints/subscriptions/crud.py`, `lifecycle.py`, and `settings.py`, import `ProTenantId` and change every tenant-facing `tenant_id: ActiveTenantId` to `tenant_id: ProTenantId`.

Keep API-key routes in `subscriptions/jobs.py` unchanged; Task 8 handles job-level Starter skipping.

- [ ] **Step 7: Run tests**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py tests/test_auth.py tests/test_clients.py tests/test_catalog.py tests/test_subscriptions.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/dependencies.py backend/app/schemas/auth.py backend/app/services/auth_service/service.py backend/app/api/v1/endpoints/clients.py backend/app/api/v1/endpoints/catalog.py backend/app/api/v1/endpoints/subscriptions/crud.py backend/app/api/v1/endpoints/subscriptions/lifecycle.py backend/app/api/v1/endpoints/subscriptions/settings.py backend/tests/test_tenant_plan.py
git commit -m "feat: enforce pro tenant gates"
```

---

### Task 3: Tenant settings Starter timezone behavior

**Files:**
- Modify: `backend/app/api/v1/endpoints/tenant_settings.py:1-45`
- Modify: `backend/app/schemas/tenant_settings.py:10-24`
- Test: `backend/tests/test_tenant_plan.py`

**Interfaces:**
- Consumes: `TenantPlanDep` from Task 2.
- Produces: `GET /tenant-settings` returns `timezone: null` for tenant-admin Starter; Master-switched bypass still sees real timezone.
- Produces: `PUT /tenant-settings` with `timezone` by tenant-admin Starter returns 404.

- [ ] **Step 1: Add failing tests**

Append:

```python
async def test_starter_tenant_settings_hides_and_blocks_timezone(client, auth_headers, active_tenant_user):
    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text
    login = await _login(client, "tenant", "tenant-password")
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    read = await client.get("/api/v1/tenant-settings", headers=headers)
    assert read.status_code == 200, read.text
    assert read.json()["locale"] in {"en", "es"}
    assert read.json()["timezone"] is None

    locale_update = await client.put("/api/v1/tenant-settings", json={"locale": "es"}, headers=headers)
    assert locale_update.status_code == 200, locale_update.text
    assert locale_update.json()["locale"] == "es"
    assert locale_update.json()["timezone"] is None

    timezone_update = await client.put("/api/v1/tenant-settings", json={"timezone": "America/Bogota"}, headers=headers)
    assert timezone_update.status_code == 404


async def test_master_switched_starter_can_see_timezone(client, auth_headers, active_tenant_user):
    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text
    switched = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": changed.json()["id"]},
        headers=auth_headers,
    )
    headers = {"Authorization": f"Bearer {switched.json()['access_token']}"}

    response = await client.get("/api/v1/tenant-settings", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["timezone"] == "UTC"
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py::test_starter_tenant_settings_hides_and_blocks_timezone tests/test_tenant_plan.py::test_master_switched_starter_can_see_timezone -q
```

Expected: FAIL because timezone is still visible/mutable.

- [ ] **Step 3: Allow nullable timezone in response**

In `backend/app/schemas/tenant_settings.py`:

```python
    timezone: str | None
```

- [ ] **Step 4: Implement endpoint rule**

In `backend/app/api/v1/endpoints/tenant_settings.py`, import `TenantPlanDep`:

```python
from app.api.dependencies import ActiveTenantId, CurrentUser, DbDep, TenantPlanDep
```

Change GET signature and body:

```python
@router.get("", response_model=TenantSettingsResponse)
async def get_tenant_settings(
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
    tenant_plan: TenantPlanDep,
):
    require_tenant_or_master(current_user)
    settings = await service.get_settings(db, tenant_id)
    if current_user.role == "tenant" and tenant_plan == "starter":
        settings.timezone = None
    return settings
```

Change PUT signature and body:

```python
@router.put("", response_model=TenantSettingsResponse)
async def update_tenant_settings(
    payload: TenantSettingsUpdate,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
    tenant_plan: TenantPlanDep,
):
    require_tenant_or_master(current_user)
    if current_user.role == "tenant" and tenant_plan == "starter" and payload.timezone is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        settings = await service.update_settings(db, tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if current_user.role == "tenant" and tenant_plan == "starter":
        settings.timezone = None
    return settings
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py tests/test_profile.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/endpoints/tenant_settings.py backend/app/schemas/tenant_settings.py backend/tests/test_tenant_plan.py
git commit -m "feat: hide starter timezone settings"
```

---

### Task 4: Downgrade side effects

**Files:**
- Modify: `backend/app/services/tenant_service/mutations.py:107-157`
- Modify: `backend/app/repositories/sessions_repository.py:1-51`
- Modify: `backend/app/services/evolution_client/client.py:190-200`
- Test: `backend/tests/test_tenant_plan.py`

**Interfaces:**
- Consumes: `Tenant.plan` and `TenantUpdate.plan`.
- Produces: `sessions_repository.revoke_all_for_tenant_clients(db, tenant_id: UUID) -> None`.
- Produces: `TenantService.update_tenant()` side effect only when current plan is `pro` and new plan is `starter`.

- [ ] **Step 1: Add failing downgrade test**

Append:

```python
from unittest.mock import AsyncMock, patch

from app.models import RefreshSession
from app.core.security import create_refresh_token


async def test_downgrade_revokes_client_sessions_and_keeps_tenant_login(client, auth_headers, db_session, active_tenant_user):
    result = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = result.scalar_one()
    client_user = User(
        username=f"{tenant.client_prefix}_downgrade_client",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(client_user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="Downgrade Client",
            username=client_user.username,
            phone="12015550201",
            is_active=True,
        )
    )
    db_session.add(
        RefreshSession(
            user_id=client_user.id,
            refresh_token_hash="hash",
            expires_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(year=2099),
            revoked=False,
        )
    )
    await db_session.commit()

    fake_manager = AsyncMock()
    with patch("app.services.tenant_service.mutations.get_redis_manager", return_value=fake_manager), patch(
        "app.services.tenant_service.mutations.evolution_client.close_chat_session", new=AsyncMock()
    ) as close_chat:
        response = await client.put(
            f"/api/v1/tenants/{active_tenant_user.id}",
            json={"plan": "starter"},
            headers=auth_headers,
        )

    assert response.status_code == 200, response.text
    assert response.json()["plan"] == "starter"

    session_row = await db_session.execute(select(RefreshSession).where(RefreshSession.user_id == client_user.id))
    assert session_row.scalar_one().revoked is True
    fake_manager.execute.assert_awaited()
    close_chat.assert_awaited()

    tenant_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    assert tenant_login.status_code == 200
    assert tenant_login.json()["tenant_plan"] == "starter"
```

- [ ] **Step 2: Run failing test**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py::test_downgrade_revokes_client_sessions_and_keeps_tenant_login -q
```

Expected: FAIL because downgrade side effects do not exist.

- [ ] **Step 3: Add refresh-session repository helper**

In `backend/app/repositories/sessions_repository.py`, import `Client`:

```python
from app.models import Client, RefreshSession
```

Add:

```python
async def revoke_all_for_tenant_clients(db: AsyncSession, tenant_id: UUID) -> None:
    result = await db.execute(select(Client.owner_user_id).where(Client.tenant_id == tenant_id))
    user_ids = [row[0] for row in result.all()]
    if not user_ids:
        return
    await db.execute(
        update(RefreshSession)
        .where(
            RefreshSession.user_id.in_(user_ids),
            RefreshSession.revoked == False,  # noqa: E712
        )
        .values(revoked=True)
    )
```

Add it to `__all__`.

- [ ] **Step 4: Add downgrade helper in tenant mutations**

In `backend/app/services/tenant_service/mutations.py`, add imports:

```python
import logging
from app.core.redis_client import get_redis_manager
```

Add module logger:

```python
logger = logging.getLogger(__name__)
```

Add helper above `update_tenant()`:

```python
async def _run_pro_to_starter_downgrade_effects(db: AsyncSession, profile: Tenant) -> None:
    await sessions_repository.revoke_all_for_tenant_clients(db, profile.id)

    phone = validate_phone(profile.whatsapp_phone) if profile.whatsapp_phone else None
    manager = get_redis_manager()
    if manager is not None and phone:
        async def _delete_admin_session(client):
            await client.delete(f"session:admin:{phone}")

        try:
            await manager.execute("clear_admin_session_on_downgrade", _delete_admin_session)
        except Exception:
            logger.warning("Failed to clear admin WhatsApp session during downgrade tenant=%s", profile.id, exc_info=True)

    if profile.evolution_instance_name and phone:
        try:
            await evolution_client.close_chat_session(
                instance=profile.evolution_instance_name,
                remote_jid=f"{phone}@s.whatsapp.net",
            )
        except Exception:
            logger.warning("Failed to close Evolution session during downgrade tenant=%s", profile.id, exc_info=True)
```

Update the import from repositories:

```python
from app.repositories import clients_repository, sessions_repository, tenants_repository, users_repository
```

In `update_tenant()`, before the `for field, value in update_data.items():` loop:

```python
    old_plan = profile.plan
    new_plan = update_data.get("plan", old_plan)
```

After the loop and before commit:

```python
    if old_plan == "pro" and new_plan == "starter":
        await _run_pro_to_starter_downgrade_effects(db, profile)
```

- [ ] **Step 5: Keep Evolution close best-effort**

`backend/app/services/evolution_client/client.py` currently has `close_chat_session()` as a logged no-op. Keep it as no-op for this issue because n8n owns actual closing; the requirement is “attempt best-effort and do not fail plan change.” The call in tenant service is the attempt seam, and the warning is enough if it fails.

- [ ] **Step 6: Run tests**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/tenant_service/mutations.py backend/app/repositories/sessions_repository.py backend/tests/test_tenant_plan.py
git commit -m "feat: apply starter downgrade side effects"
```

---

### Task 5: Dashboard payload for Starter, Pro, and stale-plan correction

**Files:**
- Modify: `backend/app/schemas/dashboard.py:1-41`
- Modify: `backend/app/services/dashboard_service/__init__.py:1-69`
- Test: `backend/tests/test_tenant_plan.py`

**Interfaces:**
- Produces: `TenantDashboardResponse.tenant_plan`.
- Produces common fields: `mailbox_status`, `enabled_code_services`, `access_control_count`.
- Produces Pro fields nullable for Starter: `active_clients`, `catalog_services`, `active_subscriptions`, `subscriptions_expiring_soon`.

- [ ] **Step 1: Add failing dashboard tests**

Append:

```python
async def test_dashboard_returns_starter_common_widgets(client, auth_headers, active_tenant_user):
    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text
    login = await _login(client, "tenant", "tenant-password")
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    response = await client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_plan"] == "starter"
    assert body["mailbox_status"] in {"missing", "disconnected", "connected", "error", "revoked"}
    assert body["enabled_code_services"] == []
    assert body["access_control_count"] == 0
    assert body["active_clients"] is None
    assert body["catalog_services"] is None
    assert body["active_subscriptions"] is None
    assert body["subscriptions_expiring_soon"] is None


async def test_dashboard_returns_pro_metrics(client, active_tenant_user):
    login = await _login(client, "tenant", "tenant-password")
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    response = await client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_plan"] == "pro"
    assert isinstance(body["active_clients"], int)
    assert isinstance(body["catalog_services"], int)
    assert isinstance(body["active_subscriptions"], int)
    assert isinstance(body["subscriptions_expiring_soon"], int)
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py::test_dashboard_returns_starter_common_widgets tests/test_tenant_plan.py::test_dashboard_returns_pro_metrics -q
```

Expected: FAIL because dashboard schema lacks fields.

- [ ] **Step 3: Extend schema**

In `backend/app/schemas/dashboard.py`, replace `TenantDashboardResponse` with:

```python
class TenantDashboardResponse(BaseModel):
    message: str = "Dashboard en construccion"
    full_name: str
    email: str | None
    tenant_plan: str
    mailbox_status: str
    enabled_code_services: list[str] = Field(default_factory=list)
    access_control_count: int = 0
    active_clients: int | None = None
    catalog_services: int | None = None
    active_subscriptions: int | None = None
    subscriptions_expiring_soon: int | None = None
```

- [ ] **Step 4: Implement dashboard queries**

In `backend/app/services/dashboard_service/__init__.py`, add imports:

```python
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func, select
from app.models import BlockedClient, Client, Service, Subscription, TenantMailbox, TenantSettings
from app.repositories import code_services_repository
```

Add helpers inside `DashboardService`:

```python
    async def _tenant_dashboard(self, db, profile) -> TenantDashboardResponse:
        tenant_id = profile.id
        mailbox_status = await self._mailbox_status(db, tenant_id)
        enabled = await code_services_repository.get_effective_service_keys(db, tenant_id)
        access_count = await self._access_control_count(db, tenant_id)
        payload = TenantDashboardResponse(
            full_name=profile.full_name,
            email=profile.email,
            tenant_plan=profile.plan,
            mailbox_status=mailbox_status,
            enabled_code_services=enabled,
            access_control_count=access_count,
        )
        if profile.plan == "pro":
            payload.active_clients = await self._count(db, Client, tenant_id, Client.is_active.is_(True))
            payload.catalog_services = await self._count(db, Service, tenant_id)
            payload.active_subscriptions = await self._count(db, Subscription, tenant_id, Subscription.status == "active")
            payload.subscriptions_expiring_soon = await self._subscriptions_expiring_soon(db, tenant_id)
        return payload

    async def _mailbox_status(self, db, tenant_id) -> str:
        row = await db.execute(select(TenantMailbox.status).where(TenantMailbox.tenant_id == tenant_id))
        return row.scalar_one_or_none() or "missing"

    async def _access_control_count(self, db, tenant_id) -> int:
        row = await db.execute(
            select(func.count()).select_from(BlockedClient).where(BlockedClient.tenant_id == tenant_id, BlockedClient.is_active)
        )
        return int(row.scalar_one())

    async def _count(self, db, model, tenant_id, *conditions) -> int:
        stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
        for condition in conditions:
            stmt = stmt.where(condition)
        row = await db.execute(stmt)
        return int(row.scalar_one())

    async def _subscriptions_expiring_soon(self, db, tenant_id) -> int:
        settings_row = await db.execute(select(TenantSettings.timezone).where(TenantSettings.tenant_id == tenant_id))
        tz_name = settings_row.scalar_one_or_none() or "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except (KeyError, TypeError, ValueError):
            tz = ZoneInfo("UTC")
        local_today = datetime.now(timezone.utc).astimezone(tz).date()
        start_utc = datetime.combine(local_today, time.min, tzinfo=tz).astimezone(timezone.utc)
        end_utc = datetime.combine(local_today + timedelta(days=7), time.max, tzinfo=tz).astimezone(timezone.utc)
        row = await db.execute(
            select(func.count())
            .select_from(Subscription)
            .where(
                Subscription.tenant_id == tenant_id,
                Subscription.status == "active",
                Subscription.expires_at >= start_utc,
                Subscription.expires_at <= end_utc,
            )
        )
        return int(row.scalar_one())
```

Change `get_dashboard()` tenant branch from:

```python
        return TenantDashboardResponse(full_name=profile.full_name, email=profile.email)
```

To:

```python
        return await self._tenant_dashboard(db, profile)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py tests/test_subscriptions.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/dashboard.py backend/app/services/dashboard_service/__init__.py backend/tests/test_tenant_plan.py
git commit -m "feat: return plan-aware tenant dashboard"
```

---

### Task 6: Control de acceso REST API and immediate code-lookup cleanup

**Files:**
- Create: `backend/app/schemas/access_control.py`
- Create: `backend/app/services/access_control_service.py`
- Create: `backend/app/api/v1/endpoints/access_control.py`
- Modify: `backend/app/api/v1/router.py:3-34`
- Modify: `backend/app/repositories/mailbox_lookup_repository.py:1-185`
- Test: `backend/tests/test_access_control_api.py`

**Interfaces:**
- Produces: `GET /api/v1/access-control/blocks`.
- Produces: `POST /api/v1/access-control/blocks` with body `{ "phone": "+12015550222" }`.
- Produces: `DELETE /api/v1/access-control/blocks/{block_id}`.
- Produces: duplicate active phone block returns 409.

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_access_control_api.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import BlockedClient, MailLookupJob, Tenant, TenantMailbox
from app.services.whatsapp_session_service import ConversationSession

pytestmark = pytest.mark.asyncio


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, keepttl: bool = False) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> int:
        return 1 if self.store.pop(key, None) is not None else 0


class _FakeManager:
    def __init__(self, redis: _FakeRedis) -> None:
        self.redis = redis

    async def execute(self, operation_name: str, async_callable):
        return await async_callable(self.redis)


async def _tenant_headers(client):
    login = await client.post("/api/v1/auth/login", json={"username": "tenant", "password": "tenant-password"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _tenant(db_session, active_tenant_user):
    row = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    return row.scalar_one()


async def test_access_control_list_block_duplicate_and_unblock(client, db_session, active_tenant_user):
    headers = await _tenant_headers(client)

    created = await client.post("/api/v1/access-control/blocks", json={"phone": "+12015550222"}, headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["phone"] == "12015550222"
    assert body["is_active"] is True

    duplicate = await client.post("/api/v1/access-control/blocks", json={"phone": "+12015550222"}, headers=headers)
    assert duplicate.status_code == 409

    listed = await client.get("/api/v1/access-control/blocks", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [row["phone"] for row in listed.json()] == ["12015550222"]

    deleted = await client.delete(f"/api/v1/access-control/blocks/{body['id']}", headers=headers)
    assert deleted.status_code == 204

    listed_again = await client.get("/api/v1/access-control/blocks", headers=headers)
    assert listed_again.status_code == 200
    assert listed_again.json() == []


async def test_block_phone_cancels_active_codigo_session_and_job(client, db_session, active_tenant_user, monkeypatch):
    from app.services import access_control_service

    tenant = await _tenant(db_session, active_tenant_user)
    mailbox = TenantMailbox(tenant_id=tenant.id, mailbox_email="codes@example.com", provider="google", auth_method="oauth", status="connected")
    db_session.add(mailbox)
    await db_session.flush()
    job = MailLookupJob(
        tenant_id=tenant.id,
        mailbox_id=mailbox.id,
        service_key="netflix",
        target_email="viewer@example.com",
        status="pending",
        expires_at=datetime.now(timezone.utc).replace(year=2099),
    )
    db_session.add(job)
    await db_session.commit()

    redis = _FakeRedis()
    session_key = f"session:unreg:{str(tenant.id)[:8]}:12015550223"
    redis.store[session_key] = ConversationSession(
        phone=f"unreg:{str(tenant.id)[:8]}:12015550223",
        flow="codigo",
        step="awaiting_result",
        temp_data={"lookup_job_id": str(job.id)},
    ).model_dump_json()
    monkeypatch.setattr(access_control_service, "get_redis_manager", lambda: _FakeManager(redis))

    headers = await _tenant_headers(client)
    created = await client.post("/api/v1/access-control/blocks", json={"phone": "+12015550223"}, headers=headers)
    assert created.status_code == 201, created.text

    assert session_key not in redis.store
    refreshed = await db_session.get(MailLookupJob, job.id)
    assert refreshed.status == "failed"
    assert refreshed.error_code == "user_cancelled"
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && uv run pytest tests/test_access_control_api.py -q
```

Expected: FAIL because the route does not exist.

- [ ] **Step 3: Create schemas**

Create `backend/app/schemas/access_control.py`:

```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.input_validation import validate_phone


class AccessControlBlockCreate(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone_field(cls, value: str) -> str:
        normalized = validate_phone(value)
        if normalized is None:
            raise ValueError("Phone is required")
        return normalized


class AccessControlBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    phone: str | None
    whatsapp_lid: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Create service**

Create `backend/app/services/access_control_service.py`:

```python
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis_manager
from app.repositories import blocked_clients_repository, mailbox_lookup_repository
from app.services.whatsapp_session_service import WhatsAppSessionService

logger = logging.getLogger(__name__)


class DuplicateAccessBlockError(ValueError):
    pass


class AccessControlService:
    async def list_blocks(self, db: AsyncSession, tenant_id: UUID):
        return await blocked_clients_repository.list_active(db, tenant_id)

    async def block_phone(self, db: AsyncSession, tenant_id: UUID, phone: str):
        existing = await blocked_clients_repository.find_active(db, tenant_id, phone=phone)
        if existing is not None:
            raise DuplicateAccessBlockError("Phone is already blocked")
        block = await blocked_clients_repository.create(db, tenant_id, phone=phone)
        await self._cancel_codigo_for_phone(db, tenant_id, phone)
        await db.commit()
        await db.refresh(block)
        return block

    async def unblock(self, db: AsyncSession, tenant_id: UUID, block_id: UUID):
        block = await blocked_clients_repository.unblock(db, tenant_id, block_id)
        if block is None:
            return None
        await db.commit()
        return block

    async def _cancel_codigo_for_phone(self, db: AsyncSession, tenant_id: UUID, phone: str) -> None:
        manager = get_redis_manager()
        if manager is None:
            return
        session_service = WhatsAppSessionService(manager)
        logical_keys = [
            f"unreg:{str(tenant_id)[:8]}:{phone}",
            f"admin:{phone}",
        ]
        for logical_key in logical_keys:
            try:
                session = await session_service.get_session(logical_key)
                if session and session.flow == "codigo":
                    lookup_job_id = (session.temp_data or {}).get("lookup_job_id")
                    if lookup_job_id:
                        try:
                            await mailbox_lookup_repository.cancel_active_job_if_present(
                                db,
                                UUID(lookup_job_id),
                                tenant_id=tenant_id,
                            )
                        except ValueError:
                            logger.warning("Invalid lookup job id while blocking phone: %s", lookup_job_id)
                    await session_service.clear_session(logical_key)
            except Exception:
                logger.warning("Failed to clear codigo session for blocked phone tenant=%s phone=%s", tenant_id, phone, exc_info=True)
```

- [ ] **Step 5: Create endpoint**

Create `backend/app/api/v1/endpoints/access_control.py`:

```python
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import ActiveTenantId, DbDep
from app.schemas.access_control import AccessControlBlockCreate, AccessControlBlockResponse
from app.services.access_control_service import AccessControlService, DuplicateAccessBlockError

router = APIRouter(prefix="/access-control", tags=["access-control"])
service = AccessControlService()


@router.get("/blocks", response_model=list[AccessControlBlockResponse])
async def list_blocks(db: DbDep, tenant_id: ActiveTenantId):
    return await service.list_blocks(db, tenant_id)


@router.post("/blocks", response_model=AccessControlBlockResponse, status_code=status.HTTP_201_CREATED)
async def create_block(payload: AccessControlBlockCreate, db: DbDep, tenant_id: ActiveTenantId):
    try:
        return await service.block_phone(db, tenant_id, payload.phone)
    except DuplicateAccessBlockError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(block_id: UUID, db: DbDep, tenant_id: ActiveTenantId):
    block = await service.unblock(db, tenant_id, block_id)
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

In `backend/app/api/v1/router.py`, add `access_control` to imports and include it after `tenant_settings`:

```python
from app.api.v1.endpoints import access_control, auth, catalog, clients, code_services, dashboard, i18n, integrations, mailbox, me, tenants, tenant_settings, subscriptions
```

```python
api_router.include_router(access_control.router)
```

- [ ] **Step 6: Run tests**

```bash
cd backend && uv run pytest tests/test_access_control_api.py tests/test_code_services.py tests/test_mailbox_lookup_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/access_control.py backend/app/services/access_control_service.py backend/app/api/v1/endpoints/access_control.py backend/app/api/v1/router.py backend/tests/test_access_control_api.py
git commit -m "feat: add access control block API"
```

---

### Task 7: WhatsApp Starter/Pro menus, mailbox gate, and silent blocks

**Files:**
- Modify: `backend/app/services/whatsapp_tenant_console_service/constants.py:7-235`
- Modify: `backend/app/services/whatsapp_tenant_console_service/service.py:182-383`
- Modify: `backend/app/services/whatsapp_tenant_console_service/clients_flow.py:12-219`
- Modify: `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py:85-135`
- Modify: `backend/app/api/v1/endpoints/integrations/console.py:239-414`
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py:529-921`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`, `backend/app/core/i18n/catalogs_es_wa.py`
- Test: `backend/tests/test_tenant_plan.py`
- Test: `backend/tests/test_whatsapp_endpoint.py`
- Test: `backend/tests/test_tenant_console_service.py`

**Interfaces:**
- Consumes: `tenant.plan` from routing.
- Produces Starter tenant menu: Profile, Buscar código de acceso, Control de acceso, Help, Exit.
- Produces Pro tenant menu: Clients, Catalog, Profile, Subscriptions, Control de acceso, Help, Buscar código de acceso, Exit.
- Produces mailbox gate requiring `connected` only.

- [ ] **Step 1: Add focused WhatsApp tests**

Append to `backend/tests/test_tenant_plan.py`:

```python
async def test_whatsapp_starter_menu_is_reduced(client, auth_headers, active_tenant_user):
    from app.core.config import settings
    from unittest.mock import patch
    from backend.tests.test_whatsapp_endpoint import _FakeManager

    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text

    fake_mgr = _FakeManager()
    with patch("app.api.v1.endpoints.integrations.console.get_redis_manager", return_value=fake_mgr):
        response = await client.post(
            "/api/v1/integrations/n8n/console",
            json={"phone": "+12015550002", "message": "menu", "instance": changed.json()["evolution_instance_name"]},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200, response.text
    reply = response.json()["reply"]
    assert "Buscar" in reply or "Find Access Code" in reply
    assert "Control" in reply or "Access Control" in reply
    assert "Clientes" not in reply and "Clients" not in reply
    assert "Suscripciones" not in reply and "Subscriptions" not in reply


async def test_whatsapp_blocked_identity_receives_no_reply(client, db_session, active_tenant_user):
    from app.core.config import settings
    from app.models import BlockedClient, Tenant
    from unittest.mock import patch
    from backend.tests.test_whatsapp_endpoint import _FakeManager

    row = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = row.scalar_one()
    db_session.add(BlockedClient(tenant_id=tenant.id, phone="12015550999", is_active=True))
    await db_session.commit()

    fake_mgr = _FakeManager()
    with patch("app.api.v1.endpoints.integrations.console.get_redis_manager", return_value=fake_mgr):
        response = await client.post(
            "/api/v1/integrations/n8n/console",
            json={"phone": "+12015550999", "message": "codigo", "instance": tenant.evolution_instance_name},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200, response.text
    assert response.json()["no_reply"] is True
    assert response.json()["reply"] == ""
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py::test_whatsapp_starter_menu_is_reduced tests/test_tenant_plan.py::test_whatsapp_blocked_identity_receives_no_reply -q
```

Expected: FAIL for reduced menu and possibly import path; if `backend.tests...` import fails, copy `_FakeManager` into `test_tenant_plan.py` instead of importing it.

- [ ] **Step 3: Add i18n menu keys**

In English WA catalog, replace main menu/help with Pro text and add Starter text:

```python
"wa.tenant.main_menu.starter": "🤖 *TrackPal Starter Console*\n\n1️⃣ My Profile\n2️⃣ Find Access Code\n3️⃣ Access Control\n4️⃣ Help\n\n0️⃣ Exit\n\nReply with the desired option number.",
"wa.tenant.main_menu.pro": "🤖 *TrackPal Admin Console*\n\n1️⃣ Clients\n2️⃣ Catalog\n3️⃣ My Profile\n4️⃣ Subscriptions\n5️⃣ Access Control\n6️⃣ Help\n7️⃣ Find Access Code\n\n0️⃣ Exit\n\nReply with the desired option number.",
"wa.tenant.access_control.menu": "🚫 *Access Control*\n\n1️⃣ List blocked identities\n2️⃣ Block phone\n\n9️⃣ Back to main menu\n0️⃣ Cancel",
"wa.tenant.access_control.block_phone_prompt": "Type the phone number to block.\n\n0️⃣ Cancel",
"wa.tenant.access_control.block_success": "✅ Access blocked for *{identity}*.",
"wa.tenant.access_control.duplicate": "⚠️ That phone is already blocked.",
"wa.tenant.codigo.mailbox_unavailable_external": "❌ Service temporarily unavailable. Try again later.",
```

Add Spanish equivalents to `catalogs_es_wa.py`:

```python
"wa.tenant.main_menu.starter": "🤖 *Consola TrackPal Starter*\n\n1️⃣ Mi Perfil\n2️⃣ Buscar código de acceso\n3️⃣ Control de acceso\n4️⃣ Ayuda\n\n0️⃣ Salir\n\nResponde con el número de la opción.",
"wa.tenant.main_menu.pro": "🤖 *Consola de Administración TrackPal*\n\n1️⃣ Clientes\n2️⃣ Catálogo\n3️⃣ Mi Perfil\n4️⃣ Suscripciones\n5️⃣ Control de acceso\n6️⃣ Ayuda\n7️⃣ Buscar código de acceso\n\n0️⃣ Salir\n\nResponde con el número de la opción.",
"wa.tenant.access_control.menu": "🚫 *Control de acceso*\n\n1️⃣ Ver identidades bloqueadas\n2️⃣ Bloquear teléfono\n\n9️⃣ Volver al menú principal\n0️⃣ Cancelar",
"wa.tenant.access_control.block_phone_prompt": "Escribe el teléfono que quieres bloquear.\n\n0️⃣ Cancelar",
"wa.tenant.access_control.block_success": "✅ Acceso bloqueado para *{identity}*.",
"wa.tenant.access_control.duplicate": "⚠️ Ese teléfono ya está bloqueado.",
"wa.tenant.codigo.mailbox_unavailable_external": "❌ Servicio temporalmente no disponible. Intenta más tarde.",
```

- [ ] **Step 4: Route tenant console by plan**

In `WhatsAppTenantConsoleService.process_message()`, add parameter:

```python
        tenant_plan: str = "pro",
```

When rendering empty/no-flow menu, choose key:

```python
            menu_key = "wa.tenant.main_menu.starter" if tenant_plan == "starter" else "wa.tenant.main_menu.pro"
```

Replace `self._t(self.KEY_MAIN_MENU)` calls in no active flow with `self._t(menu_key)`.

Replace main numeric routing block with:

```python
            if tenant_plan == "starter":
                if msg == "1":
                    return await self._start_profile_flow(phone, session_service, user_id, db)
                if msg == "2" or msg.lower() in ("codigo", "código", "code"):
                    return await self._start_codigo_flow(phone, session_service, tenant_id, db, started_from_menu=msg == "2", role="tenant")
                if msg == "3":
                    return await self._start_access_control_flow(phone, session_service)
                if msg == "4":
                    return self._t(self.KEY_HELP_TEXT)
                return self._t(self.KEY_FALLBACK_NO_FLOW)

            if msg == "1":
                return await self._start_clients_flow(phone, session_service, tenant_id, db)
            if msg == "2":
                return await self._start_catalog_flow(phone, session_service, tenant_id, db)
            if msg == "3":
                return await self._start_profile_flow(phone, session_service, user_id, db)
            if msg == "4":
                return await self._start_subscriptions_flow(phone, session_service, tenant_id, db)
            if msg == "5":
                return await self._start_access_control_flow(phone, session_service)
            if msg == "6":
                return self._t(self.KEY_HELP_TEXT)
            if msg == "7" or msg.lower() in ("codigo", "código", "code"):
                return await self._start_codigo_flow(phone, session_service, tenant_id, db, started_from_menu=msg == "7", role="tenant")
```

Add `ACCESS_CONTROL_FLOW = "access_control"`, `ACCESS_CONTROL_STEP_MENU = "menu"`, `ACCESS_CONTROL_STEP_BLOCK_PHONE = "block_phone"` constants and handler assignments matching the existing assignment pattern. Minimal implementation can reuse `_handle_clients_block_list()` for list/unblock and add block-phone creation through `AccessControlService`.

- [ ] **Step 5: Pass plan from facade/handlers**

In `backend/app/services/whatsapp_tenant_console_facade/facade.py`, after resolving tenant, pass `tenant_plan=tenant.plan` into `console_service.process_message()`.

If the facade does not currently expose the tenant object at the call site, get it through `tenant_service.get_tenant(db, tenant_id)` before calling the console service.

- [ ] **Step 6: Require mailbox exactly connected**

In `codigo_flow.py`, replace:

```python
        if mailbox.status not in ("connected", "error"):
```

With:

```python
        if mailbox.status != "connected":
```

In `console_handlers.py` unauthenticated path, replace:

```python
        if mailbox is None or mailbox.status not in ("connected", "error"):
            return WhatsAppConsoleResponse(reply=_i18n_t(locale, "wa.tenant.codigo.no_mailbox"))
```

With:

```python
        if mailbox is None or mailbox.status != "connected":
            return WhatsAppConsoleResponse(reply=_i18n_t(locale, "wa.tenant.codigo.mailbox_unavailable_external"))
```

- [ ] **Step 7: Ensure blocked check runs before registered client console**

In `console.py`, after `phone_digits` is computed and before `tenant_admin`/`client` routing, run:

```python
    blocked = await blocked_clients_repository.find_active(
        db,
        tenant.id,
        phone=phone_digits if phone_digits else None,
        whatsapp_lid=sender_lid,
    )
    if blocked:
        return WhatsAppConsoleResponse(reply="", no_reply=True)
```

Remove the duplicate unregistered-only blocked check later in the same function or leave it unreachable; prefer removal to avoid drift.

For registered clients under Starter, before `_handle_client_console()`:

```python
        if tenant.plan == "starter":
            if msg_lower in ("codigo", "código", "code"):
                return await _handle_unauthenticated_codigo(phone_digits, message, sender_lid, manager, tenant, db, close_jid)
            return WhatsAppConsoleResponse(reply=t(_tl(tenant), "wa.client.access_denied"), status="closed", close_jid=close_jid)
```

- [ ] **Step 8: Run tests**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py tests/test_whatsapp_endpoint.py tests/test_tenant_console_service.py tests/test_whatsapp_menu_flow.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/whatsapp_tenant_console_service backend/app/services/whatsapp_tenant_console_facade backend/app/api/v1/endpoints/integrations/console.py backend/app/api/v1/endpoints/integrations/console_handlers.py backend/app/core/i18n/catalogs_en_wa.py backend/app/core/i18n/catalogs_es_wa.py backend/tests/test_tenant_plan.py
git commit -m "feat: split whatsapp tenant console by plan"
```

---

### Task 8: Subscription automation ignores Starter tenants

**Files:**
- Modify: `backend/app/services/subscription_job_service/cleanup.py:74-240`
- Modify: `backend/app/services/subscription_job_service/reminder_schedule.py:81-124`
- Modify: `backend/app/services/subscription_job_service/reminder_payloads.py:160-184`
- Test: `backend/tests/test_subscriptions.py`
- Test: `backend/tests/test_tenant_plan.py`

**Interfaces:**
- Consumes: `Tenant.plan`.
- Produces: cleanup/reminder generation skips all subscriptions whose tenant plan is `starter`.

- [ ] **Step 1: Add failing job test**

Append to `backend/tests/test_tenant_plan.py`:

```python
async def test_subscription_cleanup_ignores_starter_tenant(client, db_session, auth_headers, active_tenant_user):
    from datetime import datetime, timedelta, timezone
    from app.models import Client, Plan, Service, Subscription
    from app.services.subscription_job_service import SubscriptionJobService

    row = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = row.scalar_one()
    tenant.plan = "starter"
    client_user = User(username="cleanup_client", password_hash=get_password_hash("x-password"), role="client")
    db_session.add(client_user)
    await db_session.flush()
    c = Client(tenant_id=tenant.id, owner_user_id=client_user.id, full_name="Cleanup Client", username="cleanup_client", is_active=True)
    s = Service(tenant_id=tenant.id, name="Netflix")
    db_session.add_all([c, s])
    await db_session.flush()
    p = Plan(tenant_id=tenant.id, service_id=s.id, name="Monthly")
    db_session.add(p)
    await db_session.flush()
    sub = Subscription(
        tenant_id=tenant.id,
        client_id=c.id,
        service_id=s.id,
        plan_id=p.id,
        streaming_email="viewer@example.com",
        duration_type="1_month",
        starts_at=datetime.now(timezone.utc) - timedelta(days=40),
        expires_at=datetime.now(timezone.utc) - timedelta(days=2),
        status="active",
    )
    db_session.add(sub)
    await db_session.commit()

    results = await SubscriptionJobService().run_cleanup(db_session)
    await db_session.refresh(sub)
    assert sub.status == "active"
    assert results == []
```

- [ ] **Step 2: Run failing test**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py::test_subscription_cleanup_ignores_starter_tenant -q
```

Expected: FAIL because cleanup still mutates Starter subscriptions.

- [ ] **Step 3: Join Tenant in cleanup queries**

In `cleanup.py`, import `Tenant`:

```python
from app.models.tenant import Tenant
```

In `_expire_active_subs`, change select:

```python
        select(Subscription)
        .join(Tenant, Tenant.id == Subscription.tenant_id)
        .where(
            Tenant.plan == "pro",
            Subscription.status == "active",
            Subscription.expires_at <= now,
        )
```

In `_cancel_long_expired_subs`, add `.join(Tenant, Tenant.id == Subscription.tenant_id)` and `Tenant.plan == "pro"`.

In `_delete_old_cancelled_subs`, add `.join(Tenant, Tenant.id == Subscription.tenant_id)` and `Tenant.plan == "pro"`.

- [ ] **Step 4: Skip Starter reminder payloads**

In `reminder_payloads.py`, after `tenant = tenants_map.get(sub.tenant_id)`:

```python
            if not tenant or tenant.plan != "pro" or not settings:
                continue
```

Replace the existing `if not tenant or not settings:` block.

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py tests/test_subscriptions.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/subscription_job_service/cleanup.py backend/app/services/subscription_job_service/reminder_payloads.py backend/tests/test_tenant_plan.py
git commit -m "feat: skip starter tenants in subscription automation"
```

---

### Task 9: Backend docs and verification

**Files:**
- Modify: `docs/architecture/api-layer.md`
- Modify: `docs/architecture/database-schema.md`
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Modify: `docs/architecture/subscriptions.md`
- Modify: `docs/codebase/backend-structure.md`
- Modify: `docs/SUMMARY.md` only if a new doc file is created; do not rewrite it otherwise.

**Interfaces:**
- Consumes: all backend changes.
- Produces: docs that describe `tenants.plan`, Pro gate, access-control API, Starter WhatsApp menu, and subscription job skipping.

- [ ] **Step 1: Update API docs**

In `docs/architecture/api-layer.md`, add:

```markdown
### Plan-aware tenant access

Tenant package is stored on `tenants.plan` with allowed values `starter` and `pro`. Backend gates read this database value. Frontend `tenant_plan` is only a rendering hint.

- Starter tenant admins receive HTTP 404 for Pro-only modules: `/clients`, `/catalog/*`, `/subscriptions/*`, `/subscription-settings`.
- Master users switched into a Starter tenant bypass Pro gates for support.
- Starter can access profile, locale, `/tenant/mailbox/*`, `/code-services/tenants/current`, `/access-control/blocks`, dashboard, and WhatsApp code lookup.
```

Add `/api/v1/access-control/blocks` to the route table.

- [ ] **Step 2: Update database docs**

In `docs/architecture/database-schema.md`, add `tenants.plan` to the Tenant table section:

```markdown
| plan | VARCHAR(20) | Package source of truth. Allowed: `starter`, `pro`. Existing tenants are backfilled to `pro`; new tenants must choose explicitly. |
```

- [ ] **Step 3: Update WhatsApp docs**

In `docs/architecture/whatsapp-console-flow.md`, update Tenant Console menu section with Starter and Pro tables. Use these exact labels:

```markdown
Starter menu: Profile, Buscar código de acceso, Control de acceso, Help, Exit.
Pro menu: Clients, Catalog, Profile, Subscriptions, Control de acceso, Help, Buscar código de acceso, Exit.
```

Also state: blocked identities receive `no_reply=true`; mailbox status must be `connected` for code lookup.

- [ ] **Step 4: Update subscriptions docs**

In `docs/architecture/subscriptions.md`, add:

```markdown
Subscription automation is Pro-only. Cleanup, reminder generation, and pending-reminder payloads skip tenants whose `tenants.plan != 'pro'`. Downgrading to Starter preserves subscription rows and reminder settings but automation stops mutating that tenant's preserved Pro data until upgrade.
```

- [ ] **Step 5: Run backend verification**

```bash
cd backend && uv run pytest
cd backend && uv run ruff check .
```

Expected: pytest PASS; ruff PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/architecture/api-layer.md docs/architecture/database-schema.md docs/architecture/whatsapp-console-flow.md docs/architecture/subscriptions.md docs/codebase/backend-structure.md
git commit -m "docs: document starter pro backend split"
```
