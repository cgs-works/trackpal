# Catalog CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete tenant-scoped Catalog CRUD for services and plans across REST, WhatsApp Tenant Console, and dashboard delete confirmation UI.

**Architecture:** Keep `CatalogService` as backend source of catalog behavior and reuse it from REST and WhatsApp. Add shared preview/count/delete methods, then extend the existing modular WhatsApp Catalog flow and the existing `CatalogPanel.vue` with a typed-confirmation preview modal. Preserve existing route shape under `/catalog`, tenant/RLS scoping, and i18n catalogs.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy async, pytest/pytest-asyncio, Redis-backed WhatsApp sessions, Vue 3 Composition API with Pinia i18n store, Vitest.

---

## Scope and sequencing

This spec spans backend, WhatsApp, frontend, docs, and PR prep, but the subsystems depend on the same backend preview/delete contract. Keep one plan with logical commits:

1. Backend service/repository/API preview and confirmed cascade delete.
2. WhatsApp Catalog menu/list/create/edit/detail behavior.
3. WhatsApp delete warning/confirmation flows.
4. Dashboard preview modal and frontend helper tests.
5. Docs, full verification, Draft PR.

## File structure

### Backend Catalog REST and service layer

- Modify: `backend/app/schemas/catalog.py`
  - Add `CatalogDeleteSubscriptionRow`, `CatalogDeletePreview`, and `CatalogDeletePagination` response schemas.
- Modify: `backend/app/repositories/catalog_repository.py`
  - Preserve existing tenant filters.
  - Change service/plan list ordering to alphabetical by `name` where Catalog UI consumes it.
  - Add count/preview query helpers for services, plans, active subscription rows, and cascade deletes.
- Modify: `backend/app/services/catalog_service/service.py`
  - Add internal dataclasses for service/plan summaries and delete results if Pydantic response models are not convenient for WhatsApp.
  - Add `list_service_summaries()`, `list_plan_summaries()`, `get_service_delete_preview()`, `get_plan_delete_preview()`, `delete_service(..., confirm: bool = False)`, and `delete_plan(..., confirm: bool = False)`.
  - Use service-layer explicit cascade if SQLite tests prove ORM cascade does not delete all dependent subscriptions/events/logs consistently. Use existing DB FK/relationship cascade only where verified.
- Modify: `backend/app/api/v1/endpoints/catalog.py`
  - Add preview routes.
  - Require `confirm=true` on DELETE routes.
- Modify: `backend/app/services/tenant_console_protocols/protocols.py`
  - Extend `CatalogServiceProtocol` with create, delete, summary, and preview methods used by WhatsApp.
- Test: `backend/tests/test_catalog.py`

### WhatsApp Tenant Console

- Modify: `backend/app/services/whatsapp_tenant_console_service/constants.py`
  - Add Catalog steps and i18n key constants.
- Modify: `backend/app/services/whatsapp_tenant_console_service/formatters.py`
  - Add count pluralization helpers, Catalog menu/list/detail/delete-warning formatters, and post-success prompt helper.
- Modify: `backend/app/services/whatsapp_tenant_console_service/catalog_flow.py`
  - Add main Catalog menu, empty menu, service/plan list pagination, create/edit direct flows, plan empty menu, and post-success handler.
- Create: `backend/app/services/whatsapp_tenant_console_service/catalog_delete_flow.py`
  - Isolate delete service/plan warning pagination, confirm handling, and summary output.
- Modify: `backend/app/services/whatsapp_tenant_console_service/_routers.py`
  - Route all new Catalog steps.
- Modify: `backend/app/services/whatsapp_tenant_console_service/_assignments.py`
  - Bind new handlers to `WhatsAppTenantConsoleService`.
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Test: `backend/tests/test_tenant_console_service.py`
- Test: `backend/tests/test_whatsapp_endpoint.py`

### Frontend dashboard

- Modify: `frontend/src/components/CatalogPanel.vue`
  - Replace `window.confirm` deletes with preview modal and typed confirmation.
- Create: `frontend/src/components/catalogDeletePreview.js`
  - Pure helpers: confirmation validation, count labels, date display.
- Create: `frontend/src/components/__tests__/catalogDeletePreview.spec.js`
  - Vitest coverage without adding component-test dependencies.
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py`

### Docs and PR

- Modify: `docs/architecture/api-layer.md`
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Modify: `docs/codebase/frontend-components.md`
- Modify: `docs/SUMMARY.md`

---

## Task 1: Backend preview schemas, repository queries, and service cascade contract

**Files:**
- Modify: `backend/app/schemas/catalog.py`
- Modify: `backend/app/repositories/catalog_repository.py`
- Modify: `backend/app/services/catalog_service/service.py`
- Modify: `backend/app/services/tenant_console_protocols/protocols.py`
- Test: `backend/tests/test_catalog.py`

- [x] **Step 1: Add failing API/service tests for preview, confirm required, cascade, duplicate scope**

Append these imports to `backend/tests/test_catalog.py`:

```python
from datetime import datetime, timezone
from uuid import uuid4

from app.models import Client, Plan, Service, Subscription, User
from app.core.security import get_password_hash
```

Append these helpers and tests to `backend/tests/test_catalog.py`:

```python
async def _catalog_fixture(db_session, tenant_id):
    client_user = User(
        username=f"client_{uuid4().hex[:8]}",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(client_user)
    await db_session.flush()
    client = Client(
        tenant_id=tenant_id,
        owner_user_id=client_user.id,
        full_name="Cliente Demo",
        username=f"client_{uuid4().hex[:8]}",
        phone="584241234567",
        is_active=True,
    )
    db_session.add(client)
    await db_session.flush()

    service = Service(tenant_id=tenant_id, name="Netflix")
    db_session.add(service)
    await db_session.flush()
    basic = Plan(tenant_id=tenant_id, service_id=service.id, name="Basic")
    premium = Plan(tenant_id=tenant_id, service_id=service.id, name="Premium")
    db_session.add_all([basic, premium])
    await db_session.flush()

    active = Subscription(
        tenant_id=tenant_id,
        client_id=client.id,
        service_id=service.id,
        plan_id=premium.id,
        streaming_email="active@example.com",
        duration_type="1_month",
        starts_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        status="active",
    )
    historical = Subscription(
        tenant_id=tenant_id,
        client_id=client.id,
        service_id=service.id,
        plan_id=basic.id,
        streaming_email="old@example.com",
        duration_type="1_month",
        starts_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        status="expired",
    )
    db_session.add_all([active, historical])
    await db_session.commit()
    return service, basic, premium, active, historical


async def test_catalog_delete_preview_and_confirmed_service_cascade(
    client, active_tenant_user, db_session
):
    tenant_id = await _tenant_id(db_session, active_tenant_user)
    service, basic, premium, active, historical = await _catalog_fixture(db_session, tenant_id)
    headers = await _login(client)

    preview = await client.get(
        f"/api/v1/catalog/services/{service.id}/delete-preview?page=1&page_size=10",
        headers=headers,
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["target_type"] == "service"
    assert payload["target_name"] == "Netflix"
    assert payload["affected_plan_count"] == 2
    assert payload["active_subscription_count"] == 1
    assert payload["historical_subscription_count"] == 1
    assert payload["total_subscription_count"] == 2
    assert payload["active_subscriptions"][0]["streaming_email"] == "active@example.com"
    assert "historical" in payload["note"].lower() or "hist" in payload["note"].lower()

    denied = await client.delete(f"/api/v1/catalog/services/{service.id}", headers=headers)
    assert denied.status_code == 400

    deleted = await client.delete(
        f"/api/v1/catalog/services/{service.id}?confirm=true", headers=headers
    )
    assert deleted.status_code == 204

    assert (await client.get(f"/api/v1/catalog/services/{service.id}", headers=headers)).status_code == 404
    assert (await client.get(f"/api/v1/catalog/services/{service.id}/plans", headers=headers)).status_code == 404


async def test_catalog_delete_preview_and_confirmed_plan_cascade(
    client, active_tenant_user, db_session
):
    tenant_id = await _tenant_id(db_session, active_tenant_user)
    service, basic, premium, active, historical = await _catalog_fixture(db_session, tenant_id)
    headers = await _login(client)

    preview = await client.get(
        f"/api/v1/catalog/services/{service.id}/plans/{premium.id}/delete-preview?page=1&page_size=10",
        headers=headers,
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["target_type"] == "plan"
    assert payload["target_name"] == "Premium"
    assert payload["affected_plan_count"] == 0
    assert payload["active_subscription_count"] == 1
    assert payload["historical_subscription_count"] == 0
    assert payload["total_subscription_count"] == 1

    denied = await client.delete(
        f"/api/v1/catalog/services/{service.id}/plans/{premium.id}", headers=headers
    )
    assert denied.status_code == 400

    deleted = await client.delete(
        f"/api/v1/catalog/services/{service.id}/plans/{premium.id}?confirm=true",
        headers=headers,
    )
    assert deleted.status_code == 204

    plans = await client.get(f"/api/v1/catalog/services/{service.id}/plans", headers=headers)
    assert plans.status_code == 200
    assert [plan["name"] for plan in plans.json()] == ["Basic"]


async def test_plan_duplicate_name_is_scoped_to_same_service(client, active_tenant_user):
    headers = await _login(client)
    one = await client.post("/api/v1/catalog/services", json={"name": "Netflix"}, headers=headers)
    two = await client.post("/api/v1/catalog/services", json={"name": "Disney"}, headers=headers)
    assert one.status_code == 201
    assert two.status_code == 201

    first_plan = await client.post(
        f"/api/v1/catalog/services/{one.json()['id']}/plans",
        json={"name": "Premium"},
        headers=headers,
    )
    same_other_service = await client.post(
        f"/api/v1/catalog/services/{two.json()['id']}/plans",
        json={"name": "Premium"},
        headers=headers,
    )
    duplicate_same_service = await client.post(
        f"/api/v1/catalog/services/{one.json()['id']}/plans",
        json={"name": "premium"},
        headers=headers,
    )

    assert first_plan.status_code == 201
    assert same_other_service.status_code == 201
    assert duplicate_same_service.status_code == 409
```

Update existing `test_tenant_service_and_plan_crud` so the plain service delete assertion expects `400`, then add a confirmed delete assertion:

```python
plain_delete = await client.delete(f"/api/v1/catalog/services/{sid}", headers=headers)
assert plain_delete.status_code == 400
confirmed_delete = await client.delete(f"/api/v1/catalog/services/{sid}?confirm=true", headers=headers)
assert confirmed_delete.status_code == 204
```

- [x] **Step 2: Run failing backend catalog tests**

Run:

```bash
cd backend && uv run pytest tests/test_catalog.py -q
```

Expected: FAIL because delete-preview routes and `confirm` enforcement do not exist yet, and existing `_commit_catalog_change` test still expects `ValueError` from `UserFacingError`-based implementation.

- [x] **Step 3: Add preview response schemas**

In `backend/app/schemas/catalog.py`, add after `PlanResponse`:

```python
class CatalogDeleteSubscriptionRow(BaseModel):
    id: UUID
    streaming_email: str
    client_name: str | None = None
    client_phone: str | None = None
    service_name: str
    plan_name: str
    expires_at: datetime


class CatalogDeletePagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool


class CatalogDeletePreview(BaseModel):
    target_type: str
    target_id: UUID
    target_name: str
    affected_plan_count: int = 0
    active_subscription_count: int
    historical_subscription_count: int
    total_subscription_count: int
    active_subscriptions: list[CatalogDeleteSubscriptionRow]
    pagination: CatalogDeletePagination
    note: str
```

- [x] **Step 4: Add repository query helpers**

In `backend/app/repositories/catalog_repository.py`:

1. Extend imports:

```python
from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import aliased

from app.models import Client, Plan, Service, Subscription
```

2. Change `list_services()` ordering to alphabetical:

```python
.order_by(func.lower(Service.name).asc(), Service.created_at.asc())
```

3. Change `list_plans()` ordering to alphabetical:

```python
.order_by(func.lower(Plan.name).asc(), Plan.created_at.asc())
```

4. Add helpers before `__all__`:

```python
async def count_plans_for_service(db: AsyncSession, tenant_id: UUID, service_id: UUID) -> int:
    result = await db.execute(
        select(func.count(Plan.id)).where(
            Plan.tenant_id == tenant_id,
            Plan.service_id == service_id,
        )
    )
    return int(result.scalar_one() or 0)


async def count_subscriptions_for_service(db: AsyncSession, tenant_id: UUID, service_id: UUID) -> tuple[int, int]:
    active_expr = func.sum(case((Subscription.status == "active", 1), else_=0))
    total_expr = func.count(Subscription.id)
    result = await db.execute(
        select(active_expr, total_expr).where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
        )
    )
    active_count, total_count = result.one()
    active = int(active_count or 0)
    total = int(total_count or 0)
    return active, total - active


async def count_subscriptions_for_plan(db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID) -> tuple[int, int]:
    active_expr = func.sum(case((Subscription.status == "active", 1), else_=0))
    total_expr = func.count(Subscription.id)
    result = await db.execute(
        select(active_expr, total_expr).where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
            Subscription.plan_id == plan_id,
        )
    )
    active_count, total_count = result.one()
    active = int(active_count or 0)
    total = int(total_count or 0)
    return active, total - active


async def list_active_subscription_rows_for_service(
    db: AsyncSession, tenant_id: UUID, service_id: UUID, *, offset: int, limit: int
) -> list[tuple[Subscription, Client, Service, Plan]]:
    result = await db.execute(
        select(Subscription, Client, Service, Plan)
        .join(Client, Client.id == Subscription.client_id)
        .join(Service, Service.id == Subscription.service_id)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
            Subscription.status == "active",
        )
        .order_by(Subscription.expires_at.is_(None).asc(), Subscription.expires_at.asc(), Subscription.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.all())


async def list_active_subscription_rows_for_plan(
    db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID, *, offset: int, limit: int
) -> list[tuple[Subscription, Client, Service, Plan]]:
    result = await db.execute(
        select(Subscription, Client, Service, Plan)
        .join(Client, Client.id == Subscription.client_id)
        .join(Service, Service.id == Subscription.service_id)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
            Subscription.plan_id == plan_id,
            Subscription.status == "active",
        )
        .order_by(Subscription.expires_at.is_(None).asc(), Subscription.expires_at.asc(), Subscription.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.all())


async def delete_subscriptions_for_service(db: AsyncSession, tenant_id: UUID, service_id: UUID) -> None:
    await db.execute(
        delete(Subscription).where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
        )
    )


async def delete_subscriptions_for_plan(db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID) -> None:
    await db.execute(
        delete(Subscription).where(
            Subscription.tenant_id == tenant_id,
            Subscription.service_id == service_id,
            Subscription.plan_id == plan_id,
        )
    )


async def delete_plans_for_service(db: AsyncSession, tenant_id: UUID, service_id: UUID) -> None:
    await db.execute(
        delete(Plan).where(
            Plan.tenant_id == tenant_id,
            Plan.service_id == service_id,
        )
    )
```

5. Add new function names to `__all__`.

- [x] **Step 5: Implement service preview and confirm contract**

In `backend/app/services/catalog_service/service.py`:

1. Add imports:

```python
from dataclasses import dataclass
import math

from app.schemas.catalog import (
    CatalogDeletePagination,
    CatalogDeletePreview,
    CatalogDeleteSubscriptionRow,
    PlanCreate,
    PlanUpdate,
    ServiceCreate,
    ServiceUpdate,
)
```

2. Add dataclasses above `CatalogService`:

```python
@dataclass(frozen=True)
class CatalogServiceSummary:
    id: UUID
    name: str
    plan_count: int
    active_subscription_count: int


@dataclass(frozen=True)
class CatalogPlanSummary:
    id: UUID
    service_id: UUID
    name: str
    active_subscription_count: int
```

3. Add private helpers inside `CatalogService`:

```python
def _page_bounds(self, page: int, page_size: int) -> tuple[int, int]:
    safe_page = max(1, int(page or 1))
    safe_page_size = max(1, min(100, int(page_size or 10)))
    return safe_page, safe_page_size


def _pagination(self, *, page: int, page_size: int, total_items: int) -> CatalogDeletePagination:
    total_pages = max(1, math.ceil(total_items / page_size))
    return CatalogDeletePagination(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
    )


def _row(self, sub, client, service, plan) -> CatalogDeleteSubscriptionRow:
    return CatalogDeleteSubscriptionRow(
        id=sub.id,
        streaming_email=sub.streaming_email,
        client_name=getattr(client, "full_name", None),
        client_phone=getattr(client, "phone", None),
        service_name=service.name,
        plan_name=plan.name,
        expires_at=sub.expires_at,
    )
```

4. Add summary methods:

```python
async def list_service_summaries(self, db: AsyncSession, tenant_id: UUID) -> list[CatalogServiceSummary]:
    services = await self.list_services(db, tenant_id)
    summaries = []
    for service in services:
        plan_count = await catalog_repository.count_plans_for_service(db, tenant_id, service.id)
        active_count, _historical_count = await catalog_repository.count_subscriptions_for_service(db, tenant_id, service.id)
        summaries.append(CatalogServiceSummary(service.id, service.name, plan_count, active_count))
    return summaries


async def list_plan_summaries(self, db: AsyncSession, tenant_id: UUID, service_id: UUID) -> list[CatalogPlanSummary] | None:
    plans = await self.list_plans(db, tenant_id, service_id)
    if plans is None:
        return None
    summaries = []
    for plan in plans:
        active_count, _historical_count = await catalog_repository.count_subscriptions_for_plan(db, tenant_id, service_id, plan.id)
        summaries.append(CatalogPlanSummary(plan.id, service_id, plan.name, active_count))
    return summaries
```

5. Add preview methods:

```python
async def get_service_delete_preview(
    self, db: AsyncSession, tenant_id: UUID, service_id: UUID, *, page: int = 1, page_size: int = 10
) -> CatalogDeletePreview | None:
    service = await self.get_service(db, tenant_id, service_id)
    if service is None:
        return None
    page, page_size = self._page_bounds(page, page_size)
    offset = (page - 1) * page_size
    plan_count = await catalog_repository.count_plans_for_service(db, tenant_id, service_id)
    active_count, historical_count = await catalog_repository.count_subscriptions_for_service(db, tenant_id, service_id)
    rows = await catalog_repository.list_active_subscription_rows_for_service(
        db, tenant_id, service_id, offset=offset, limit=page_size
    )
    return CatalogDeletePreview(
        target_type="service",
        target_id=service.id,
        target_name=service.name,
        affected_plan_count=plan_count,
        active_subscription_count=active_count,
        historical_subscription_count=historical_count,
        total_subscription_count=active_count + historical_count,
        active_subscriptions=[self._row(sub, client, svc, plan) for sub, client, svc, plan in rows],
        pagination=self._pagination(page=page, page_size=page_size, total_items=active_count),
        note="Historical, expired, cancelled, and other non-active subscriptions will also be deleted even when they are not listed.",
    )


async def get_plan_delete_preview(
    self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID, *, page: int = 1, page_size: int = 10
) -> CatalogDeletePreview | None:
    plan = await self.get_plan(db, tenant_id, service_id, plan_id)
    if plan is None:
        return None
    page, page_size = self._page_bounds(page, page_size)
    offset = (page - 1) * page_size
    active_count, historical_count = await catalog_repository.count_subscriptions_for_plan(db, tenant_id, service_id, plan_id)
    rows = await catalog_repository.list_active_subscription_rows_for_plan(
        db, tenant_id, service_id, plan_id, offset=offset, limit=page_size
    )
    return CatalogDeletePreview(
        target_type="plan",
        target_id=plan.id,
        target_name=plan.name,
        affected_plan_count=0,
        active_subscription_count=active_count,
        historical_subscription_count=historical_count,
        total_subscription_count=active_count + historical_count,
        active_subscriptions=[self._row(sub, client, svc, row_plan) for sub, client, svc, row_plan in rows],
        pagination=self._pagination(page=page, page_size=page_size, total_items=active_count),
        note="Historical, expired, cancelled, and other non-active subscriptions will also be deleted even when they are not listed.",
    )
```

6. Replace delete methods with confirm-gated versions:

```python
async def delete_service(
    self, db: AsyncSession, tenant_id: UUID, service_id: UUID, *, confirm: bool = False
) -> CatalogDeletePreview | None:
    if not confirm:
        raise UserFacingError("catalog_delete_confirmation_required")
    preview = await self.get_service_delete_preview(db, tenant_id, service_id)
    if preview is None:
        return None
    service = await self.get_service(db, tenant_id, service_id)
    if service is None:
        return None
    await catalog_repository.delete_subscriptions_for_service(db, tenant_id, service_id)
    await catalog_repository.delete_plans_for_service(db, tenant_id, service_id)
    await db.delete(service)
    await db.commit()
    return preview


async def delete_plan(
    self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID, *, confirm: bool = False
) -> CatalogDeletePreview | None:
    if not confirm:
        raise UserFacingError("catalog_delete_confirmation_required")
    preview = await self.get_plan_delete_preview(db, tenant_id, service_id, plan_id)
    if preview is None:
        return None
    plan = await self.get_plan(db, tenant_id, service_id, plan_id)
    if plan is None:
        return None
    await catalog_repository.delete_subscriptions_for_plan(db, tenant_id, service_id, plan_id)
    await db.delete(plan)
    await db.commit()
    return preview
```

7. Update `_commit_catalog_change` test expectation because method already raises `UserFacingError`, which subclasses `ValueError`:

```python
with pytest.raises(UserFacingError, match="service_name_already_exists"):
    await CatalogService()._commit_catalog_change(db, "service_name_already_exists")
```

Import `UserFacingError` in `backend/tests/test_catalog.py` if missing.

- [x] **Step 6: Extend CatalogServiceProtocol**

In `backend/app/services/tenant_console_protocols/protocols.py`, update `CatalogServiceProtocol` docstring to remove “creation and deletion are out of scope”, then add methods:

```python
async def list_service_summaries(self, db: AsyncSession, tenant_id: UUID) -> list[Any]: ...

async def list_plan_summaries(self, db: AsyncSession, tenant_id: UUID, service_id: UUID) -> list[Any] | None: ...

async def create_service(self, db: AsyncSession, tenant_id: UUID, payload: Any) -> Any | None: ...

async def create_plan(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, payload: Any) -> Any | None: ...

async def get_service_delete_preview(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, *, page: int = 1, page_size: int = 10) -> Any | None: ...

async def get_plan_delete_preview(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID, *, page: int = 1, page_size: int = 10) -> Any | None: ...

async def delete_service(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, *, confirm: bool = False) -> Any | None: ...

async def delete_plan(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID, *, confirm: bool = False) -> Any | None: ...
```

- [x] **Step 7: Run service/API-focused tests**

Run:

```bash
cd backend && uv run pytest tests/test_catalog.py -q
```

Expected: still FAIL until routes are added in Task 2, but pure service tests should now be close to passing.

- [x] **Step 8: Commit backend service foundation**

```bash
git add backend/app/schemas/catalog.py \
  backend/app/repositories/catalog_repository.py \
  backend/app/services/catalog_service/service.py \
  backend/app/services/tenant_console_protocols/protocols.py \
  backend/tests/test_catalog.py
git commit -m "feat(catalog): add delete previews and confirmed cascade"
```

---

## Task 2: REST preview routes and confirm-gated DELETE endpoints

**Files:**
- Modify: `backend/app/api/v1/endpoints/catalog.py`
- Modify: `backend/app/core/i18n/catalogs_es_general.py`
- Modify: `backend/app/core/i18n/catalogs_en_general.py`
- Test: `backend/tests/test_catalog.py`

- [x] **Step 1: Add localized confirmation-required error**

In `backend/app/core/i18n/catalogs_es_general.py`, add near other `errors.*` keys:

```python
"errors.catalog_delete_confirmation_required": "Debes confirmar la eliminacion con confirm=true",
```

In `backend/app/core/i18n/catalogs_en_general.py`, add:

```python
"errors.catalog_delete_confirmation_required": "Delete must be confirmed with confirm=true",
```

- [x] **Step 2: Update Catalog API imports and route signatures**

In `backend/app/api/v1/endpoints/catalog.py`:

1. Extend imports:

```python
from fastapi import APIRouter, HTTPException, Query, Response, status
from app.schemas.catalog import (
    CatalogDeletePreview,
    PlanCreate,
    PlanResponse,
    PlanUpdate,
    ServiceCreate,
    ServiceResponse,
    ServiceUpdate,
)
```

2. Add helper near `catalog_service = CatalogService()`:

```python
async def _confirmation_required(db: DbDep, tenant_id: ActiveTenantId) -> HTTPException:
    locale = await resolve_locale(db, tenant_id)
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=_t(locale, "errors.catalog_delete_confirmation_required"),
    )
```

3. Add service preview route before service DELETE:

```python
@router.get("/services/{service_id}/delete-preview", response_model=CatalogDeletePreview)
async def preview_delete_service(
    service_id: UUID,
    db: DbDep,
    tenant_id: ActiveTenantId,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=10),
):
    preview = await catalog_service.get_service_delete_preview(
        db, tenant_id, service_id, page=page, page_size=page_size
    )
    if preview is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.service_not_found"))
    return preview
```

4. Replace service DELETE:

```python
@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: UUID,
    db: DbDep,
    tenant_id: ActiveTenantId,
    confirm: bool = Query(False),
):
    if not confirm:
        raise await _confirmation_required(db, tenant_id)
    deleted = await catalog_service.delete_service(db, tenant_id, service_id, confirm=True)
    if deleted is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.service_not_found"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

5. Add plan preview route before plan DELETE:

```python
@router.get("/services/{service_id}/plans/{plan_id}/delete-preview", response_model=CatalogDeletePreview)
async def preview_delete_plan(
    service_id: UUID,
    plan_id: UUID,
    db: DbDep,
    tenant_id: ActiveTenantId,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=10),
):
    preview = await catalog_service.get_plan_delete_preview(
        db, tenant_id, service_id, plan_id, page=page, page_size=page_size
    )
    if preview is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.plan_not_found"))
    return preview
```

6. Replace plan DELETE:

```python
@router.delete("/services/{service_id}/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    service_id: UUID,
    plan_id: UUID,
    db: DbDep,
    tenant_id: ActiveTenantId,
    confirm: bool = Query(False),
):
    if not confirm:
        raise await _confirmation_required(db, tenant_id)
    deleted = await catalog_service.delete_plan(db, tenant_id, service_id, plan_id, confirm=True)
    if deleted is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.plan_not_found"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [x] **Step 3: Run Catalog API tests**

Run:

```bash
cd backend && uv run pytest tests/test_catalog.py -q
```

Expected: PASS. If SQLite FK behavior differs, adjust service-layer explicit deletes in Task 1 code, not tests.

- [x] **Step 4: Commit API routes**

```bash
git add backend/app/api/v1/endpoints/catalog.py \
  backend/app/core/i18n/catalogs_es_general.py \
  backend/app/core/i18n/catalogs_en_general.py \
  backend/tests/test_catalog.py
git commit -m "feat(api): require catalog delete previews and confirmation"
```

---

## Task 3: WhatsApp Catalog menu, pagination, create/edit, details, and post-success flow

**Files:**
- Modify: `backend/app/services/whatsapp_tenant_console_service/constants.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/formatters.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/catalog_flow.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/_routers.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/_assignments.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Test: `backend/tests/test_tenant_console_service.py`

- [ ] **Step 1: Extend WhatsApp fakes and add failing menu/list/create/detail tests**

In `backend/tests/test_tenant_console_service.py`, extend `FakeServiceObj` and `FakePlanObj`:

```python
@dataclass
class FakeServiceObj:
    id: UUID = field(default_factory=uuid4)
    name: str = "Test Service"
    plan_count: int = 0
    active_subscription_count: int = 0


@dataclass
class FakePlanObj:
    id: UUID = field(default_factory=uuid4)
    service_id: UUID | None = None
    name: str = "Test Plan"
    active_subscription_count: int = 0
```

Add methods to `FakeCatalogService`:

```python
async def list_service_summaries(self, db: Any, tenant_id: UUID) -> list[FakeServiceObj]:
    return sorted(self._services.values(), key=lambda item: item.name.lower())

async def list_plan_summaries(self, db: Any, tenant_id: UUID, service_id: UUID) -> list[FakePlanObj] | None:
    if str(service_id) not in self._services:
        return None
    return sorted(
        [plan for plan in self._plans.values() if plan.service_id in (None, service_id)],
        key=lambda item: item.name.lower(),
    )

async def create_service(self, db: Any, tenant_id: UUID, payload: Any) -> FakeServiceObj:
    if any(item.name.lower() == payload.name.lower() for item in self._services.values()):
        raise UserFacingError("service_name_already_exists")
    service = FakeServiceObj(name=payload.name)
    self._services[str(service.id)] = service
    return service

async def create_plan(self, db: Any, tenant_id: UUID, service_id: UUID, payload: Any) -> FakePlanObj | None:
    if str(service_id) not in self._services:
        return None
    if any(item.service_id == service_id and item.name.lower() == payload.name.lower() for item in self._plans.values()):
        raise UserFacingError("plan_name_already_exists")
    plan = FakePlanObj(service_id=service_id, name=payload.name)
    self._plans[str(plan.id)] = plan
    return plan
```

Append tests under `TestServiceMainMenu` or a new `TestCatalogFlow` class:

```python
async def test_catalog_starts_with_main_catalog_menu(
    self, console_service: WhatsAppTenantConsoleService, session_service: WhatsAppSessionService
) -> None:
    reply = await console_service.process_message(
        phone="+10000000000",
        message="2",
        tenant_id=uuid4(),
        db=cast(AsyncSession, object()),
        session_service=session_service,
    )
    assert "📦" in reply
    assert "Ver servicios" in reply
    assert "Crear servicio" in reply
    assert "Eliminar servicio" in reply
    session = await session_service.get_session("admin:+10000000000")
    assert session is not None
    assert session.flow == "catalog"
    assert session.step == "menu"


async def test_catalog_empty_menu_only_offers_create(
    self, console_service: WhatsAppTenantConsoleService, catalog_service: FakeCatalogService, session_service: WhatsAppSessionService
) -> None:
    catalog_service._services.clear()
    reply = await console_service.process_message(
        phone="+10000000000",
        message="2",
        tenant_id=uuid4(),
        db=cast(AsyncSession, object()),
        session_service=session_service,
    )
    assert "No hay servicios" in reply
    assert "Crear servicio" in reply
    assert "Eliminar servicio" not in reply


async def test_catalog_service_list_is_alphabetical_paginated_and_has_counts(
    self, console_service: WhatsAppTenantConsoleService, catalog_service: FakeCatalogService, session_service: WhatsAppSessionService
) -> None:
    catalog_service._services.clear()
    for name in ["Zulu", "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Eta", "Theta"]:
        service = FakeServiceObj(name=name, plan_count=1, active_subscription_count=2)
        catalog_service._services[str(service.id)] = service
    await console_service.process_message("+10000000000", "2", tenant_id=uuid4(), db=cast(AsyncSession, object()), session_service=session_service)
    reply = await console_service.process_message("+10000000000", "1", tenant_id=uuid4(), db=cast(AsyncSession, object()), session_service=session_service)
    assert "1️⃣ Alpha - 1 plan - 2 suscripciones activas" in reply
    assert "7️⃣ Eta" in reply
    assert "8️⃣ Siguiente" in reply
    assert "Zulu" not in reply


async def test_catalog_service_detail_hides_id_and_exposes_required_actions(
    self, console_service: WhatsAppTenantConsoleService, session_service: WhatsAppSessionService
) -> None:
    tenant_id = uuid4()
    await console_service.process_message("+10000000000", "2", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    await console_service.process_message("+10000000000", "1", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    reply = await console_service.process_message("+10000000000", "1", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    assert "*ID:*" not in reply
    assert "Editar nombre" in reply
    assert "Ver planes" in reply
    assert "Crear plan" in reply
    assert "Eliminar plan" in reply
    assert "Eliminar servicio" not in reply


async def test_catalog_create_service_direct_success_and_duplicate_retry(
    self, console_service: WhatsAppTenantConsoleService, catalog_service: FakeCatalogService, session_service: WhatsAppSessionService
) -> None:
    tenant_id = uuid4()
    await console_service.process_message("+10000000000", "2", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    prompt = await console_service.process_message("+10000000000", "2", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    assert "nombre" in prompt.lower()
    duplicate = await console_service.process_message("+10000000000", "Netflix", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    assert "nombre del servicio ya existe" in duplicate
    session = await session_service.get_session("admin:+10000000000")
    assert session is not None
    assert session.step == "create_service_name"
    success = await console_service.process_message("+10000000000", "Disney", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    assert "Servicio" in success and "creado" in success
    assert "1️⃣ Volver al menú principal" in success or "1️⃣ Volver al menu principal" in success
```

- [ ] **Step 2: Run failing WhatsApp Catalog tests**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_console_service.py -k "catalog" -q
```

Expected: FAIL because current Catalog starts with direct service list, detail shows ID, no create steps exist, and counts are not formatted.

- [ ] **Step 3: Add Catalog constants and i18n keys**

In `backend/app/services/whatsapp_tenant_console_service/constants.py`, add:

```python
CATALOG_PAGE_SIZE = 7
CATALOG_STEP_MENU = "menu"
CATALOG_STEP_CREATE_SERVICE_NAME = "create_service_name"
CATALOG_STEP_CREATE_PLAN_NAME = "create_plan_name"
CATALOG_STEP_EMPTY_PLAN_MENU = "empty_plan_menu"
CATALOG_STEP_POST_ACTION = "post_action"
CATALOG_STEP_DELETE_SERVICE_SELECT = "delete_service_select"
CATALOG_STEP_DELETE_SERVICE_CONFIRM = "delete_service_confirm"
CATALOG_STEP_DELETE_PLAN_SELECT = "delete_plan_select"
CATALOG_STEP_DELETE_PLAN_CONFIRM = "delete_plan_confirm"

KEY_CATALOG_EMPTY_MENU = "wa.tenant.catalog.empty_menu"
KEY_CATALOG_CREATE_SERVICE_PROMPT = "wa.tenant.catalog.create_service_prompt"
KEY_CATALOG_CREATE_SERVICE_SUCCESS = "wa.tenant.catalog.create_service_success"
KEY_CATALOG_CREATE_PLAN_PROMPT = "wa.tenant.catalog.create_plan_prompt"
KEY_CATALOG_CREATE_PLAN_SUCCESS = "wa.tenant.catalog.create_plan_success"
KEY_CATALOG_EMPTY_PLANS_MENU = "wa.tenant.catalog.empty_plans_menu"
KEY_CATALOG_NO_PLANS_FOR_DELETE = "wa.tenant.catalog.no_plans_for_delete"
KEY_CATALOG_POST_SUCCESS_PROMPT = "wa.tenant.catalog.post_success_prompt"
KEY_CATALOG_POST_SUCCESS_INVALID = "wa.tenant.catalog.post_success_invalid"
```

Update ES WA catalog keys:

```python
"wa.tenant.catalog.menu": "📦 *Catalogo*\n\n1️⃣ Ver servicios\n2️⃣ Crear servicio\n3️⃣ Eliminar servicio\n9️⃣ Volver al menu principal\n0️⃣ Cancelar",
"wa.tenant.catalog.empty_menu": "📦 *Catalogo*\n\n📭 No hay servicios registrados.\n\n1️⃣ Crear servicio\n9️⃣ Volver al menu principal\n0️⃣ Cancelar",
"wa.tenant.catalog.service_actions": "*Acciones disponibles:*\n1️⃣ Editar nombre\n2️⃣ Ver planes\n3️⃣ Crear plan\n4️⃣ Eliminar plan\n9️⃣ Volver",
"wa.tenant.catalog.plan_actions": "*Acciones disponibles:*\n1️⃣ Editar nombre\n2️⃣ Eliminar plan\n9️⃣ Volver",
"wa.tenant.catalog.create_service_prompt": "✏️ *Crear Servicio*\n\nCual es el *nombre* del nuevo servicio?",
"wa.tenant.catalog.create_service_success": "✅ Servicio *{name}* creado exitosamente.",
"wa.tenant.catalog.create_plan_prompt": "✏️ *Crear Plan*\n\nCual es el *nombre* del nuevo plan?",
"wa.tenant.catalog.create_plan_success": "✅ Plan *{name}* creado exitosamente.",
"wa.tenant.catalog.empty_plans_menu": "📭 Este servicio no tiene planes.\n\n1️⃣ Crear plan\n9️⃣ Volver\n0️⃣ Cancelar",
"wa.tenant.catalog.no_plans_for_delete": "📭 Este servicio no tiene planes para eliminar.\n\nVolviendo al Catalogo.",
"wa.tenant.catalog.post_success_prompt": "\n\n1️⃣ Volver al menu principal\n0️⃣ Cancelar",
"wa.tenant.catalog.post_success_invalid": "❌ Opcion invalida. Responde *1* para volver al menu principal o *0* para cancelar.",
"wa.tenant.catalog.count.plan.one": "1 plan",
"wa.tenant.catalog.count.plan.other": "{count} planes",
"wa.tenant.catalog.count.subscription_active.one": "1 suscripcion activa",
"wa.tenant.catalog.count.subscription_active.other": "{count} suscripciones activas",
```

Add English equivalents with `Catalog`, `View services`, `Create service`, `Delete service`, `Back to main menu`, `1 plan`, `{count} plans`, `1 active subscription`, `{count} active subscriptions`.

- [ ] **Step 4: Add formatting helpers**

In `backend/app/services/whatsapp_tenant_console_service/formatters.py`, add helpers:

```python
def _catalog_count(key_base: str, count: int) -> str:
    suffix = "one" if count == 1 else "other"
    return _i18n_t(ctx.get_locale(), f"{key_base}.{suffix}", count=count)


def _format_service_list(services: list[Any], page: int = 1, total_pages: int = 1) -> tuple[str, dict[str, str]]:
    entries: list[str] = []
    selection_map: dict[str, str] = {}
    for i, s in enumerate(services, start=1):
        num = str(i)
        plan_count = int(getattr(s, "plan_count", 0) or 0)
        active_count = int(getattr(s, "active_subscription_count", 0) or 0)
        entries.append(
            f"{num}️⃣ {s.name} - "
            f"{_catalog_count('wa.tenant.catalog.count.plan', plan_count)} - "
            f"{_catalog_count('wa.tenant.catalog.count.subscription_active', active_count)}"
        )
        selection_map[num] = str(s.id)
    reply = "📋 *Servicios*\n\n" + "\n".join(entries)
    if total_pages > 1:
        reply += "\n\n" + _i18n_t(ctx.get_locale(), "wa.tenant.subscriptions.list.page_info", page=page, total=total_pages)
    nav = []
    if page < total_pages:
        nav.append(_i18n_t(ctx.get_locale(), "wa.nav.next"))
    nav.append(_i18n_t(ctx.get_locale(), "wa.nav.back"))
    nav.append(_i18n_t(ctx.get_locale(), "wa.nav.cancel"))
    reply += "\n" + " | ".join(nav)
    return reply, selection_map


def _format_service_detail(service: Any) -> str:
    return f"📦 *Servicio*\n\n*Nombre:* {service.name}\n\n"


def _format_plan_list(plans: list[Any], page: int = 1, total_pages: int = 1) -> tuple[str, dict[str, str]]:
    entries: list[str] = []
    selection_map: dict[str, str] = {}
    for i, p in enumerate(plans, start=1):
        num = str(i)
        active_count = int(getattr(p, "active_subscription_count", 0) or 0)
        entries.append(
            f"{num}️⃣ {p.name} - "
            f"{_catalog_count('wa.tenant.catalog.count.subscription_active', active_count)}"
        )
        selection_map[num] = str(p.id)
    reply = "📋 *Planes*\n\n" + "\n".join(entries)
    if total_pages > 1:
        reply += "\n\n" + _i18n_t(ctx.get_locale(), "wa.tenant.subscriptions.list.page_info", page=page, total=total_pages)
    nav = []
    if page < total_pages:
        nav.append(_i18n_t(ctx.get_locale(), "wa.nav.next"))
    nav.append(_i18n_t(ctx.get_locale(), "wa.nav.back"))
    nav.append(_i18n_t(ctx.get_locale(), "wa.nav.cancel"))
    reply += "\n" + " | ".join(nav)
    return reply, selection_map
```

Keep `_format_plan_detail()` as ID-free.

- [ ] **Step 5: Implement menu/list/create/edit/post-success flow**

In `backend/app/services/whatsapp_tenant_console_service/catalog_flow.py`, add imports:

```python
import math
from app.schemas.catalog import PlanCreate, PlanUpdate, ServiceCreate, ServiceUpdate
```

Add helpers:

```python
def _paginate(items, page: int, page_size: int):
    safe_page = max(1, page)
    total_pages = max(1, math.ceil(len(items) / page_size))
    start = (safe_page - 1) * page_size
    return items[start : start + page_size], safe_page, total_pages


async def _catalog_menu_reply(self, tenant_id, db):
    if tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_EMPTY_MENU)
    services = await self._catalog_service.list_service_summaries(db, tenant_id)
    return self._t(self.KEY_CATALOG_MENU if services else self.KEY_CATALOG_EMPTY_MENU)


async def _set_post_action(self, phone, session_service, message):
    if session_service is not None:
        session = await session_service.get_session(f"admin:{phone}")
        if session is None:
            session = await session_service.create_session(f"admin:{phone}")
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_POST_ACTION
        session.selection_map = {}
        session.temp_data = {}
        await session_service.save_session(session)
    return message.rstrip() + self._t(self.KEY_CATALOG_POST_SUCCESS_PROMPT)
```

Replace `_start_catalog_flow()` so it creates a session at `CATALOG_STEP_MENU` and returns `_catalog_menu_reply()`.

Add `_handle_catalog_menu()`:

```python
async def _handle_catalog_menu(self, phone, msg, session, session_service, tenant_id, db):
    services = []
    if tenant_id is not None and db is not None and self._catalog_service is not None:
        services = await self._catalog_service.list_service_summaries(db, tenant_id)
    has_services = bool(services)
    if is_back(msg):
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._t(self.KEY_MAIN_MENU)
    if msg == "1" and has_services:
        return await self._show_catalog_service_list(phone, session, session_service, tenant_id, db, page=1)
    if msg == "1" and not has_services:
        session.step = self.CATALOG_STEP_CREATE_SERVICE_NAME
        await session_service.save_session(session)
        return self._t(self.KEY_CATALOG_CREATE_SERVICE_PROMPT)
    if msg == "2" and has_services:
        session.step = self.CATALOG_STEP_CREATE_SERVICE_NAME
        await session_service.save_session(session)
        return self._t(self.KEY_CATALOG_CREATE_SERVICE_PROMPT)
    if msg == "3" and has_services:
        return await self._show_catalog_delete_service_list(phone, session, session_service, tenant_id, db, page=1)
    return self._t(self.KEY_CATALOG_INVALID_SELECTION)
```

Add `_show_catalog_service_list()` and update `_handle_catalog_service_select()` to support `8` next, `9` back to Catalog menu, and page temp data. Use `session.temp_data["catalog_page"]`.

Update `_handle_catalog_service_select()` and `_handle_catalog_service_action()` so Catalog target IDs are stored in `session.temp_data`, not `session.selected_tenant_id`:

```python
session.temp_data["service_id"] = service_id
```

`_handle_catalog_service_action()` reads:

```python
service_id = session.temp_data.get("service_id")
```

Then route actions:

- `1` -> edit service
- `2` -> plan list or empty plans menu
- `3` -> create plan name step using `session.temp_data["service_id"]`
- `4` -> delete plan select list or no-plans-for-delete + Catalog menu
- `9` -> service list page 1

Update `_handle_catalog_plan_select()` so selected plan ID is stored as:

```python
session.temp_data["plan_id"] = plan_id
```

Update `_handle_catalog_edit_service()` and `_handle_catalog_edit_plan()` to read IDs from `session.temp_data["service_id"]` and `session.temp_data["plan_id"]`.

- keep same step on `UserFacingError` and `ValueError`
- after success call `_set_post_action()` instead of `_with_main_menu()`

Add `_handle_catalog_create_service_name()`, `_handle_catalog_create_plan_name()`, `_handle_catalog_empty_plan_menu()`, and `_handle_catalog_post_action()`:

```python
async def _handle_catalog_post_action(self, phone, msg, session, session_service, tenant_id, db):
    if msg == "1":
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._t(self.KEY_MAIN_MENU)
    return self._t(self.KEY_CATALOG_POST_SUCCESS_INVALID)
```

`0` is handled by `WhatsAppTenantConsoleService.process_message()` before active flow routing, so it returns goodbye and endpoint marks closed.

- [ ] **Step 6: Route and assign new handlers**

In `_routers.py`, add branches in `_route_catalog_flow()`:

```python
elif step == self.CATALOG_STEP_MENU:
    return await self._handle_catalog_menu(phone, msg, session, session_service, tenant_id, db)
elif step == self.CATALOG_STEP_CREATE_SERVICE_NAME:
    return await self._handle_catalog_create_service_name(phone, msg, session, session_service, tenant_id, db)
elif step == self.CATALOG_STEP_CREATE_PLAN_NAME:
    return await self._handle_catalog_create_plan_name(phone, msg, session, session_service, tenant_id, db)
elif step == self.CATALOG_STEP_EMPTY_PLAN_MENU:
    return await self._handle_catalog_empty_plan_menu(phone, msg, session, session_service, tenant_id, db)
elif step == self.CATALOG_STEP_POST_ACTION:
    return await self._handle_catalog_post_action(phone, msg, session, session_service, tenant_id, db)
```

In `_assignments.py`, assign:

```python
_handle_catalog_menu = caf._handle_catalog_menu
_show_catalog_service_list = caf._show_catalog_service_list
_handle_catalog_create_service_name = caf._handle_catalog_create_service_name
_handle_catalog_create_plan_name = caf._handle_catalog_create_plan_name
_handle_catalog_empty_plan_menu = caf._handle_catalog_empty_plan_menu
_handle_catalog_post_action = caf._handle_catalog_post_action
_catalog_menu_reply = caf._catalog_menu_reply
_set_post_action = caf._set_post_action
_paginate = staticmethod(caf._paginate)
_catalog_count = staticmethod(fmt._catalog_count)
_format_catalog_subscription_warning_row = staticmethod(fmt._format_catalog_subscription_warning_row)
```

- [ ] **Step 7: Run WhatsApp Catalog menu/create tests**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_console_service.py -k "catalog" -q
```

Expected: tests from this task PASS except delete-specific tests not yet added.

- [ ] **Step 8: Commit WhatsApp menu/create foundation**

```bash
git add backend/app/services/whatsapp_tenant_console_service/constants.py \
  backend/app/services/whatsapp_tenant_console_service/formatters.py \
  backend/app/services/whatsapp_tenant_console_service/catalog_flow.py \
  backend/app/services/whatsapp_tenant_console_service/_routers.py \
  backend/app/services/whatsapp_tenant_console_service/_assignments.py \
  backend/app/core/i18n/catalogs_es_wa.py \
  backend/app/core/i18n/catalogs_en_wa.py \
  backend/tests/test_tenant_console_service.py
git commit -m "feat(whatsapp): add catalog menu create and pagination flows"
```

---

## Task 4: WhatsApp delete service/plan warnings, pagination, confirmation, and close contract

**Files:**
- Create: `backend/app/services/whatsapp_tenant_console_service/catalog_delete_flow.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/constants.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/formatters.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/catalog_flow.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/_routers.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/_assignments.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Test: `backend/tests/test_tenant_console_service.py`
- Test: `backend/tests/test_whatsapp_endpoint.py`

- [x] **Step 1: Add failing delete flow tests**

In `backend/tests/test_tenant_console_service.py`, add a preview dataclass near fakes:

```python
@dataclass
class FakeDeletePagination:
    page: int = 1
    page_size: int = 7
    total_items: int = 0
    total_pages: int = 1
    has_next: bool = False


@dataclass
class FakeDeleteRow:
    id: UUID = field(default_factory=uuid4)
    streaming_email: str = "active@example.com"
    client_name: str = "Cliente Demo"
    client_phone: str = "584241234567"
    service_name: str = "Netflix"
    plan_name: str = "Premium"
    expires_at: datetime = field(default_factory=lambda: datetime(2026, 7, 1))


@dataclass
class FakeDeletePreview:
    target_type: str = "service"
    target_id: UUID = field(default_factory=uuid4)
    target_name: str = "Netflix"
    affected_plan_count: int = 0
    active_subscription_count: int = 0
    historical_subscription_count: int = 0
    total_subscription_count: int = 0
    active_subscriptions: list[FakeDeleteRow] = field(default_factory=list)
    pagination: FakeDeletePagination = field(default_factory=FakeDeletePagination)
    note: str = "Las suscripciones historicas tambien se eliminaran."
```

Add FakeCatalogService methods:

```python
async def get_service_delete_preview(self, db: Any, tenant_id: UUID, service_id: UUID, *, page: int = 1, page_size: int = 7) -> FakeDeletePreview | None:
    service = self._services.get(str(service_id))
    if service is None:
        return None
    rows = [FakeDeleteRow(service_name=service.name, plan_name="Premium")]
    return FakeDeletePreview(
        target_type="service",
        target_id=service.id,
        target_name=service.name,
        affected_plan_count=service.plan_count,
        active_subscription_count=service.active_subscription_count,
        historical_subscription_count=1,
        total_subscription_count=service.active_subscription_count + 1,
        active_subscriptions=rows[:page_size],
        pagination=FakeDeletePagination(page=page, page_size=page_size, total_items=len(rows), total_pages=1, has_next=False),
    )

async def get_plan_delete_preview(self, db: Any, tenant_id: UUID, service_id: UUID, plan_id: UUID, *, page: int = 1, page_size: int = 7) -> FakeDeletePreview | None:
    plan = self._plans.get(str(plan_id))
    if plan is None:
        return None
    rows = [FakeDeleteRow(plan_name=plan.name)] if plan.active_subscription_count else []
    return FakeDeletePreview(
        target_type="plan",
        target_id=plan.id,
        target_name=plan.name,
        affected_plan_count=0,
        active_subscription_count=plan.active_subscription_count,
        historical_subscription_count=0,
        total_subscription_count=plan.active_subscription_count,
        active_subscriptions=rows[:page_size],
        pagination=FakeDeletePagination(page=page, page_size=page_size, total_items=len(rows), total_pages=1, has_next=False),
    )

async def delete_service(self, db: Any, tenant_id: UUID, service_id: UUID, *, confirm: bool = False) -> FakeDeletePreview | None:
    if not confirm:
        raise UserFacingError("catalog_delete_confirmation_required")
    preview = await self.get_service_delete_preview(db, tenant_id, service_id)
    self._services.pop(str(service_id), None)
    return preview

async def delete_plan(self, db: Any, tenant_id: UUID, service_id: UUID, plan_id: UUID, *, confirm: bool = False) -> FakeDeletePreview | None:
    if not confirm:
        raise UserFacingError("catalog_delete_confirmation_required")
    preview = await self.get_plan_delete_preview(db, tenant_id, service_id, plan_id)
    self._plans.pop(str(plan_id), None)
    return preview
```

Add tests:

```python
async def test_delete_service_warning_requires_confirm_and_summarizes_cascade(
    self, console_service: WhatsAppTenantConsoleService, catalog_service: FakeCatalogService, session_service: WhatsAppSessionService
) -> None:
    tenant_id = uuid4()
    service = next(iter(catalog_service._services.values()))
    service.plan_count = 3
    service.active_subscription_count = 1
    await console_service.process_message("+10000000000", "2", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    await console_service.process_message("+10000000000", "3", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    warning = await console_service.process_message("+10000000000", "1", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    assert "Eliminar servicio" in warning
    assert "3" in warning and "planes" in warning
    assert "suscripciones" in warning
    assert "active@example.com - Cliente Demo - 584241234567 - Netflix/Premium" in warning
    assert "CONFIRMAR" in warning
    invalid = await console_service.process_message("+10000000000", "si", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    assert "CONFIRMAR" in invalid
    success = await console_service.process_message("+10000000000", "confirmar", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    assert "Servicio" in success and "eliminado" in success
    assert "3 planes" in success
    assert "2 suscripciones" in success


async def test_delete_plan_no_plans_returns_to_catalog_menu(
    self, console_service: WhatsAppTenantConsoleService, catalog_service: FakeCatalogService, session_service: WhatsAppSessionService
) -> None:
    tenant_id = uuid4()
    catalog_service._plans.clear()
    await console_service.process_message("+10000000000", "2", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    await console_service.process_message("+10000000000", "1", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    await console_service.process_message("+10000000000", "1", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    reply = await console_service.process_message("+10000000000", "4", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    assert "no tiene planes" in reply.lower()
    assert "Cat" in reply


async def test_delete_plan_warning_and_confirm(
    self, console_service: WhatsAppTenantConsoleService, catalog_service: FakeCatalogService, session_service: WhatsAppSessionService
) -> None:
    tenant_id = uuid4()
    service = next(iter(catalog_service._services.values()))
    plan = FakePlanObj(service_id=service.id, name="Premium", active_subscription_count=1)
    catalog_service._plans[str(plan.id)] = plan
    await console_service.process_message("+10000000000", "2", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    await console_service.process_message("+10000000000", "1", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    await console_service.process_message("+10000000000", "1", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    await console_service.process_message("+10000000000", "4", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    warning = await console_service.process_message("+10000000000", "1", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    assert "Eliminar plan" in warning
    assert "Premium" in warning
    success = await console_service.process_message("+10000000000", "CONFIRM", tenant_id=tenant_id, db=cast(AsyncSession, object()), session_service=session_service)
    assert "Plan" in success and "eliminado" in success
```

Add or update endpoint test in `backend/tests/test_whatsapp_endpoint.py` near close-jid contract tests:

```python
async def test_tenant_catalog_zero_sets_closed_response_with_close_jid(client, active_tenant_user):
    headers = {"X-API-Key": "test-n8n-key"}
    payload = {
        "instance": "tenant-instance",
        "message": {"conversation": "0"},
        "key": {"remoteJid": "12015550002@s.whatsapp.net", "fromMe": False},
        "sender": "12015550002@s.whatsapp.net",
        "senderPn": "12015550002@s.whatsapp.net",
    }
    response = await client.post("/api/v1/integrations/whatsapp/console", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "closed"
    assert body.get("close_jid") == "12015550002@s.whatsapp.net"
```

If the existing endpoint payload shape differs, use the nearest existing tenant-console close test payload and only change message to `0`.

- [x] **Step 2: Run failing delete flow tests**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_console_service.py -k "delete_service or delete_plan or catalog" -q
```

Expected: FAIL because delete handlers and i18n keys do not exist.

- [x] **Step 3: Add delete i18n keys**

Add ES keys:

```python
"wa.tenant.catalog.delete_service_prompt": "Responde con el numero del servicio que deseas eliminar.",
"wa.tenant.catalog.delete_plan_prompt": "Responde con el numero del plan que deseas eliminar.",
"wa.tenant.catalog.delete_confirm_reprompt": "❌ Para confirmar, escribe *CONFIRMAR* o *CONFIRM*. Escribe *0* para cancelar.",
"wa.tenant.catalog.delete_service_success": "✅ Servicio *{name}* eliminado exitosamente.",
"wa.tenant.catalog.delete_plan_success": "✅ Plan *{name}* eliminado exitosamente.",
"wa.tenant.catalog.delete_summary": "\n\nTambien se eliminaron:\n- {plans}\n- {subscriptions}",
"wa.tenant.catalog.delete_service_zero_subscriptions": "El servicio *{name}* tiene {plans} asociados.\nNo tiene suscripciones activas asociadas.\nNo tiene suscripciones historicas asociadas.\n\nSi confirmas, se eliminaran:\n- El servicio\n- {plans} asociados",
"wa.tenant.catalog.delete_plan_zero_subscriptions": "El plan *{name}* no tiene suscripciones asociadas.\n\nSi confirmas, se eliminara:\n- El plan",
"wa.tenant.catalog.count.subscription.one": "1 suscripcion asociada",
"wa.tenant.catalog.count.subscription.other": "{count} suscripciones asociadas",
"wa.tenant.catalog.delete_note": "Las suscripciones historicas, expiradas y canceladas asociadas tambien se eliminaran, aunque no aparezcan en la lista.",
```

Add English equivalents using `CONFIRM`, `service deleted successfully`, `plan deleted successfully`, and `Historical, expired, and cancelled subscriptions will also be deleted even when they are not listed.`

- [x] **Step 4: Add delete formatting helpers**

In `formatters.py`, add:

```python
def _format_catalog_subscription_warning_row(row: Any) -> str:
    expires = getattr(row, "expires_at", None)
    if hasattr(expires, "strftime"):
        expires_text = expires.strftime("%Y-%m-%d")
    else:
        expires_text = str(expires or "—")
    return (
        f"{row.streaming_email} - {row.client_name or '—'} - {row.client_phone or '—'} - "
        f"{row.service_name}/{row.plan_name} - expira {expires_text}"
    )
```

Use this helper from `catalog_delete_flow.py`.

- [x] **Step 5: Create delete flow module**

Create `backend/app/services/whatsapp_tenant_console_service/catalog_delete_flow.py`:

```python
"""Catalog delete warning and confirmation flow handlers."""

from __future__ import annotations

from app.services.whatsapp_navigation import is_back, is_next

CONFIRM_WORDS = {"confirmar", "confirm"}


def _is_confirm(msg: str) -> bool:
    return msg.strip().lower() in CONFIRM_WORDS


async def _show_catalog_delete_service_list(self, phone, session, session_service, tenant_id, db, page: int = 1):
    services = []
    if tenant_id is not None and db is not None and self._catalog_service is not None:
        services = await self._catalog_service.list_service_summaries(db, tenant_id)
    if not services:
        return await self._catalog_menu_reply(tenant_id, db)
    page_items, page, total_pages = self._paginate(services, page, self.CATALOG_PAGE_SIZE)
    reply, selection_map = self._format_service_list(page_items, page=page, total_pages=total_pages)
    session.flow = self.CATALOG_FLOW
    session.step = self.CATALOG_STEP_DELETE_SERVICE_SELECT
    session.selection_map = selection_map
    session.temp_data["catalog_page"] = str(page)
    if session_service is not None:
        await session_service.save_session(session)
    return reply + "\n\n" + self._t("wa.tenant.catalog.delete_service_prompt")


async def _handle_catalog_delete_service_select(self, phone, msg, session, session_service, tenant_id, db):
    if is_next(msg):
        return await self._show_catalog_delete_service_list(phone, session, session_service, tenant_id, db, int(session.temp_data.get("catalog_page", "1")) + 1)
    if is_back(msg):
        session.step = self.CATALOG_STEP_MENU
        await session_service.save_session(session)
        return await self._catalog_menu_reply(tenant_id, db)
    service_id = session.selection_map.get(msg)
    parsed_service_id = self._safe_uuid(service_id)
    if parsed_service_id is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    session.step = self.CATALOG_STEP_DELETE_SERVICE_CONFIRM
    session.temp_data["delete_service_id"] = str(parsed_service_id)
    session.temp_data["delete_page"] = "1"
    await session_service.save_session(session)
    return await self._render_service_delete_warning(session, tenant_id, db, page=1)


async def _render_service_delete_warning(self, session, tenant_id, db, page: int = 1):
    service_id = self._safe_uuid(session.temp_data.get("delete_service_id"))
    if service_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    preview = await self._catalog_service.get_service_delete_preview(db, tenant_id, service_id, page=page, page_size=self.CATALOG_PAGE_SIZE)
    if preview is None:
        return self._t("wa.tenant.errors.service_not_found")
    plan_label = self._catalog_count('wa.tenant.catalog.count.plan', preview.affected_plan_count)
    if preview.total_subscription_count == 0:
        lines = [
            "⚠️ *Eliminar servicio*",
            "",
            self._t("wa.tenant.catalog.delete_service_zero_subscriptions", name=preview.target_name, plans=plan_label),
        ]
    else:
        lines = [
            "⚠️ *Eliminar servicio*",
            "",
            f"El servicio *{preview.target_name}* tiene {plan_label} asociados.",
            f"Suscripciones activas: {preview.active_subscription_count}",
            f"Suscripciones historicas/no activas: {preview.historical_subscription_count}",
            f"Total afectado: {preview.total_subscription_count}",
            "",
            self._t("wa.tenant.catalog.delete_note"),
        ]
    if preview.active_subscriptions:
        lines.append("")
        lines.extend(self._format_catalog_subscription_warning_row(row) for row in preview.active_subscriptions)
    lines.extend(["", "Escribe *CONFIRMAR* para eliminar o *0* para cancelar."])
    if preview.pagination.has_next:
        lines.append(self._t("wa.nav.next"))
    lines.append(self._t("wa.nav.back"))
    return "\n".join(lines)


async def _handle_catalog_delete_service_confirm(self, phone, msg, session, session_service, tenant_id, db):
    if is_next(msg):
        page = int(session.temp_data.get("delete_page", "1")) + 1
        session.temp_data["delete_page"] = str(page)
        await session_service.save_session(session)
        return await self._render_service_delete_warning(session, tenant_id, db, page=page)
    if is_back(msg):
        return await self._show_catalog_delete_service_list(phone, session, session_service, tenant_id, db, page=1)
    if not _is_confirm(msg):
        return self._t("wa.tenant.catalog.delete_confirm_reprompt")
    service_id = self._safe_uuid(session.temp_data.get("delete_service_id"))
    if service_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    preview = await self._catalog_service.delete_service(db, tenant_id, service_id, confirm=True)
    if preview is None:
        return self._t("wa.tenant.errors.service_not_found")
    message = self._t("wa.tenant.catalog.delete_service_success", name=preview.target_name)
    if preview.affected_plan_count or preview.total_subscription_count:
        message += self._t(
            "wa.tenant.catalog.delete_summary",
            plans=self._catalog_count("wa.tenant.catalog.count.plan", preview.affected_plan_count),
            subscriptions=self._catalog_count("wa.tenant.catalog.count.subscription", preview.total_subscription_count),
        )
    return await self._set_post_action(phone, session_service, message)
```

Add plan delete handlers in same file:

```python
async def _show_catalog_delete_plan_list(self, phone, session, session_service, tenant_id, db, page: int = 1):
    service_id = self._safe_uuid(session.temp_data.get("service_id"))
    if service_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    plans = await self._catalog_service.list_plan_summaries(db, tenant_id, service_id)
    if not plans:
        session.step = self.CATALOG_STEP_MENU
        await session_service.save_session(session)
        return self._t(self.KEY_CATALOG_NO_PLANS_FOR_DELETE) + "\n\n" + await self._catalog_menu_reply(tenant_id, db)
    page_items, page, total_pages = self._paginate(plans, page, self.CATALOG_PAGE_SIZE)
    reply, selection_map = self._format_plan_list(page_items, page=page, total_pages=total_pages)
    session.flow = self.CATALOG_FLOW
    session.step = self.CATALOG_STEP_DELETE_PLAN_SELECT
    session.selection_map = selection_map
    session.temp_data["delete_service_id"] = str(service_id)
    session.temp_data["catalog_page"] = str(page)
    await session_service.save_session(session)
    return reply + "\n\n" + self._t("wa.tenant.catalog.delete_plan_prompt")


async def _handle_catalog_delete_plan_select(self, phone, msg, session, session_service, tenant_id, db):
    if is_next(msg):
        return await self._show_catalog_delete_plan_list(phone, session, session_service, tenant_id, db, int(session.temp_data.get("catalog_page", "1")) + 1)
    if is_back(msg):
        service_id = self._safe_uuid(session.temp_data.get("delete_service_id"))
        if service_id is None or tenant_id is None or db is None or self._catalog_service is None:
            session.step = self.CATALOG_STEP_MENU
            await session_service.save_session(session)
            return await self._catalog_menu_reply(tenant_id, db)
        service = await self._catalog_service.get_service(db, tenant_id, service_id)
        if service is None:
            session.step = self.CATALOG_STEP_MENU
            await session_service.save_session(session)
            return await self._catalog_menu_reply(tenant_id, db)
        session.step = self.CATALOG_STEP_SERVICE_ACTION
        session.temp_data["service_id"] = str(service_id)
        await session_service.save_session(session)
        return self._format_service_detail(service) + "\n" + self._t(self.KEY_CATALOG_SERVICE_ACTIONS)
    plan_id = session.selection_map.get(msg)
    parsed_plan_id = self._safe_uuid(plan_id)
    if parsed_plan_id is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    session.step = self.CATALOG_STEP_DELETE_PLAN_CONFIRM
    session.temp_data["delete_plan_id"] = str(parsed_plan_id)
    session.temp_data["delete_page"] = "1"
    await session_service.save_session(session)
    return await self._render_plan_delete_warning(session, tenant_id, db, page=1)


async def _render_plan_delete_warning(self, session, tenant_id, db, page: int = 1):
    service_id = self._safe_uuid(session.temp_data.get("delete_service_id"))
    plan_id = self._safe_uuid(session.temp_data.get("delete_plan_id"))
    if service_id is None or plan_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    preview = await self._catalog_service.get_plan_delete_preview(db, tenant_id, service_id, plan_id, page=page, page_size=self.CATALOG_PAGE_SIZE)
    if preview is None:
        return self._t("wa.tenant.errors.plan_not_found")
    if preview.total_subscription_count == 0:
        lines = [
            "⚠️ *Eliminar plan*",
            "",
            self._t("wa.tenant.catalog.delete_plan_zero_subscriptions", name=preview.target_name),
        ]
    else:
        lines = [
            "⚠️ *Eliminar plan*",
            "",
            f"El plan *{preview.target_name}* tiene suscripciones asociadas.",
            f"Suscripciones activas: {preview.active_subscription_count}",
            f"Suscripciones historicas/no activas: {preview.historical_subscription_count}",
            f"Total afectado: {preview.total_subscription_count}",
            "",
            self._t("wa.tenant.catalog.delete_note"),
        ]
    if preview.active_subscriptions:
        lines.append("")
        lines.extend(self._format_catalog_subscription_warning_row(row) for row in preview.active_subscriptions)
    lines.extend(["", "Escribe *CONFIRMAR* para eliminar o *0* para cancelar."])
    if preview.pagination.has_next:
        lines.append(self._t("wa.nav.next"))
    lines.append(self._t("wa.nav.back"))
    return "\n".join(lines)


async def _handle_catalog_delete_plan_confirm(self, phone, msg, session, session_service, tenant_id, db):
    if is_next(msg):
        page = int(session.temp_data.get("delete_page", "1")) + 1
        session.temp_data["delete_page"] = str(page)
        await session_service.save_session(session)
        return await self._render_plan_delete_warning(session, tenant_id, db, page=page)
    if is_back(msg):
        return await self._show_catalog_delete_plan_list(phone, session, session_service, tenant_id, db, page=1)
    if not _is_confirm(msg):
        return self._t("wa.tenant.catalog.delete_confirm_reprompt")
    service_id = self._safe_uuid(session.temp_data.get("delete_service_id"))
    plan_id = self._safe_uuid(session.temp_data.get("delete_plan_id"))
    if service_id is None or plan_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    preview = await self._catalog_service.delete_plan(db, tenant_id, service_id, plan_id, confirm=True)
    if preview is None:
        return self._t("wa.tenant.errors.plan_not_found")
    message = self._t("wa.tenant.catalog.delete_plan_success", name=preview.target_name)
    if preview.total_subscription_count:
        message += self._t(
            "wa.tenant.catalog.delete_summary",
            plans=self._catalog_count("wa.tenant.catalog.count.plan", 0),
            subscriptions=self._catalog_count("wa.tenant.catalog.count.subscription", preview.total_subscription_count),
        )
    return await self._set_post_action(phone, session_service, message)
```

- [x] **Step 6: Wire delete handlers**

In `_assignments.py`:

```python
from . import catalog_delete_flow as cdf
_show_catalog_delete_service_list = cdf._show_catalog_delete_service_list
_handle_catalog_delete_service_select = cdf._handle_catalog_delete_service_select
_render_service_delete_warning = cdf._render_service_delete_warning
_handle_catalog_delete_service_confirm = cdf._handle_catalog_delete_service_confirm
_show_catalog_delete_plan_list = cdf._show_catalog_delete_plan_list
_handle_catalog_delete_plan_select = cdf._handle_catalog_delete_plan_select
_render_plan_delete_warning = cdf._render_plan_delete_warning
_handle_catalog_delete_plan_confirm = cdf._handle_catalog_delete_plan_confirm
```

In `_routers.py`, route:

```python
elif step == self.CATALOG_STEP_DELETE_SERVICE_SELECT:
    return await self._handle_catalog_delete_service_select(phone, msg, session, session_service, tenant_id, db)
elif step == self.CATALOG_STEP_DELETE_SERVICE_CONFIRM:
    return await self._handle_catalog_delete_service_confirm(phone, msg, session, session_service, tenant_id, db)
elif step == self.CATALOG_STEP_DELETE_PLAN_SELECT:
    return await self._handle_catalog_delete_plan_select(phone, msg, session, session_service, tenant_id, db)
elif step == self.CATALOG_STEP_DELETE_PLAN_CONFIRM:
    return await self._handle_catalog_delete_plan_confirm(phone, msg, session, session_service, tenant_id, db)
```

- [x] **Step 7: Run delete and endpoint tests**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_console_service.py -k "catalog" -q
cd backend && uv run pytest tests/test_whatsapp_endpoint.py -k "close_jid or catalog_zero" -q
```

Expected: PASS.

- [x] **Step 8: Commit WhatsApp delete flows**

```bash
git add backend/app/services/whatsapp_tenant_console_service/catalog_delete_flow.py \
  backend/app/services/whatsapp_tenant_console_service/constants.py \
  backend/app/services/whatsapp_tenant_console_service/formatters.py \
  backend/app/services/whatsapp_tenant_console_service/catalog_flow.py \
  backend/app/services/whatsapp_tenant_console_service/_routers.py \
  backend/app/services/whatsapp_tenant_console_service/_assignments.py \
  backend/app/core/i18n/catalogs_es_wa.py \
  backend/app/core/i18n/catalogs_en_wa.py \
  backend/tests/test_tenant_console_service.py \
  backend/tests/test_whatsapp_endpoint.py
git commit -m "feat(whatsapp): add catalog delete confirmation flows"
```

---

## Task 5: Dashboard preview modal, frontend i18n, and frontend helper tests

**Files:**
- Create: `frontend/src/components/catalogDeletePreview.js`
- Create: `frontend/src/components/__tests__/catalogDeletePreview.spec.js`
- Modify: `frontend/src/components/CatalogPanel.vue`
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py`

- [x] **Step 1: Add frontend helper tests first**

Create directory:

```bash
mkdir -p frontend/src/components/__tests__
```

Create `frontend/src/components/__tests__/catalogDeletePreview.spec.js`:

```javascript
import { describe, expect, it } from 'vitest'
import { formatCount, formatPreviewRow, isDeleteConfirmationValid } from '../catalogDeletePreview'

describe('catalog delete preview helpers', () => {
  it('accepts CONFIRM and CONFIRMAR case-insensitively', () => {
    expect(isDeleteConfirmationValid('CONFIRM')).toBe(true)
    expect(isDeleteConfirmationValid(' confirmar ')).toBe(true)
    expect(isDeleteConfirmationValid('delete')).toBe(false)
  })

  it('formats singular and plural counts through i18n keys', () => {
    const t = (key, params) => `${key}:${params?.count ?? ''}`
    expect(formatCount(t, 1, 'frontend.catalog.plan_one', 'frontend.catalog.plan_other')).toBe('frontend.catalog.plan_one:1')
    expect(formatCount(t, 3, 'frontend.catalog.plan_one', 'frontend.catalog.plan_other')).toBe('frontend.catalog.plan_other:3')
  })

  it('formats preview rows without throwing on missing phone', () => {
    const row = formatPreviewRow({
      streaming_email: 'active@example.com',
      client_name: 'Cliente Demo',
      client_phone: null,
      service_name: 'Netflix',
      plan_name: 'Premium',
      expires_at: '2026-07-15T00:00:00Z',
    })
    expect(row).toContain('active@example.com')
    expect(row).toContain('Cliente Demo')
    expect(row).toContain('Netflix/Premium')
    expect(row).toContain('2026-07-15')
  })
})
```

- [x] **Step 2: Run failing frontend helper tests**

Run:

```bash
cd frontend && npm test -- catalogDeletePreview
```

Expected: FAIL because `catalogDeletePreview.js` does not exist.

- [x] **Step 3: Add frontend helper module**

Create `frontend/src/components/catalogDeletePreview.js`:

```javascript
export function isDeleteConfirmationValid(value) {
  const normalized = String(value || '').trim().toLowerCase()
  return normalized === 'confirmar' || normalized === 'confirm'
}

export function formatCount(t, count, oneKey, otherKey) {
  return t(count === 1 ? oneKey : otherKey, { count })
}

export function formatPreviewRow(row) {
  const expires = row.expires_at ? String(row.expires_at).slice(0, 10) : '—'
  return `${row.streaming_email} - ${row.client_name || '—'} - ${row.client_phone || '—'} - ${row.service_name}/${row.plan_name} - ${expires}`
}
```

- [x] **Step 4: Add frontend i18n keys**

Add ES frontend keys near existing `frontend.catalog.*` keys:

```python
"frontend.catalog.delete_preview_title_service": "Eliminar servicio",
"frontend.catalog.delete_preview_title_plan": "Eliminar plan",
"frontend.catalog.delete_preview_loading": "Cargando vista previa...",
"frontend.catalog.delete_preview_note": "Las suscripciones historicas, expiradas y canceladas tambien se eliminaran aunque no aparezcan en la lista.",
"frontend.catalog.affected_plans": "Planes afectados",
"frontend.catalog.active_subscriptions": "Suscripciones activas",
"frontend.catalog.historical_subscriptions": "Suscripciones historicas/no activas",
"frontend.catalog.total_subscriptions": "Suscripciones totales afectadas",
"frontend.catalog.plan_one": "1 plan",
"frontend.catalog.plan_other": "{count} planes",
"frontend.catalog.subscription_one": "1 suscripcion",
"frontend.catalog.subscription_other": "{count} suscripciones",
"frontend.catalog.confirm_label": "Escribe CONFIRMAR o CONFIRM para confirmar",
"frontend.catalog.confirm_placeholder": "CONFIRMAR",
"frontend.catalog.preview_prev": "Anterior",
"frontend.catalog.preview_next": "Siguiente",
"frontend.catalog.cancel_delete": "Cancelar",
"frontend.catalog.confirm_delete": "Eliminar definitivamente",
"frontend.catalog.deleting": "Eliminando...",
"frontend.catalog.no_active_rows": "No hay suscripciones activas para mostrar.",
```

Add English equivalents with `Delete service`, `Delete plan`, `Historical, expired, and cancelled subscriptions will also be deleted even when they are not listed.`, `Type CONFIRMAR or CONFIRM to confirm`, `Delete permanently`.

- [x] **Step 5: Replace `window.confirm` in CatalogPanel.vue**

In `frontend/src/components/CatalogPanel.vue`:

1. Add import:

```javascript
import { computed, onMounted, ref } from 'vue'
import { formatCount, formatPreviewRow, isDeleteConfirmationValid } from './catalogDeletePreview'
```

2. Add state:

```javascript
const deletePreview = ref(null)
const deleteTarget = ref(null)
const deleteConfirmText = ref('')
const deletePage = ref(1)
const isDeleteLoading = ref(false)
const isDeleting = ref(false)
const canConfirmDelete = computed(() => isDeleteConfirmationValid(deleteConfirmText.value))
```

3. Add helpers:

```javascript
function closeDeleteModal() {
  deletePreview.value = null
  deleteTarget.value = null
  deleteConfirmText.value = ''
  deletePage.value = 1
  isDeleteLoading.value = false
  isDeleting.value = false
}

function deletePreviewTitle() {
  if (!deleteTarget.value) return ''
  return i18nStore.t(deleteTarget.value.type === 'service'
    ? 'frontend.catalog.delete_preview_title_service'
    : 'frontend.catalog.delete_preview_title_plan')
}

function countText(count, oneKey, otherKey) {
  return formatCount(i18nStore.t, count, oneKey, otherKey)
}

async function loadDeletePreview(page = 1) {
  if (!deleteTarget.value) return
  isDeleteLoading.value = true
  errorMessage.value = ''
  try {
    const url = deleteTarget.value.type === 'service'
      ? `/catalog/services/${deleteTarget.value.serviceId}/delete-preview?page=${page}&page_size=10`
      : `/catalog/services/${selectedServiceId.value}/plans/${deleteTarget.value.planId}/delete-preview?page=${page}&page_size=10`
    const response = await api.get(url)
    deletePreview.value = response.data
    deletePage.value = page
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_delete_service'))
    closeDeleteModal()
  } finally {
    isDeleteLoading.value = false
  }
}

async function openDeleteService(service) {
  catalogMessage.value = ''
  errorMessage.value = ''
  deleteTarget.value = { type: 'service', serviceId: service.id, name: service.name }
  await loadDeletePreview(1)
}

async function openDeletePlan(plan) {
  catalogMessage.value = ''
  errorMessage.value = ''
  deleteTarget.value = { type: 'plan', planId: plan.id, name: plan.name }
  await loadDeletePreview(1)
}

async function confirmDelete() {
  if (!deleteTarget.value || !canConfirmDelete.value) return
  isDeleting.value = true
  try {
    const url = deleteTarget.value.type === 'service'
      ? `/catalog/services/${deleteTarget.value.serviceId}?confirm=true`
      : `/catalog/services/${selectedServiceId.value}/plans/${deleteTarget.value.planId}?confirm=true`
    await api.delete(url)
    if (deleteTarget.value.type === 'service' && selectedServiceId.value === deleteTarget.value.serviceId) selectedServiceId.value = ''
    closeDeleteModal()
    await loadServices()
    if (selectedServiceId.value) await loadPlans()
  } catch (error) {
    errorMessage.value = getApiError(error, deleteTarget.value.type === 'service'
      ? i18nStore.t('frontend.catalog.error_delete_service')
      : i18nStore.t('frontend.catalog.error_delete_plan'))
  } finally {
    isDeleting.value = false
  }
}
```

4. Replace button handlers:

```vue
@click="openDeleteService(service)"
@click="openDeletePlan(plan)"
```

5. Add modal before closing `</section>`:

```vue
<div v-if="deleteTarget" class="modal-overlay" @click.self="closeDeleteModal">
  <div class="modal">
    <div class="modal-header">
      <h2>{{ deletePreviewTitle() }}</h2>
      <button class="modal-close" type="button" @click="closeDeleteModal">✕</button>
    </div>
    <div class="modal-body">
      <p v-if="isDeleteLoading">{{ i18nStore.t('frontend.catalog.delete_preview_loading') }}</p>
      <template v-else-if="deletePreview">
        <p><strong>{{ deletePreview.target_name }}</strong></p>
        <ul class="preview-counts">
          <li v-if="deletePreview.target_type === 'service'">{{ i18nStore.t('frontend.catalog.affected_plans') }}: {{ countText(deletePreview.affected_plan_count, 'frontend.catalog.plan_one', 'frontend.catalog.plan_other') }}</li>
          <li>{{ i18nStore.t('frontend.catalog.active_subscriptions') }}: {{ countText(deletePreview.active_subscription_count, 'frontend.catalog.subscription_one', 'frontend.catalog.subscription_other') }}</li>
          <li>{{ i18nStore.t('frontend.catalog.historical_subscriptions') }}: {{ countText(deletePreview.historical_subscription_count, 'frontend.catalog.subscription_one', 'frontend.catalog.subscription_other') }}</li>
          <li>{{ i18nStore.t('frontend.catalog.total_subscriptions') }}: {{ countText(deletePreview.total_subscription_count, 'frontend.catalog.subscription_one', 'frontend.catalog.subscription_other') }}</li>
        </ul>
        <p class="warning-note">{{ i18nStore.t('frontend.catalog.delete_preview_note') }}</p>
        <ul v-if="deletePreview.active_subscriptions?.length" class="preview-rows">
          <li v-for="row in deletePreview.active_subscriptions" :key="row.id">{{ formatPreviewRow(row) }}</li>
        </ul>
        <p v-else>{{ i18nStore.t('frontend.catalog.no_active_rows') }}</p>
        <div class="pagination-actions" v-if="deletePreview.pagination?.total_pages > 1">
          <button class="button button-secondary" type="button" :disabled="deletePage <= 1 || isDeleteLoading" @click="loadDeletePreview(deletePage - 1)">{{ i18nStore.t('frontend.catalog.preview_prev') }}</button>
          <button class="button button-secondary" type="button" :disabled="!deletePreview.pagination.has_next || isDeleteLoading" @click="loadDeletePreview(deletePage + 1)">{{ i18nStore.t('frontend.catalog.preview_next') }}</button>
        </div>
        <label>{{ i18nStore.t('frontend.catalog.confirm_label') }}<input v-model.trim="deleteConfirmText" type="text" :placeholder="i18nStore.t('frontend.catalog.confirm_placeholder')" /></label>
      </template>
    </div>
    <div class="modal-footer">
      <button class="button button-secondary" type="button" @click="closeDeleteModal">{{ i18nStore.t('frontend.catalog.cancel_delete') }}</button>
      <button class="button button-primary danger-action" type="button" :disabled="!canConfirmDelete || isDeleting" @click="confirmDelete">{{ isDeleting ? i18nStore.t('frontend.catalog.deleting') : i18nStore.t('frontend.catalog.confirm_delete') }}</button>
    </div>
  </div>
</div>
```

6. Add scoped styles matching existing dashboard modal pattern:

```css
.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: var(--card-bg, #fff); border-radius: 16px; width: min(92vw, 620px); max-height: 90vh; overflow-y: auto; box-shadow: 0 25px 50px rgba(15, 23, 42, 0.25); }
.modal-header, .modal-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 20px 24px; }
.modal-body { padding: 0 24px 20px; display: grid; gap: 14px; }
.modal-close { border: 0; background: transparent; cursor: pointer; font-size: 1.25rem; }
.preview-counts, .preview-rows { margin: 0; padding-left: 20px; }
.warning-note { color: var(--danger, #ef4444); font-weight: 600; }
.pagination-actions { display: flex; gap: 8px; }
.danger-action { background: var(--danger, #ef4444); }
```

- [x] **Step 6: Run frontend tests and build**

Run:

```bash
cd frontend && npm test -- catalogDeletePreview
cd frontend && npm test
cd frontend && npm run build
```

Expected: PASS.

- [x] **Step 7: Commit dashboard changes**

```bash
git add frontend/src/components/catalogDeletePreview.js \
  frontend/src/components/__tests__/catalogDeletePreview.spec.js \
  frontend/src/components/CatalogPanel.vue \
  backend/app/core/i18n/catalogs_es_frontend.py \
  backend/app/core/i18n/catalogs_en_frontend.py
git commit -m "feat(frontend): add catalog delete preview modal"
```

---

## Task 6: Docs refresh and full verification

**Files:**
- Modify: `docs/architecture/api-layer.md`
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Modify: `docs/codebase/frontend-components.md`
- Modify: `docs/SUMMARY.md`

- [x] **Step 1: Update API docs**

In `docs/architecture/api-layer.md`, update Catalog Endpoints list to include:

```markdown
- `GET /api/v1/catalog/services/{service_id}/delete-preview?page=1&page_size=10` — Preview cascade impact before deleting a service. Returns affected plan count, active/historical/total subscription counts, note, and paginated active subscription rows.
- `DELETE /api/v1/catalog/services/{service_id}?confirm=true` — Confirmed cascade delete for a service, its plans, and all related subscriptions. Without `confirm=true`, returns 400.
- `GET /api/v1/catalog/services/{service_id}/plans/{plan_id}/delete-preview?page=1&page_size=10` — Preview cascade impact before deleting a plan.
- `DELETE /api/v1/catalog/services/{service_id}/plans/{plan_id}?confirm=true` — Confirmed cascade delete for a plan and all related subscriptions. Without `confirm=true`, returns 400.
```

Add note:

```markdown
Active subscription counts use `status == "active"` only. Services and plans have no active/inactive lifecycle; existing rows count as active catalog items.
```

- [x] **Step 2: Update WhatsApp flow docs**

In `docs/architecture/whatsapp-console-flow.md`, update Tenant Console Catalog section/table so option 2 says:

```markdown
| 2 | Catálogo | Service/plan CRUD. Starts with Catalog menu, supports service/plan list pagination (`8` next, `9` back, `0` close), direct create/edit, and destructive delete warnings requiring `CONFIRMAR`/`CONFIRM`. |
```

Add short paragraph:

```markdown
Catalog delete warnings list active subscriptions ordered by expiration date and state that historical/non-active subscriptions are also deleted. `0` in Catalog closes the WhatsApp session and relies on the endpoint response contract (`status="closed"`, `close_jid`) for Evolution/n8n session closure.
```

- [x] **Step 3: Update frontend component docs**

In `docs/codebase/frontend-components.md`, update `CatalogPanel` bullets:

```markdown
- Creates and renames services and plans.
- Deletes services/plans through REST preview + typed confirmation modal (`CONFIRMAR` or `CONFIRM`).
- Preview modal shows affected plan count, active/historical/total subscription counts, and active subscription rows paginated at 10/page.
```

- [x] **Step 4: Update docs summary wording**

In `docs/SUMMARY.md`, adjust the Frontend Components description if needed:

```markdown
| [Frontend Components](codebase/frontend-components.md) | Reusable panels, including Catalog CRUD with delete preview confirmation, and their responsibilities |
```

If this exact table row is not present, update the existing `Frontend Components` row with equivalent wording.

- [x] **Step 5: Run full backend verification**

Run:

```bash
cd backend && uv run pytest
```

Expected: PASS.

- [x] **Step 6: Run full frontend verification**

Run:

```bash
cd frontend && npm test
cd frontend && npm run build
```

Expected: PASS.

- [x] **Step 7: Run formatting/lint if available without expanding scope**

Run backend Ruff commands documented by `AGENTS.md`:

```bash
cd backend && uv run ruff check .
cd backend && uv run ruff format --check .
```

Expected: PASS. If Ruff is not installed in the environment, record exact command failure in PR notes and do not change tooling.

- [x] **Step 8: Commit docs and verification fixes**

```bash
git add docs/architecture/api-layer.md \
  docs/architecture/whatsapp-console-flow.md \
  docs/codebase/frontend-components.md \
  docs/SUMMARY.md
git commit -m "docs: document catalog delete preview flow"
```

If verification required small code fixes, include only files changed by those fixes in same commit when they directly support passing tests; otherwise create a separate `fix:` commit.

---

## Task 7: Draft PR preparation

**Files:**
- No code files unless PR command requires a generated template file.

- [ ] **Step 1: Inspect final diff and commit history**

Run:

```bash
git status --short
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
```

Expected:

- working tree clean except intentionally untracked `trackpal_codex_catalog_crud_prompt.md`
- multiple logical commits
- diff covers backend/API, WhatsApp/i18n, frontend, docs, tests

- [ ] **Step 2: Push branch**

Run:

```bash
git push -u origin feature/43-catalog-crud-whatsapp-dashboard
```

Expected: branch pushed.

- [ ] **Step 3: Open Draft PR linked to GitHub #43 and Linear TPL-6**

Run:

```bash
gh pr create --draft \
  --base main \
  --head feature/43-catalog-crud-whatsapp-dashboard \
  --title "feat: add catalog CRUD delete previews" \
  --body-file /tmp/trackpal-catalog-crud-pr.md
```

Before running, create `/tmp/trackpal-catalog-crud-pr.md` with this structure and actual verification output:

```markdown
## Summary

Implements GitHub #43 / Linear TPL-6: tenant Catalog CRUD for services and plans across WhatsApp Tenant Console, REST/dashboard, and docs.

## Backend service/repository/API

- [ ] Added service/plan delete preview endpoints.
- [ ] Gated service/plan DELETE endpoints with `confirm=true`.
- [ ] Added cascade preview counts for plans, active subscriptions, historical/non-active subscriptions, and totals.
- [ ] Preserved tenant scoping and existing `/catalog` route convention.

Cascade strategy: service-layer explicit deletion of related subscriptions before deleting service/plan, relying on existing model/DB cascade for remaining service-plan relationships and subscription child rows.

## WhatsApp Catalog flow + i18n

- [ ] Catalog starts with menu and empty menu variant.
- [ ] Service/plan lists paginate at 7 items/page and show counts with singular/plural labels.
- [ ] Create/edit service/plan flows update directly after name input.
- [ ] Delete service/plan warnings require `CONFIRMAR` or `CONFIRM` and include active/historical/total counts.
- [ ] New ES/EN WhatsApp strings added.

## Frontend dashboard

- [ ] Extended existing `CatalogPanel.vue`.
- [ ] Replaced `window.confirm` with preview modal and typed confirmation.
- [ ] Added frontend i18n keys and helper tests.

## Tests

- [ ] `cd backend && uv run pytest` — PASS
- [ ] `cd frontend && npm test` — PASS
- [ ] `cd frontend && npm run build` — PASS
- [ ] `cd backend && uv run ruff check .` — PASS or exact failure reason
- [ ] `cd backend && uv run ruff format --check .` — PASS or exact failure reason

## Docs

- [ ] Updated API, WhatsApp flow, frontend component, and summary docs.

Closes #43
Linear: TPL-6
```

- [ ] **Step 4: Commit nothing during PR step unless files changed intentionally**

Run:

```bash
git status --short
```

Expected: clean except `trackpal_codex_catalog_crud_prompt.md` if still intentionally untracked.

---

## Self-review notes

- Spec coverage: Tasks 1-2 cover REST/backend preview, confirm, cascade, duplicate validation, tenant scoping. Tasks 3-4 cover WhatsApp menu/list/detail/create/edit/delete/post-success/close contract/i18n. Task 5 covers dashboard preview modal, typed confirmation, frontend i18n, and frontend tests/build. Task 6 covers docs and full verification. Task 7 covers branch/PR requirements and cascade strategy explanation.
- No soft-delete or service/plan active status is introduced.
- REST route shape stays under existing `/catalog/services/...` convention.
- Active subscriptions are always `status == "active"`; historical/non-active is total minus active.
- `9` is back, not previous-page pagination. `8` is next. `0` closes session through existing active-flow cancel and endpoint close response.
