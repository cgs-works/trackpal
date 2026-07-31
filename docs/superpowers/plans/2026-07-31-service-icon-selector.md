# Service Icon Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each Tenant assign, replace, remove, search, and consistently display an optional Iconify Service Icon without storing SVG assets in TrackPal.

**Architecture:** Persist only a nullable Icon Reference (`prefix:name`) on each Service. The frontend owns a deep `IconPicker` module backed by a direct Iconify HTTP adapter and a shared `ServiceIcon` renderer with a generic fallback; backend Service mutations remain independent from Iconify availability. Production, Demo, subscription, client-dashboard, export, and Public API Catalog contracts propagate the same reference.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL/SQLite tests, React 19, TypeScript 6 strict mode, Vitest, Testing Library, Zustand, shadcn/ui, Tailwind CSS v4, `@iconify/react` 6.0.2.

## Global Constraints

- Use Iconify as the technical source; do not scrape All SVG Icons.
- Search the complete Iconify catalog rather than a curated subset.
- Persist only `prefix:name`; do not store SVG markup, files, or provider responses.
- `Service.icon` is optional and existing Services migrate to `null`.
- On create, omitted or empty `icon` becomes `null`.
- On update, omitted `icon` preserves the current reference; explicit `null` removes it.
- Preserve original icon palettes when the collection supplies them.
- Display collection, author, license, and license link before confirming a new icon.
- Do not translate search terms automatically.
- Iconify failure must never block Service CRUD or TrackPal API responses.
- WhatsApp remains text-only.
- All TrackPal-owned UI copy must come from the backend i18n catalog.
- Automated tests must not make live Iconify requests.
- Follow TDD for every behavior change: RED, verify expected failure, GREEN, verify passing tests, then commit.

---

## File Structure Map

### Backend persistence and contracts

- Create `backend/alembic/versions/e021fe74cac1_add_service_icon.py` — nullable database column migration.
- Create `backend/tests/test_service_icon_migration.py` — migration contract.
- Modify `backend/app/models/service.py` — `Service.icon` ORM field.
- Modify `backend/app/schemas/catalog.py` — Icon Reference normalization and create/update/response fields.
- Modify `backend/app/services/catalog_service/service.py` — create, preserve, replace, and clear semantics.
- Modify `backend/tests/test_catalog.py` — API and isolation behavior.
- Modify `backend/app/schemas/public_api_key.py` — public `icon` field.
- Modify `backend/app/services/public_api_key_service.py` — public payload propagation.
- Modify `backend/app/schemas/dashboard.py` — `service_icon` for client subscriptions.
- Modify `backend/app/services/dashboard_service/__init__.py` — dashboard assembly.
- Modify `backend/tests/test_public_api_catalog.py` and `backend/tests/test_profile.py` — public and client response contracts.

### Export

- Modify `backend/app/services/export_worker.py` — CSV, JSON, README, and export format version.
- Modify `backend/tests/test_export_worker.py` — export contract coverage.

### Shared frontend icon modules

- Modify `frontend/package.json` and `frontend/package-lock.json` — add `@iconify/react` 6.0.2.
- Create `frontend/src/features/catalog/services/icon-reference.ts` — parse and validate Icon References.
- Create `frontend/src/features/catalog/services/icon-catalog.ts` — `IconCatalog` interface, Iconify adapter, normalized response types, and session cache.
- Create `frontend/src/features/catalog/services/__tests__/icon-catalog.spec.ts` — adapter behavior without live network.
- Create `frontend/src/features/catalog/components/service-icon.tsx` — consistent renderer and fallback.
- Create `frontend/src/features/catalog/components/icon-picker.tsx` — debounced search dialog, grid, details, license, pagination, errors, and retry.
- Create `frontend/src/features/catalog/components/__tests__/service-icon.spec.tsx`.
- Create `frontend/src/features/catalog/components/__tests__/icon-picker.spec.tsx`.

### Demo and Catalog administration

- Modify `frontend/src/features/admin/services/catalog-api.ts` — `icon` types and optional update semantics.
- Modify `frontend/src/features/demo/services/demo-baseline.ts` — baseline icons and version.
- Modify `frontend/src/features/demo/services/demo-workspace.ts` — schema migration for existing Services.
- Modify `frontend/src/features/demo/services/demo-catalog.ts` — local create/update/clear behavior.
- Modify Demo tests under `frontend/src/features/demo/services/__tests__/`.
- Create `frontend/src/features/admin/components/service-form-dialog.tsx` — shared create/edit Service form.
- Create `frontend/src/features/admin/components/__tests__/service-form-dialog.spec.tsx`.
- Modify `frontend/src/features/admin/components/catalog-page.tsx` — use Service form and render icons.
- Modify `frontend/src/features/admin/components/__tests__/catalog-page-demo.spec.tsx`.
- Modify `backend/app/core/i18n/catalogs_en_frontend.py` and `backend/app/core/i18n/catalogs_es_frontend.py` — selector and Service form copy.

### Related Web and public surfaces

- Modify `frontend/src/features/admin/components/subscription-form-dialog.tsx` — icon-aware Service selector.
- Modify `frontend/src/features/admin/components/subscription-table.tsx` — icon-aware desktop/mobile summaries.
- Modify `frontend/src/features/admin/components/subscriptions-page.tsx` — pass full Service records.
- Create `frontend/src/features/admin/components/__tests__/subscription-service-icons.spec.tsx`.
- Modify `frontend/src/features/client/services/client-dashboard-api.ts` and `frontend/src/features/client/components/dashboard-page.tsx` — client icons.
- Create `frontend/src/features/client/components/__tests__/dashboard-page.spec.tsx`.
- Modify `frontend/src/features/admin/components/public-api-section.tsx` and its test — developer handoff for Icon References.

### User and architecture documentation

- Modify `backend/help/en/tenant-admin/catalog.md` and `backend/help/es/tenant-admin/catalog.md`.
- Modify `backend/help/en/tenant-admin/public-api.md` and `backend/help/es/tenant-admin/public-api.md`.
- Regenerate `backend/app/help/artifact.json`.
- Modify `docs/architecture/database-schema.md`.
- Modify `docs/architecture/api-layer.md`.
- Modify `docs/architecture/frontend-architecture.md`.
- Modify `docs/architecture/tenant-data-export.md`.
- Modify `docs/codebase/frontend-components.md`.
- Modify `docs/project-pdr/public-api-catalog.md`.

---

### Task 1: Persist and Validate Icon References on Services

**Files:**
- Create: `backend/alembic/versions/e021fe74cac1_add_service_icon.py`
- Create: `backend/tests/test_service_icon_migration.py`
- Modify: `backend/app/models/service.py`
- Modify: `backend/app/schemas/catalog.py`
- Modify: `backend/app/services/catalog_service/service.py`
- Modify: `backend/tests/test_catalog.py`

**Interfaces:**
- Consumes: existing `/api/v1/catalog/services` CRUD and `ServiceCreate`/`ServiceUpdate`.
- Produces:
  - ORM field `Service.icon: str | None`.
  - JSON field `icon: string | null`.
  - Backend normalizer `normalize_icon_reference(value: str | None) -> str | None`.
  - Update rule based on `payload.model_fields_set`.

- [ ] **Step 1: Write the migration contract tests**

Create `backend/tests/test_service_icon_migration.py` with a fake Alembic operation recorder:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "e021fe74cac1_add_service_icon.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("add_service_icon", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []

    def add_column(self, table: str, column: object) -> None:
        self.calls.append(("add_column", table, column))

    def drop_column(self, table: str, column: str) -> None:
        self.calls.append(("drop_column", table, column))


def test_upgrade_adds_nullable_icon_column(monkeypatch):
    module = _load_migration_module()
    fake = FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    _, table, column = fake.calls[0]
    assert table == "services"
    assert column.name == "icon"
    assert column.type.length == 255
    assert column.nullable is True


def test_downgrade_removes_icon_column(monkeypatch):
    module = _load_migration_module()
    fake = FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    assert fake.calls == [("drop_column", "services", "icon")]
```

- [ ] **Step 2: Run the migration tests and verify RED**

Run:

```bash
cd backend
uv run pytest tests/test_service_icon_migration.py -v
```

Expected: FAIL because `e021fe74cac1_add_service_icon.py` does not exist.

- [ ] **Step 3: Add failing Catalog API tests for create, preserve, clear, and validation**

Append focused cases to `backend/tests/test_catalog.py`:

```python
@pytest.mark.parametrize(
    "icon",
    ["netflix", "Simple-Icons:netflix", "simple-icons:", "a" * 256],
)
async def test_service_icon_rejects_invalid_references(
    client, active_tenant_user, icon: str
):
    headers = await _login(client)
    response = await client.post(
        "/api/v1/catalog/services",
        json={"name": "Icon validation", "icon": icon},
        headers=headers,
    )
    assert response.status_code == 422


async def test_service_icon_create_preserve_replace_and_clear(
    client, active_tenant_user
):
    headers = await _login(client)
    created = await client.post(
        "/api/v1/catalog/services",
        json={"name": "Netflix", "icon": "simple-icons:netflix"},
        headers=headers,
    )
    assert created.status_code == 201
    service_id = created.json()["id"]
    assert created.json()["icon"] == "simple-icons:netflix"

    renamed = await client.put(
        f"/api/v1/catalog/services/{service_id}",
        json={"name": "Netflix Premium"},
        headers=headers,
    )
    assert renamed.json()["icon"] == "simple-icons:netflix"

    replaced = await client.put(
        f"/api/v1/catalog/services/{service_id}",
        json={"icon": "logos:netflix-icon"},
        headers=headers,
    )
    assert replaced.json()["icon"] == "logos:netflix-icon"

    cleared = await client.put(
        f"/api/v1/catalog/services/{service_id}",
        json={"icon": None},
        headers=headers,
    )
    assert cleared.json()["icon"] is None
```

Also extend the existing cross-Tenant test so Tenant B cannot read or overwrite Tenant A's icon.

Add a direct service test proving the save path performs no Iconify HTTP request:

```python
from unittest.mock import AsyncMock
from app.schemas.catalog import ServiceCreate


async def test_service_icon_save_does_not_call_iconify(
    db_session, active_tenant_user, monkeypatch
):
    tenant_id = await _tenant_id(db_session, active_tenant_user)
    request = AsyncMock(side_effect=AssertionError("unexpected external HTTP request"))
    monkeypatch.setattr("httpx.AsyncClient.request", request)

    saved = await CatalogService().create_service(
        db_session,
        tenant_id,
        ServiceCreate(name="Offline-safe", icon="mdi:cloud-off-outline"),
    )

    assert saved.icon == "mdi:cloud-off-outline"
    request.assert_not_awaited()
```

- [ ] **Step 4: Run the Catalog tests and verify RED**

Run:

```bash
cd backend
uv run pytest tests/test_catalog.py -q
```

Expected: FAIL because `ServiceResponse` has no `icon`, valid references are ignored, and malformed references are accepted.

- [ ] **Step 5: Implement the migration and ORM field**

Create `backend/alembic/versions/e021fe74cac1_add_service_icon.py`:

```python
"""Add optional Iconify reference to Catalog Services.

Revision ID: e021fe74cac1
Revises: e020fe74cac0
Create Date: 2026-07-31 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e021fe74cac1"
down_revision: str | None = "e020fe74cac0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("services", sa.Column("icon", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("services", "icon")
```

Add to `backend/app/models/service.py`:

```python
icon: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 6: Implement local Pydantic normalization**

In `backend/app/schemas/catalog.py`, add:

```python
import re
from pydantic import field_validator

ICON_REFERENCE_MAX_LENGTH = 255
ICON_REFERENCE_PATTERN = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$"
)


def normalize_icon_reference(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if (
        len(cleaned) > ICON_REFERENCE_MAX_LENGTH
        or ICON_REFERENCE_PATTERN.fullmatch(cleaned) is None
    ):
        raise ValueError("invalid_icon_reference")
    return cleaned
```

Define the fields and validators:

```python
class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    icon: str | None = None

    @field_validator("icon", mode="before")
    @classmethod
    def clean_icon(cls, value: str | None) -> str | None:
        return normalize_icon_reference(value)


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    icon: str | None = None

    @field_validator("icon", mode="before")
    @classmethod
    def clean_icon(cls, value: str | None) -> str | None:
        return normalize_icon_reference(value)
```

Add `icon: str | None` to `ServiceResponse`.

- [ ] **Step 7: Implement create/preserve/replace/clear semantics**

Update `CatalogService.create_service()`:

```python
service = Service(tenant_id=tenant_id, name=name, icon=payload.icon)
```

Update `CatalogService.update_service()` after the name block:

```python
if "icon" in payload.model_fields_set:
    service.icon = payload.icon
```

Do not add any Iconify HTTP client, URL, or remote validation to backend modules.

- [ ] **Step 8: Run focused backend verification**

Run:

```bash
cd backend
uv run pytest tests/test_service_icon_migration.py tests/test_catalog.py -v
uv run ruff check app/models/service.py app/schemas/catalog.py app/services/catalog_service/service.py tests/test_service_icon_migration.py tests/test_catalog.py
```

Expected: all tests PASS and Ruff reports no errors.

- [ ] **Step 9: Commit Task 1**

```bash
git add backend/alembic/versions/e021fe74cac1_add_service_icon.py backend/tests/test_service_icon_migration.py backend/app/models/service.py backend/app/schemas/catalog.py backend/app/services/catalog_service/service.py backend/tests/test_catalog.py
git commit -m "feat(catalog): persist service icon references"
```

---

### Task 2: Propagate Icons Through Public and Client Contracts

**Files:**
- Modify: `backend/app/schemas/public_api_key.py`
- Modify: `backend/app/services/public_api_key_service.py`
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/dashboard_service/__init__.py`
- Modify: `backend/tests/test_public_api_catalog.py`
- Modify: `backend/tests/test_profile.py`

**Interfaces:**
- Consumes: `Service.icon` from Task 1.
- Produces:
  - `PublicCatalogService.icon: str | None`.
  - `ClientActiveSubscription.service_icon: str | None`.

- [ ] **Step 1: Write the failing public catalog assertion**

Change `_seed_catalog()` in `backend/tests/test_public_api_catalog.py` to create:

```python
service = Service(
    tenant_id=tenant_id,
    name="Netflix",
    icon="simple-icons:netflix",
)
```

Add `"icon": "simple-icons:netflix"` to the expected Service object in `test_public_catalog_success_returns_nested_services_and_cors`.

- [ ] **Step 2: Write a failing client dashboard icon test**

Add a focused assembly test to `backend/tests/test_profile.py`:

```python
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.dashboard_service import DashboardService


async def test_client_dashboard_subscription_includes_service_icon(monkeypatch):
    subscription = SimpleNamespace(
        id=uuid4(),
        service=SimpleNamespace(name="Netflix", icon="simple-icons:netflix"),
        plan=SimpleNamespace(name="Premium"),
        status="active",
        starts_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        "app.services.dashboard_service.get_active_subscriptions_for_client",
        AsyncMock(return_value=[subscription]),
    )
    profile = SimpleNamespace(
        id=uuid4(),
        full_name="Client Demo",
        username="client_demo",
        phone="12025550123",
        tenant_id=uuid4(),
        tenant=SimpleNamespace(name="Demo Provider", client_prefix="demo"),
        is_active=True,
    )

    result = await DashboardService()._client_dashboard(AsyncMock(), profile)

    assert result.subscriptions[0].service_icon == "simple-icons:netflix"
```

Use the existing `uuid4` import in the test file.

- [ ] **Step 3: Run both tests and verify RED**

Run:

```bash
cd backend
uv run pytest tests/test_public_api_catalog.py::test_public_catalog_success_returns_nested_services_and_cors tests/test_profile.py -q
```

Expected: FAIL because neither response schema exposes the icon.

- [ ] **Step 4: Add the response fields**

In `backend/app/schemas/public_api_key.py`:

```python
class PublicCatalogService(BaseModel):
    id: UUID
    name: str
    icon: str | None = None
    plans: list[PublicCatalogPlan]
```

In `backend/app/services/public_api_key_service.py`:

```python
PublicCatalogService(
    id=svc.id,
    name=svc.name,
    icon=svc.icon,
    plans=[PublicCatalogPlan(id=p.id, name=p.name) for p in plans],
)
```

In `backend/app/schemas/dashboard.py`:

```python
class ClientActiveSubscription(BaseModel):
    id: UUID
    service_name: str
    service_icon: str | None = None
    plan_name: str
    status: str
    starts_at: datetime
    expires_at: datetime
```

In `DashboardService._client_dashboard()`:

```python
service_icon=sub.service.icon if sub.service else None,
```

- [ ] **Step 5: Run focused contract tests**

Run:

```bash
cd backend
uv run pytest tests/test_public_api_catalog.py tests/test_profile.py -v
uv run ruff check app/schemas/public_api_key.py app/services/public_api_key_service.py app/schemas/dashboard.py app/services/dashboard_service/__init__.py tests/test_public_api_catalog.py tests/test_profile.py
```

Expected: PASS with public CORS behavior unchanged.

- [ ] **Step 6: Commit Task 2**

```bash
git add backend/app/schemas/public_api_key.py backend/app/services/public_api_key_service.py backend/app/schemas/dashboard.py backend/app/services/dashboard_service/__init__.py backend/tests/test_public_api_catalog.py backend/tests/test_profile.py
git commit -m "feat(catalog): expose service icons in read models"
```

---

### Task 3: Add Icon References to Tenant Data Export

**Files:**
- Modify: `backend/app/services/export_worker.py`
- Modify: `backend/tests/test_export_worker.py`

**Interfaces:**
- Consumes: nullable `Service.icon`.
- Produces:
  - CSV column `service_icon` immediately after `service_name`.
  - JSON key `service_icon` in each `service_catalog` item.
  - `export_format_version: "2"`.

- [ ] **Step 1: Change export tests first**

Update `test_service_catalog_csv_has_approved_fields` to expect seven fields:

```python
assert headers == [
    "service_name",
    "service_icon",
    "service_created_on",
    "service_updated_on",
    "plan_name",
    "plan_created_on",
    "plan_updated_on",
]
```

Create Services with `icon="simple-icons:netflix"` in the CSV and JSON data tests, then assert:

```python
assert row[1] == "simple-icons:netflix"
assert catalog[0]["service_icon"] == "simple-icons:netflix"
assert data["export_metadata"]["export_format_version"] == "2"
```

Add one null case:

```python
assert catalog_without_icon[0]["service_icon"] is None
```

Update every positional CSV assertion after the inserted column: `service_icon` is index `1`, timestamps move to indexes `2` and `3`, `plan_name` moves from index `3` to index `4`, and Plan timestamps move to indexes `5` and `6`.

- [ ] **Step 2: Run export tests and verify RED**

Run:

```bash
cd backend
uv run pytest tests/test_export_worker.py -q
```

Expected: FAIL because the approved export currently has six CSV fields, no JSON icon, and format version `1`.

- [ ] **Step 3: Implement the export field and documentation text**

In `_build_service_catalog_csv()`, insert `service_icon` in the header and `svc.icon or ""` in every Service row.

In `_build_json()`, add:

```python
"service_icon": svc.icon,
```

Change:

```python
"export_format_version": "2",
```

Update both `_README_EN` and `_README_ES` to define `service_icon` as the optional Iconify `prefix:name` reference and state that TrackPal does not include the SVG asset.

- [ ] **Step 4: Run export verification**

Run:

```bash
cd backend
uv run pytest tests/test_export_worker.py -v
uv run ruff check app/services/export_worker.py tests/test_export_worker.py
```

Expected: PASS, including no-secret and no-internal-identifier tests.

- [ ] **Step 5: Commit Task 3**

```bash
git add backend/app/services/export_worker.py backend/tests/test_export_worker.py
git commit -m "feat(export): include service icon references"
```

---

### Task 4: Build the Iconify Adapter and Shared Service Renderer

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/src/features/catalog/services/icon-reference.ts`
- Create: `frontend/src/features/catalog/services/icon-catalog.ts`
- Create: `frontend/src/features/catalog/services/__tests__/icon-catalog.spec.ts`
- Create: `frontend/src/features/catalog/components/service-icon.tsx`
- Create: `frontend/src/features/catalog/components/__tests__/service-icon.spec.tsx`

**Interfaces:**
- Consumes: Iconify Search and Collections HTTP responses.
- Produces:

```ts
export interface IconAuthor {
  name: string;
  url?: string;
}

export interface IconLicense {
  title: string;
  spdx?: string;
  url: string;
}

export interface IconCollectionInfo {
  prefix: string;
  name: string;
  author: IconAuthor;
  license: IconLicense;
  palette: boolean;
}

export interface IconSearchPage {
  icons: string[];
  total: number;
  limit: number;
  start: number;
  hasMore: boolean;
  collections: Record<string, IconCollectionInfo>;
}

export interface IconDetails {
  icon: string;
  prefix: string;
  name: string;
  collection: IconCollectionInfo;
}

export interface IconCatalog {
  search(query: string, start?: number, signal?: AbortSignal): Promise<IconSearchPage>;
  describe(icon: string, signal?: AbortSignal): Promise<IconDetails>;
}

export function parseIconReference(value: string | null | undefined):
  | { prefix: string; name: string }
  | null;

export function ServiceIcon(props: {
  icon: string | null | undefined;
  label: string;
  className?: string;
}): React.ReactElement;
```

- [ ] **Step 1: Install the pinned Iconify React dependency**

Run:

```bash
cd frontend
npm install @iconify/react@^6.0.2
```

Expected: `package.json` and `package-lock.json` record `@iconify/react` compatible with 6.0.2.

- [ ] **Step 2: Write failing parser and adapter tests**

Create `frontend/src/features/catalog/services/__tests__/icon-catalog.spec.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createIconifyCatalog } from "../icon-catalog";
import { parseIconReference } from "../icon-reference";

describe("Iconify catalog adapter", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("parses only provider-qualified icon references", () => {
    expect(parseIconReference("simple-icons:netflix")).toEqual({
      prefix: "simple-icons",
      name: "netflix",
    });
    expect(parseIconReference("netflix")).toBeNull();
    expect(parseIconReference("Simple-Icons:netflix")).toBeNull();
  });

  it("normalizes search results and collection licenses", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      icons: ["simple-icons:netflix"],
      total: 1,
      limit: 64,
      start: 0,
      collections: {
        "simple-icons": {
          name: "Simple Icons",
          author: { name: "Simple Icons Collaborators", url: "https://simpleicons.org" },
          license: { title: "CC0 1.0", spdx: "CC0-1.0", url: "https://creativecommons.org/publicdomain/zero/1.0/" },
          palette: true,
        },
      },
    }), { status: 200 }));
    const catalog = createIconifyCatalog(fetcher);

    const result = await catalog.search("netflix");

    expect(result.icons).toEqual(["simple-icons:netflix"]);
    expect(result.hasMore).toBe(false);
    expect(result.collections["simple-icons"].license.spdx).toBe("CC0-1.0");
    const requested = new URL(String(fetcher.mock.calls[0][0]));
    expect(requested.searchParams.get("limit")).toBe("64");
  });

  it("sends non-English search text unchanged", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      icons: [], total: 0, limit: 64, start: 0, collections: {},
    }), { status: 200 }));
    const catalog = createIconifyCatalog(fetcher);

    await catalog.search("música");

    const requested = new URL(String(fetcher.mock.calls[0][0]));
    expect(requested.searchParams.get("query")).toBe("música");
  });

  it("loads collection metadata for a saved icon", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      "simple-icons": {
        name: "Simple Icons",
        author: { name: "Simple Icons Collaborators" },
        license: { title: "CC0 1.0", url: "https://creativecommons.org/publicdomain/zero/1.0/" },
        palette: true,
      },
    }), { status: 200 }));
    const catalog = createIconifyCatalog(fetcher);

    const details = await catalog.describe("simple-icons:netflix");

    expect(details.icon).toBe("simple-icons:netflix");
    expect(details.collection.license.title).toBe("CC0 1.0");
    expect(String(fetcher.mock.calls[0][0])).toContain("/collections?prefix=simple-icons");
  });

  it("reuses session cache for repeated searches", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      icons: [], total: 0, limit: 64, start: 0, collections: {},
    }), { status: 200 }));
    const catalog = createIconifyCatalog(fetcher);

    await catalog.search("cloud");
    await catalog.search("cloud");

    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 3: Write failing ServiceIcon tests**

Create `frontend/src/features/catalog/components/__tests__/service-icon.spec.tsx` and mock `@iconify/react`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ServiceIcon } from "../service-icon";

const loadIcon = vi.hoisted(() => vi.fn());
vi.mock("@iconify/react", () => ({
  loadIcon,
  Icon: ({ icon }: { icon: unknown }) => <span data-testid="iconify-icon">{JSON.stringify(icon)}</span>,
}));

describe("ServiceIcon", () => {
  beforeEach(() => loadIcon.mockReset());

  it("renders loaded Iconify data", async () => {
    loadIcon.mockResolvedValue({ body: '<path fill="#e50914" />', width: 24, height: 24 });
    render(<ServiceIcon icon="simple-icons:netflix" label="Netflix" />);
    expect(await screen.findByTestId("iconify-icon")).toHaveTextContent("#e50914");
    expect(screen.getByRole("img", { name: "Netflix" })).toBeInTheDocument();
  });

  it("uses the generic fallback for null and load failures", async () => {
    const { rerender } = render(<ServiceIcon icon={null} label="Unknown" />);
    expect(screen.getByTestId("service-icon-fallback")).toBeInTheDocument();

    loadIcon.mockRejectedValue(new Error("offline"));
    rerender(<ServiceIcon icon="simple-icons:missing" label="Missing" />);
    await waitFor(() => expect(screen.getByTestId("service-icon-fallback")).toBeInTheDocument());
  });
});
```

- [ ] **Step 4: Run the module tests and verify RED**

Run:

```bash
cd frontend
npm test -- src/features/catalog/services/__tests__/icon-catalog.spec.ts src/features/catalog/components/__tests__/service-icon.spec.tsx
```

Expected: FAIL because the new modules do not exist.

- [ ] **Step 5: Implement Icon Reference parsing and the adapter**

Create `icon-reference.ts`:

```ts
export const ICON_REFERENCE_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function parseIconReference(value: string | null | undefined) {
  if (!value || value.length > 255 || !ICON_REFERENCE_PATTERN.test(value)) return null;
  const separator = value.indexOf(":");
  return { prefix: value.slice(0, separator), name: value.slice(separator + 1) };
}
```

In `icon-catalog.ts`, define normalized types and `createIconifyCatalog(fetcher = fetch)`. Use:

```ts
const SEARCH_LIMIT = 64;
const API_BASE = "https://api.iconify.design";
```

Search URL:

```ts
const url = new URL(`${API_BASE}/search`);
url.searchParams.set("query", query.trim());
url.searchParams.set("limit", String(SEARCH_LIMIT));
url.searchParams.set("start", String(start));
```

Return `hasMore` as `start + icons.length < total`. Reject non-OK responses with `new Error("iconify_search_failed")`. `describe()` parses the prefix, rejects malformed references with `new Error("iconify_icon_invalid")`, calls `/collections?prefix=<prefix>`, and returns the exact `IconDetails` shape defined above. Normalize missing author names to the collection name, missing license fields to empty strings, and missing `palette` to `false`. Cache successful search pages by `${query.trim().toLocaleLowerCase()}:${start}` and collection descriptions by prefix.

Export `iconifyCatalog = createIconifyCatalog()`.

- [ ] **Step 6: Implement the shared renderer**

Create `service-icon.tsx` with `loadIcon()` inside an effect. Render a container with `role="img"` and `aria-label={label}`. While absent, invalid, loading unsuccessfully, or rejected, render:

```tsx
<Package data-testid="service-icon-fallback" aria-hidden="true" className={className} />
```

When loaded, render:

```tsx
<Icon aria-hidden="true" icon={data} className={className} />
```

Pass the loaded Iconify data object to preserve multicolor palettes and avoid raw SVG HTML.

- [ ] **Step 7: Run focused frontend verification**

Run:

```bash
cd frontend
npm test -- src/features/catalog/services/__tests__/icon-catalog.spec.ts src/features/catalog/components/__tests__/service-icon.spec.tsx
npm run build
```

Expected: tests PASS and TypeScript accepts the Iconify data types.

- [ ] **Step 8: Commit Task 4**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/features/catalog/services frontend/src/features/catalog/components/service-icon.tsx frontend/src/features/catalog/components/__tests__/service-icon.spec.tsx
git commit -m "feat(catalog): add Iconify catalog adapter"
```

---

### Task 5: Build the Accessible Icon Picker

**Files:**
- Create: `frontend/src/features/catalog/components/icon-picker.tsx`
- Create: `frontend/src/features/catalog/components/__tests__/icon-picker.spec.tsx`

**Interfaces:**
- Consumes: `iconifyCatalog`, `IconSearchPage`, `IconDetails`, and `ServiceIcon` from Task 4.
- Produces:

```ts
export interface IconPickerProps {
  open: boolean;
  value: string | null;
  initialQuery?: string;
  onOpenChange(open: boolean): void;
  onSelect(icon: string | null): void;
}
```

- [ ] **Step 1: Write the failing interaction tests**

Create `icon-picker.spec.tsx`. Mock the internal adapter module so no live request is possible:

```tsx
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IconPicker, type IconPickerProps } from "../icon-picker";

const search = vi.hoisted(() => vi.fn());
const describeIcon = vi.hoisted(() => vi.fn());
vi.mock("@/features/catalog/services/icon-catalog", () => ({
  iconifyCatalog: { search, describe: describeIcon },
}));
vi.mock("../service-icon", () => ({
  ServiceIcon: ({ icon, label }: { icon: string | null; label: string }) => (
    <span data-testid={`icon-${icon ?? "fallback"}`}>{label}</span>
  ),
}));
vi.mock("@/i18n", () => ({ t: (key: string) => key }));

const searchPageWithNetflix = {
  icons: ["simple-icons:netflix"],
  total: 1,
  limit: 64,
  start: 0,
  hasMore: false,
  collections: {
    "simple-icons": {
      prefix: "simple-icons",
      name: "Simple Icons",
      author: { name: "Simple Icons Collaborators", url: "https://simpleicons.org" },
      license: {
        title: "CC0 1.0",
        spdx: "CC0-1.0",
        url: "https://creativecommons.org/publicdomain/zero/1.0/",
      },
      palette: true,
    },
  },
};

function renderPicker(overrides: Partial<IconPickerProps> = {}) {
  const props: IconPickerProps = {
    open: true,
    value: null,
    initialQuery: "",
    onOpenChange: vi.fn(),
    onSelect: vi.fn(),
    ...overrides,
  };
  return { props, ...render(<IconPicker {...props} />) };
}
```

Cover these observable behaviors in separate tests:

```tsx
it("waits for two characters and debounces search by 300ms", async () => {
  vi.useFakeTimers();
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  renderPicker();
  await user.type(screen.getByRole("searchbox"), "n");
  await vi.advanceTimersByTimeAsync(300);
  expect(search).not.toHaveBeenCalled();
  await user.type(screen.getByRole("searchbox"), "e");
  await vi.advanceTimersByTimeAsync(299);
  expect(search).not.toHaveBeenCalled();
  await vi.advanceTimersByTimeAsync(1);
  expect(search).toHaveBeenCalledWith("ne", 0, expect.any(AbortSignal));
});
```

```tsx
it("shows collection license before enabling selection", async () => {
  search.mockResolvedValue(searchPageWithNetflix);
  renderPicker({ initialQuery: "netflix" });
  expect(await screen.findByText("CC0 1.0")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /CC0 1.0/ })).toHaveAttribute(
    "href",
    "https://creativecommons.org/publicdomain/zero/1.0/",
  );
  expect(screen.getByRole("button", { name: "frontend.icon_picker.select" })).toBeEnabled();
});
```

Add the remaining tests with concrete assertions:

```tsx
afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

it("aborts an obsolete search when the query changes", async () => {
  vi.useFakeTimers();
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  search.mockResolvedValue(searchPageWithNetflix);
  renderPicker();

  await user.type(screen.getByRole("searchbox"), "ne");
  await vi.advanceTimersByTimeAsync(300);
  const firstSignal = search.mock.calls[0][2] as AbortSignal;
  await user.type(screen.getByRole("searchbox"), "t");
  await vi.advanceTimersByTimeAsync(300);

  expect(firstSignal.aborted).toBe(true);
  expect(search).toHaveBeenLastCalledWith("net", 0, expect.any(AbortSignal));
});

it("shows an empty state for a successful search with no matches", async () => {
  search.mockResolvedValue({
    icons: [], total: 0, limit: 64, start: 0, hasMore: false, collections: {},
  });
  renderPicker({ initialQuery: "no-match" });
  expect(await screen.findByText("frontend.icon_picker.empty")).toBeInTheDocument();
});

it("keeps the current value when search fails and retries", async () => {
  describeIcon.mockResolvedValue({
    icon: "simple-icons:netflix",
    prefix: "simple-icons",
    name: "netflix",
    collection: searchPageWithNetflix.collections["simple-icons"],
  });
  search.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(searchPageWithNetflix);
  renderPicker({ value: "simple-icons:netflix", initialQuery: "netflix" });

  expect(await screen.findByText("frontend.icon_picker.error")).toBeInTheDocument();
  expect(screen.getByTestId("icon-simple-icons:netflix")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "frontend.icon_picker.retry" }));
  expect(await screen.findByRole("option", { name: /simple-icons:netflix/ })).toBeInTheDocument();
});

it("loads and appends the next 64-result page", async () => {
  search
    .mockResolvedValueOnce({ ...searchPageWithNetflix, total: 65, hasMore: true })
    .mockResolvedValueOnce({
      icons: ["mdi:cloud"],
      total: 65,
      limit: 64,
      start: 64,
      hasMore: false,
      collections: {
        mdi: {
          prefix: "mdi",
          name: "Material Design Icons",
          author: { name: "Pictogrammers" },
          license: { title: "Apache 2.0", url: "https://www.apache.org/licenses/LICENSE-2.0" },
          palette: false,
        },
      },
    });
  renderPicker({ initialQuery: "cloud" });

  await screen.findByRole("option", { name: /simple-icons:netflix/ });
  await userEvent.click(screen.getByRole("button", { name: "frontend.icon_picker.load_more" }));

  expect(await screen.findByRole("option", { name: /mdi:cloud/ })).toBeInTheDocument();
  expect(search).toHaveBeenLastCalledWith("cloud", 64, expect.any(AbortSignal));
});

it("disables confirmation when license metadata is incomplete", async () => {
  search.mockResolvedValue({
    ...searchPageWithNetflix,
    collections: {
      "simple-icons": {
        ...searchPageWithNetflix.collections["simple-icons"],
        license: { title: "Unknown", url: "" },
      },
    },
  });
  renderPicker({ initialQuery: "netflix" });
  await userEvent.click(await screen.findByRole("option", { name: /simple-icons:netflix/ }));
  expect(screen.getByRole("button", { name: "frontend.icon_picker.select" })).toBeDisabled();
});

it("marks, confirms, and closes the selected icon", async () => {
  search.mockResolvedValue(searchPageWithNetflix);
  const { props } = renderPicker({ initialQuery: "netflix" });
  const option = await screen.findByRole("option", { name: /simple-icons:netflix/ });

  await userEvent.click(option);
  expect(option).toHaveAttribute("aria-selected", "true");
  expect(within(option).getByTestId("icon-picker-selected-marker")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "frontend.icon_picker.select" }));

  expect(props.onSelect).toHaveBeenCalledWith("simple-icons:netflix");
  expect(props.onOpenChange).toHaveBeenCalledWith(false);
});

it("places the result grid before details for stacked mobile reading order", async () => {
  search.mockResolvedValue(searchPageWithNetflix);
  renderPicker({ initialQuery: "netflix" });
  const listbox = await screen.findByRole("listbox");
  const details = screen.getByTestId("icon-picker-details");
  expect(listbox.compareDocumentPosition(details) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
```

- [ ] **Step 2: Run the picker tests and verify RED**

Run:

```bash
cd frontend
npm test -- src/features/catalog/components/__tests__/icon-picker.spec.tsx
```

Expected: FAIL because `IconPicker` does not exist.

- [ ] **Step 3: Implement the picker state machine**

Create `icon-picker.tsx` with state for:

```ts
const [query, setQuery] = useState(initialQuery ?? "");
const [results, setResults] = useState<string[]>([]);
const [collections, setCollections] = useState<Record<string, IconCollectionInfo>>({});
const [selected, setSelected] = useState<string | null>(value);
const [selectedDetails, setSelectedDetails] = useState<IconDetails | null>(null);
const [pageStart, setPageStart] = useState(0);
const [hasMore, setHasMore] = useState(false);
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string | null>(null);
```

On `open`, reset transient state from `value` and `initialQuery`. Use a 300 ms effect timer and `AbortController`; cleanup must clear the timer and abort the active request.

When a result is selected, parse its prefix and build `IconDetails` from `collections[prefix]`. When the current saved `value` has no metadata in the active search page, populate the same `IconDetails` shape from `iconifyCatalog.describe(value)`.

For `Load more`, request the next `start`, deduplicate Icon References with `new Set([...results, ...page.icons])`, and merge collection metadata.

- [ ] **Step 4: Implement the approved responsive dialog**

Use shadcn `Dialog`, `Input`, and `Button`:

```tsx
<DialogContent className="max-h-[90vh] overflow-hidden sm:max-w-5xl">
  <DialogHeader>
    <DialogTitle>{t("frontend.icon_picker.title")}</DialogTitle>
    <DialogDescription>{t("frontend.icon_picker.description")}</DialogDescription>
  </DialogHeader>
  <div className="grid min-h-0 gap-4 md:grid-cols-[minmax(0,1fr)_18rem]">
    <section className="flex min-h-0 flex-col gap-3">
      {/* search, live status, grid, load more */}
    </section>
    <aside className="order-last rounded-lg border p-4 md:order-none">
      {/* large preview, identifier, collection, author, license */}
    </aside>
  </div>
</DialogContent>
```

Wrap the result buttons in a container with `role="listbox"` and an accessible label. Render each result as a native button with `role="option"`, `aria-selected`, an accessible name containing the icon reference and collection name, and a visible `Check` marker when selected. Native button focus provides Tab and Shift+Tab keyboard navigation without custom key interception.

Add a restrained `aria-live="polite"` status for loading, errors, empty state, and result count. Render collection names, author names, license titles, and URLs directly as escaped React text/attributes; never pass provider metadata through `t()` or raw HTML.

- [ ] **Step 5: Enforce license and failure rules**

Derive details from the search response collection metadata. If an existing `value` is not in current search results, call `iconifyCatalog.describe(value)` when the dialog opens.

Disable confirm when:

```ts
const canConfirm = Boolean(
  selected !== null &&
  selectedDetails?.collection.license.title &&
  selectedDetails.collection.license.url,
);
```

Search failure must leave `selected` unchanged. Retry repeats the current query. Closing the dialog never calls `onSelect`.

- [ ] **Step 6: Add bilingual i18n keys**

Add matching English and Spanish keys in:

- `backend/app/core/i18n/catalogs_en_frontend.py`
- `backend/app/core/i18n/catalogs_es_frontend.py`

Use these exact values:

```python
# English
"frontend.icon_picker.title": "Choose a service icon",
"frontend.icon_picker.description": "Search the Iconify catalog and review the collection license before selecting an icon.",
"frontend.icon_picker.search": "Search icons",
"frontend.icon_picker.search_hint": "Enter at least 2 characters.",
"frontend.icon_picker.searching": "Searching icons...",
"frontend.icon_picker.results": "{count} icons found.",
"frontend.icon_picker.empty": "No icons match this search.",
"frontend.icon_picker.error": "Iconify is temporarily unavailable. Your current service icon is unchanged.",
"frontend.icon_picker.retry": "Retry",
"frontend.icon_picker.load_more": "Load more",
"frontend.icon_picker.selected": "Selected icon",
"frontend.icon_picker.collection": "Collection",
"frontend.icon_picker.author": "Author",
"frontend.icon_picker.license": "License",
"frontend.icon_picker.license_unavailable": "License details are unavailable, so this icon cannot be selected yet.",
"frontend.icon_picker.select": "Select icon",
"frontend.icon_picker.cancel": "Cancel",

# Spanish
"frontend.icon_picker.title": "Elegir icono del servicio",
"frontend.icon_picker.description": "Busca en el catálogo de Iconify y revisa la licencia de la colección antes de seleccionar un icono.",
"frontend.icon_picker.search": "Buscar iconos",
"frontend.icon_picker.search_hint": "Escribe al menos 2 caracteres.",
"frontend.icon_picker.searching": "Buscando iconos...",
"frontend.icon_picker.results": "Se encontraron {count} iconos.",
"frontend.icon_picker.empty": "Ningún icono coincide con esta búsqueda.",
"frontend.icon_picker.error": "Iconify no está disponible temporalmente. El icono actual del servicio no cambió.",
"frontend.icon_picker.retry": "Reintentar",
"frontend.icon_picker.load_more": "Cargar más",
"frontend.icon_picker.selected": "Icono seleccionado",
"frontend.icon_picker.collection": "Colección",
"frontend.icon_picker.author": "Autor",
"frontend.icon_picker.license": "Licencia",
"frontend.icon_picker.license_unavailable": "Los datos de licencia no están disponibles, por lo que aún no se puede seleccionar este icono.",
"frontend.icon_picker.select": "Seleccionar icono",
"frontend.icon_picker.cancel": "Cancelar",
```

Keep provider collection, author, and license values untranslated.

- [ ] **Step 7: Run picker, i18n, build, and lint checks**

Run:

```bash
cd frontend
npm test -- src/features/catalog/components/__tests__/icon-picker.spec.tsx
npm run build
npm run lint
cd ../backend
uv run pytest tests/test_i18n.py -q
```

Expected: all commands PASS; no raw translation keys render in normal operation.

- [ ] **Step 8: Commit Task 5**

```bash
git add frontend/src/features/catalog/components/icon-picker.tsx frontend/src/features/catalog/components/__tests__/icon-picker.spec.tsx backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py
git commit -m "feat(catalog): add accessible icon picker"
```

---

### Task 6: Preserve Service Icons in Demo Workspaces

**Files:**
- Modify: `frontend/src/features/admin/services/catalog-api.ts`
- Modify: `frontend/src/features/demo/services/demo-baseline.ts`
- Modify: `frontend/src/features/demo/services/demo-workspace.ts`
- Modify: `frontend/src/features/demo/services/demo-catalog.ts`
- Modify: `frontend/src/features/demo/services/__tests__/demo-catalog.spec.ts`
- Modify: `frontend/src/features/demo/services/__tests__/demo-workspace.spec.ts`

**Interfaces:**
- Consumes: `Service.icon`, `ServiceCreate.icon?`, `ServiceUpdate.icon?`, and `parseIconReference`.
- Produces: Demo Workspace schema version `3`, baseline version `3`, local icon CRUD matching production semantics.

- [ ] **Step 1: Update TypeScript Catalog contracts and write failing Demo CRUD tests**

Change `catalog-api.ts`:

```ts
export interface Service {
  id: string;
  tenant_id: string;
  name: string;
  icon: string | null;
  created_at: string;
  updated_at: string;
}

export interface ServiceCreate {
  name: string;
  icon?: string | null;
}

export interface ServiceUpdate {
  name?: string;
  icon?: string | null;
}
```

In `demo-catalog.spec.ts`, add:

```ts
const created = await catalog.createService({
  name: "New Service",
  icon: "simple-icons:netflix",
});
expect(created.icon).toBe("simple-icons:netflix");

const renamed = await catalog.updateService(created.id, { name: "Renamed" });
expect(renamed.icon).toBe("simple-icons:netflix");

const cleared = await catalog.updateService(created.id, { icon: null });
expect(cleared.icon).toBeNull();
```

Assert all six baseline Services have non-null Icon References.

- [ ] **Step 2: Write the failing workspace migration test**

In `demo-workspace.spec.ts`, store a schema version 2 Pro envelope whose Service has no `icon`, then assert after `repo.read()`:

```ts
expect(migrated?.schema_version).toBe(3);
expect((migrated?.plan_specific.services as Array<Record<string, unknown>>)[0].icon).toBeNull();
expect(migrated?.tour_state).toEqual({ completed: true });
```

- [ ] **Step 3: Run Demo tests and verify RED**

Run:

```bash
cd frontend
npm test -- src/features/demo/services/__tests__/demo-catalog.spec.ts src/features/demo/services/__tests__/demo-workspace.spec.ts
```

Expected: FAIL because Demo Services have no icon and version 2 migration does not add one.

- [ ] **Step 4: Add deterministic baseline icons**

Set `DEMO_BASELINE_VERSION = 3` and define the six Service tuples as:

```ts
const serviceDefinitions: Array<[string, string, string]> = [
  ["service-disney", "Disney+", "tabler:brand-disney"],
  ["service-hbo_max", "HBO Max", "simple-icons:max"],
  ["service-netflix", "Netflix", "simple-icons:netflix"],
  ["service-prime_video", "Prime Video", "simple-icons:primevideo"],
  ["service-spotify", "Spotify", "simple-icons:spotify"],
  ["service-universal_plus", "Universal+", "mdi:television-play"],
];
```

Map each `[id, name, icon]` tuple to `Service` with `icon`.

- [ ] **Step 5: Migrate schema versions 1 and 2 to version 3**

Set `DEMO_WORKSPACE_SCHEMA_VERSION = 3`.

Add a pure migration helper:

```ts
function migrateServiceIcons(planSpecific: unknown): unknown {
  if (!isRecord(planSpecific) || !Array.isArray(planSpecific.services)) return planSpecific;
  return {
    ...planSpecific,
    services: planSpecific.services.map((service) =>
      isRecord(service) && !("icon" in service)
        ? { ...service, icon: null }
        : service,
    ),
  };
}
```

Allow known versions `1` and `2`, apply the helper, set schema version `3`, and preserve lifecycle, business, and tour state. Import `parseIconReference` from `@/features/catalog/services/icon-reference` and tighten Service validation so `icon` must be `null` or a valid Icon Reference.

- [ ] **Step 6: Implement local create/update semantics**

In `demo-catalog.ts`:

- import `parseIconReference` from `@/features/catalog/services/icon-reference`;
- create sets `icon: payload.icon ?? null` after local Icon Reference validation;
- omitted `payload.icon` during update preserves `existing.icon`;
- explicit `null` clears it;
- omitted `payload.name` preserves the current name;
- invalid references throw `DemoCatalogError("catalog_icon_invalid")`.

Add `catalog_icon_invalid` to the error union and map it to `frontend.catalog.invalid_icon`. Add the bilingual `frontend.catalog.invalid_icon` values listed in Task 7 during this task; Task 7 reuses the existing key rather than duplicating it.

- [ ] **Step 7: Run Demo and TypeScript verification**

Run:

```bash
cd frontend
npm test -- src/features/demo/services/__tests__/demo-catalog.spec.ts src/features/demo/services/__tests__/demo-workspace.spec.ts
npm run build
```

Expected: PASS and existing workspaces preserve their non-icon data.

- [ ] **Step 8: Commit Task 6**

```bash
git add frontend/src/features/admin/services/catalog-api.ts frontend/src/features/demo/services/demo-baseline.ts frontend/src/features/demo/services/demo-workspace.ts frontend/src/features/demo/services/demo-catalog.ts frontend/src/features/demo/services/__tests__/demo-catalog.spec.ts frontend/src/features/demo/services/__tests__/demo-workspace.spec.ts backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py
git commit -m "feat(demo): persist service icon references"
```

---

### Task 7: Integrate the Picker Into Catalog Service CRUD

**Files:**
- Create: `frontend/src/features/admin/components/service-form-dialog.tsx`
- Create: `frontend/src/features/admin/components/__tests__/service-form-dialog.spec.tsx`
- Modify: `frontend/src/features/admin/components/catalog-page.tsx`
- Modify: `frontend/src/features/admin/components/__tests__/catalog-page-demo.spec.tsx`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py`

**Interfaces:**
- Consumes: `IconPicker`, `ServiceIcon`, `ServiceCreate`, and `ServiceUpdate`.
- Produces:

```ts
interface ServiceFormDialogProps {
  open: boolean;
  mode: "create" | "edit";
  service?: Service | null;
  saving: boolean;
  error: string;
  onOpenChange(open: boolean): void;
  onSubmit(payload: ServiceCreate | ServiceUpdate): Promise<void>;
}
```

- [ ] **Step 1: Write Service form tests before the form**

Mock `IconPicker` with a deterministic button and test:

```tsx
it("submits a new service with the selected icon", async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  render(<ServiceFormDialog open mode="create" saving={false} error="" onOpenChange={vi.fn()} onSubmit={onSubmit} />);

  await userEvent.type(screen.getByLabelText("frontend.common.name"), "Netflix");
  await userEvent.click(screen.getByRole("button", { name: "choose-test-icon" }));
  await userEvent.click(screen.getByRole("button", { name: "frontend.catalog.save_service" }));

  expect(onSubmit).toHaveBeenCalledWith({
    name: "Netflix",
    icon: "simple-icons:netflix",
  });
});
```

Add edit tests for preserving the existing icon, replacing it, and clicking **Remove icon** to submit `icon: null`.

- [ ] **Step 2: Update the Demo Catalog page test first**

Change `catalog-page-demo.spec.tsx` to expect a **New service** button instead of the inline input. Open the Service form, enter `Local Service`, select the mocked icon, save, and assert the new row renders `data-testid="service-icon-simple-icons:netflix"`. Then edit the Service and clear its icon without API calls.

- [ ] **Step 3: Run the tests and verify RED**

Run:

```bash
cd frontend
npm test -- src/features/admin/components/__tests__/service-form-dialog.spec.tsx src/features/admin/components/__tests__/catalog-page-demo.spec.tsx
```

Expected: FAIL because the shared Service form and icon-aware Catalog page do not exist.

- [ ] **Step 4: Implement `ServiceFormDialog`**

Use controlled `name`, `icon`, and `pickerOpen` state. Reset them every time the dialog opens:

```ts
useEffect(() => {
  if (!open) return;
  setName(service?.name ?? "");
  setIcon(service?.icon ?? null);
  setPickerOpen(false);
}, [open, service]);
```

Render the current `ServiceIcon`, **Choose icon**, and conditional **Remove icon** controls. Keep the Service form open when Iconify fails. Submit only local form state.

For edit mode, always submit both fields:

```ts
await onSubmit({ name: name.trim(), icon });
```

This gives the Web form explicit replace/clear behavior while WhatsApp name-only updates continue to preserve icons through backend omitted-field semantics.

- [ ] **Step 5: Replace Service-only CRUD UI in `CatalogPage`**

- remove `newServiceName`, `creatingService`, and Service use of `RenameDialog`;
- keep the rename dialog for Plans only;
- add one Service form state block (`serviceFormOpen`, `serviceFormMode`, `serviceFormTarget`, `serviceSaving`, `serviceFormError`);
- replace the inline Service input with a full-width **New service** button;
- open the shared form from the pencil action;
- create with `dataSource.catalog.createService(payload)`;
- edit with `dataSource.catalog.updateService(service.id, payload)`;
- invalidate/reload Services after success;
- render `ServiceIcon` before each Service name;
- inspect Axios `response.data.detail` arrays and map any message containing `invalid_icon_reference` to `frontend.catalog.invalid_icon`, while keeping the dialog open and associating the message with the icon field.

Do not change Plan CRUD or delete-preview behavior.

- [ ] **Step 6: Add bilingual Service form copy**

Add these exact bilingual values:

```python
# English
"frontend.catalog.new_service": "New service",
"frontend.catalog.edit_service": "Edit service",
"frontend.catalog.service_icon": "Service icon",
"frontend.catalog.choose_icon": "Choose icon",
"frontend.catalog.remove_icon": "Remove icon",
"frontend.catalog.icon_optional_help": "Optional. If no icon is selected, TrackPal shows a generic service icon.",
"frontend.catalog.save_service": "Save service",
"frontend.catalog.service_created": "Service created.",
"frontend.catalog.service_updated": "Service updated.",
"frontend.catalog.invalid_icon": "Choose a valid Iconify icon reference.",

# Spanish
"frontend.catalog.new_service": "Nuevo servicio",
"frontend.catalog.edit_service": "Editar servicio",
"frontend.catalog.service_icon": "Icono del servicio",
"frontend.catalog.choose_icon": "Elegir icono",
"frontend.catalog.remove_icon": "Quitar icono",
"frontend.catalog.icon_optional_help": "Opcional. Si no eliges un icono, TrackPal muestra un icono genérico de servicio.",
"frontend.catalog.save_service": "Guardar servicio",
"frontend.catalog.service_created": "Servicio creado.",
"frontend.catalog.service_updated": "Servicio actualizado.",
"frontend.catalog.invalid_icon": "Elige una referencia de icono válida de Iconify.",
```

Replace rename-only Service success copy with `service_updated`; keep Plan rename copy unchanged.

- [ ] **Step 7: Run Catalog integration verification**

Run:

```bash
cd frontend
npm test -- src/features/admin/components/__tests__/service-form-dialog.spec.tsx src/features/admin/components/__tests__/catalog-page-demo.spec.tsx
npm run build
npm run lint
```

Expected: PASS; Demo Catalog mutations remain local and Plan/delete flows still render.

- [ ] **Step 8: Commit Task 7**

```bash
git add frontend/src/features/admin/components/service-form-dialog.tsx frontend/src/features/admin/components/__tests__/service-form-dialog.spec.tsx frontend/src/features/admin/components/catalog-page.tsx frontend/src/features/admin/components/__tests__/catalog-page-demo.spec.tsx backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py
git commit -m "feat(catalog): integrate service icon picker"
```

---

### Task 8: Render Service Icons on Subscription and Client Surfaces

**Files:**
- Modify: `frontend/src/features/admin/components/subscription-form-dialog.tsx`
- Modify: `frontend/src/features/admin/components/subscription-table.tsx`
- Modify: `frontend/src/features/admin/components/subscriptions-page.tsx`
- Create: `frontend/src/features/admin/components/__tests__/subscription-service-icons.spec.tsx`
- Modify: `frontend/src/features/client/services/client-dashboard-api.ts`
- Modify: `frontend/src/features/client/components/dashboard-page.tsx`
- Create: `frontend/src/features/client/components/__tests__/dashboard-page.spec.tsx`

**Interfaces:**
- Consumes: `ServiceIcon`, full `Service` records, and backend `service_icon`.
- Produces: consistent icon+name presentation in selectors, rows, cards, and Client dashboard.

- [ ] **Step 1: Write failing subscription surface tests**

Create `subscription-service-icons.spec.tsx`. Mock `ServiceIcon` to expose its inputs:

```tsx
vi.mock("@/features/catalog/components/service-icon", () => ({
  ServiceIcon: ({ icon, label }: { icon: string | null; label: string }) => (
    <span data-testid={`service-icon-${icon ?? "fallback"}`}>{label}</span>
  ),
}));
vi.mock("@/i18n", () => ({ t: (key: string) => key }));

const service = {
  id: "service-1",
  tenant_id: "tenant-1",
  name: "Netflix",
  icon: "simple-icons:netflix",
  created_at: "2026-07-01T00:00:00.000Z",
  updated_at: "2026-07-01T00:00:00.000Z",
};
const subscription = {
  id: "sub-1",
  tenant_id: "tenant-1",
  client_id: "client-1",
  service_id: service.id,
  plan_id: "plan-1",
  streaming_email: "client@example.test",
  profile_name: null,
  duration_type: "1_month",
  starts_at: "2026-07-01T00:00:00.000Z",
  expires_at: "2026-08-01T00:00:00.000Z",
  cancelled_at: null,
  status: "active",
  created_at: "2026-07-01T00:00:00.000Z",
  updated_at: "2026-07-01T00:00:00.000Z",
  has_password: false,
  has_pin: false,
};
```

Add these tests:

```tsx
it("renders icons in the selected Service and Service options", async () => {
  const editView = render(
    <SubscriptionFormDialog
      open
      mode="edit"
      subscription={subscription}
      clients={[]}
      services={[service]}
      plans={[]}
      loadingPlans={false}
      onServiceChange={vi.fn()}
      onSubmit={vi.fn().mockResolvedValue(undefined)}
      saving={false}
      error=""
      onOpenChange={vi.fn()}
    />,
  );

  expect(await screen.findByTestId("service-icon-simple-icons:netflix")).toHaveTextContent("Netflix");
  editView.unmount();

  render(
    <SubscriptionFormDialog
      open
      mode="create"
      clients={[]}
      services={[service]}
      plans={[]}
      loadingPlans={false}
      onServiceChange={vi.fn()}
      onSubmit={vi.fn().mockResolvedValue(undefined)}
      saving={false}
      error=""
      onOpenChange={vi.fn()}
    />,
  );
  await userEvent.click(screen.getAllByRole("combobox")[1]);
  expect(await screen.findByTestId("service-icon-simple-icons:netflix")).toHaveTextContent("Netflix");
});

it("renders icons in desktop and mobile Subscription summaries", () => {
  render(
    <SubscriptionTable
      subscriptions={[subscription]}
      clients={{ "client-1": "Client Demo" }}
      services={{ [service.id]: service }}
      plans={{ "plan-1": "Premium" }}
      onEdit={vi.fn()}
      onReveal={vi.fn()}
      onCancel={vi.fn()}
      onRenew={vi.fn()}
      onReactivate={vi.fn()}
    />,
  );

  expect(screen.getAllByTestId("service-icon-simple-icons:netflix")).toHaveLength(2);
  expect(screen.getAllByText("Netflix")).toHaveLength(2);
});
```

Pass `services` as actual `Service[]` or `Record<string, Service>`, never name-only maps.

- [ ] **Step 2: Write the failing Client dashboard test**

In `frontend/src/features/client/components/__tests__/dashboard-page.spec.tsx`, mock the dashboard fetch and shared renderer:

```tsx
const fetchClientDashboard = vi.hoisted(() => vi.fn());
vi.mock("../../services/client-dashboard-api", () => ({ fetchClientDashboard }));
vi.mock("@/features/catalog/components/service-icon", () => ({
  ServiceIcon: ({ icon, label }: { icon: string | null; label: string }) => (
    <span data-testid={`service-icon-${icon ?? "fallback"}`}>{label}</span>
  ),
}));
vi.mock("@/i18n", () => ({ t: (key: string) => key }));

it("shows Service Icons in desktop and mobile Client subscriptions", async () => {
  useAuthStore.setState({ isAuthenticated: true, role: "client" });
  fetchClientDashboard.mockResolvedValue({
    message: "ok",
    id: "client-1",
    full_name: "Client Demo",
    username: "client_demo",
    phone: null,
    tenant_id: "tenant-1",
    tenant_name: "Provider",
    client_prefix: "demo",
    is_active: true,
    subscriptions: [{
      id: "sub-1",
      service_name: "Netflix",
      service_icon: "simple-icons:netflix",
      plan_name: "Premium",
      status: "active",
      starts_at: "2026-07-01T00:00:00.000Z",
      expires_at: "2026-08-01T00:00:00.000Z",
    }],
  });

  render(<DashboardPage />);

  expect(await screen.findAllByTestId("service-icon-simple-icons:netflix")).toHaveLength(2);
  expect(screen.getAllByText("Netflix")).toHaveLength(2);
});
```

Reset the Auth Store and mocks in `beforeEach` so this test cannot inherit another role.

- [ ] **Step 3: Run the new tests and verify RED**

Run:

```bash
cd frontend
npm test -- src/features/admin/components/__tests__/subscription-service-icons.spec.tsx src/features/client/components/__tests__/dashboard-page.spec.tsx
```

Expected: FAIL because the surfaces render names only and the Client type has no `service_icon`.

- [ ] **Step 4: Pass Service records through SubscriptionsPage**

Replace:

```ts
const serviceMap = Object.fromEntries(services.map((s) => [s.id, s.name]));
```

with:

```ts
const serviceMap = Object.fromEntries(services.map((service) => [service.id, service]));
```

Keep filtering based on `serviceMap[id]?.name ?? ""`.

Change `SubscriptionTableProps.services` to `Record<string, Service>` and render:

```tsx
<div className="flex items-center gap-2">
  <ServiceIcon
    icon={services[sub.service_id]?.icon}
    label={services[sub.service_id]?.name ?? t("frontend.subscriptions.service")}
    className="size-5 shrink-0"
  />
  <span>{services[sub.service_id]?.name ?? "—"}</span>
</div>
```

Use the same pattern in mobile cards.

- [ ] **Step 5: Render icons in the subscription form**

For the selected trigger and every `SelectItem`, render `ServiceIcon` and Service name in a `flex items-center gap-2` wrapper. A null icon automatically uses the generic fallback.

- [ ] **Step 6: Add Client dashboard typing and rendering**

In `client-dashboard-api.ts`:

```ts
service_icon: string | null;
```

In desktop and mobile Client subscription views, place `ServiceIcon` beside `service_name` using `size-5` desktop and `size-6` mobile.

Do not add direct Iconify searching to subscription or Client modules; only the shared renderer may contact Iconify.

- [ ] **Step 7: Run related surface verification**

Run:

```bash
cd frontend
npm test -- src/features/admin/components/__tests__/subscription-service-icons.spec.tsx src/features/admin/components/__tests__/subscriptions-page-demo.spec.tsx src/features/client/components/__tests__/dashboard-page.spec.tsx
npm run build
```

Expected: PASS for production-shaped and Demo Service records.

- [ ] **Step 8: Commit Task 8**

```bash
git add frontend/src/features/admin/components/subscription-form-dialog.tsx frontend/src/features/admin/components/subscription-table.tsx frontend/src/features/admin/components/subscriptions-page.tsx frontend/src/features/admin/components/__tests__/subscription-service-icons.spec.tsx frontend/src/features/client/services/client-dashboard-api.ts frontend/src/features/client/components/dashboard-page.tsx frontend/src/features/client/components/__tests__/dashboard-page.spec.tsx
git commit -m "feat(catalog): show service icons across subscriptions"
```

---

### Task 9: Update Public Developer Handoff and User Help

**Files:**
- Modify: `frontend/src/features/admin/components/public-api-section.tsx`
- Modify: `frontend/src/features/admin/components/__tests__/public-api-section.spec.tsx`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py`
- Modify: `backend/help/en/tenant-admin/catalog.md`
- Modify: `backend/help/es/tenant-admin/catalog.md`
- Modify: `backend/help/en/tenant-admin/public-api.md`
- Modify: `backend/help/es/tenant-admin/public-api.md`
- Regenerate: `backend/app/help/artifact.json`

**Interfaces:**
- Consumes: public payload `service.icon`.
- Produces: provider-neutral Iconify SVG URL examples and bilingual user guidance.

- [ ] **Step 1: Write the failing developer handoff test**

Extend the existing handoff test:

```ts
expect(packageText).toContain("service.icon");
expect(packageText).toContain("https://api.iconify.design");
expect(packageText).toContain("prefix:name");
expect(packageText).toContain("YOUR_PUBLIC_API_KEY");
expect(packageText).not.toContain("tpk_abc");
```

- [ ] **Step 2: Run the public section test and verify RED**

Run:

```bash
cd frontend
npm test -- src/features/admin/components/__tests__/public-api-section.spec.tsx
```

Expected: FAIL because current examples fetch Catalog JSON but do not explain or render Icon References.

- [ ] **Step 3: Add an Icon Reference helper to every developer example**

Use the provider-neutral conversion:

```js
function iconUrl(icon) {
  if (!icon || !icon.includes(":")) return null;
  const [prefix, name] = icon.split(":", 2);
  return `https://api.iconify.design/${prefix}/${name}.svg`;
}
```

Each HTML, React, Vue, Svelte, Angular, and Alpine example must reference `service.icon`, call the equivalent helper, and retain a text or generic fallback when it returns `null`.

Add one handoff instruction line explaining that `service.icon` is an optional Iconify `prefix:name` reference and the browser contacts Iconify when displaying it.

- [ ] **Step 4: Update bilingual user Help sources**

In both Catalog topics, explain:

- Service Icon is optional;
- choose, replace, and remove are Web-only visual actions;
- WhatsApp continues to manage Service names and Plans as text;
- if Iconify is unavailable, save with the current or generic icon and retry later.

In both Public API topics, explain:

- public Services include optional `icon`;
- the developer package shows how to turn `prefix:name` into an Iconify SVG URL;
- the external website must provide a generic fallback;
- visitors' browsers contact Iconify directly.

Keep English/Spanish frontmatter metadata and links identical.

- [ ] **Step 5: Regenerate and verify private Help**

Run:

```bash
cd backend
uv run python -m scripts.compile_help
uv run python -m scripts.verify_help_release
uv run pytest tests/test_help_contract.py tests/test_help_hardening.py -q
```

Expected: compiler prints `Compiled private Help artifact`; release and tests PASS.

- [ ] **Step 6: Run frontend verification**

Run:

```bash
cd frontend
npm test -- src/features/admin/components/__tests__/public-api-section.spec.tsx
npm run build
```

Expected: PASS and all handoff languages still include `YOUR_PUBLIC_API_KEY` rather than a real key.

- [ ] **Step 7: Commit Task 9**

```bash
git add frontend/src/features/admin/components/public-api-section.tsx frontend/src/features/admin/components/__tests__/public-api-section.spec.tsx backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py backend/help/en/tenant-admin/catalog.md backend/help/es/tenant-admin/catalog.md backend/help/en/tenant-admin/public-api.md backend/help/es/tenant-admin/public-api.md backend/app/help/artifact.json
git commit -m "docs(catalog): explain service icon references"
```

---

### Task 10: Synchronize Architecture Documentation and Run Full Verification

**Files:**
- Modify: `docs/architecture/database-schema.md`
- Modify: `docs/architecture/api-layer.md`
- Modify: `docs/architecture/frontend-architecture.md`
- Modify: `docs/architecture/tenant-data-export.md`
- Modify: `docs/codebase/frontend-components.md`
- Modify: `docs/project-pdr/public-api-catalog.md`

**Interfaces:**
- Consumes: completed behavior from Tasks 1–9.
- Produces: current architectural, API, export, and component documentation.

- [ ] **Step 1: Update database and API documentation**

Document:

- `services.icon` as nullable `VARCHAR(255)` containing an Iconify `prefix:name` reference;
- local syntax validation and omitted-versus-null update semantics;
- `/catalog/services` and `/public/catalog` response examples with `icon`;
- `/dashboard` Client subscription item with `service_icon`;
- no backend Iconify network dependency.

- [ ] **Step 2: Update frontend architecture and component documentation**

Document the deep modules and interfaces:

```ts
IconPickerProps
IconCatalog.search(query, start, signal)
IconCatalog.describe(icon, signal)
ServiceIcon({ icon, label, className })
```

Describe the responsive split layout, license gate, 300 ms debounce, minimum two-character query, 64-result pages, retry behavior, and generic fallback.

Update CatalogPage documentation to state that create/edit uses one Service form dialog while Plan CRUD remains unchanged.

- [ ] **Step 3: Update export and public product contracts**

Document:

- `service_icon` in `service-catalog.csv` and JSON `service_catalog`;
- export format version `2`;
- public `icon: string | null` field;
- external browser/Iconify dependency and required fallback;
- no SVG asset ownership or storage by TrackPal.

- [ ] **Step 4: Run complete backend verification**

Run with the project-required timeout allowance:

```bash
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run alembic heads
```

Expected:

- full pytest suite PASS;
- Ruff check and format check PASS;
- exactly one Alembic head: `e021fe74cac1`.

- [ ] **Step 5: Run complete frontend verification**

Run:

```bash
cd frontend
npm test
npm run lint
npm run build
```

Expected: all Vitest tests PASS, ESLint reports no errors, and the strict TypeScript/Vite build succeeds.

- [ ] **Step 6: Inspect the final diff for prohibited behavior**

Run:

```bash
git grep -n "allsvgicons" -- backend frontend ':!docs/superpowers/**'
git grep -n "dangerouslySetInnerHTML" -- frontend/src/features/catalog frontend/src/features/admin frontend/src/features/client
git status --short
git diff --check
```

Expected:

- no runtime All SVG Icons scraping references;
- no raw SVG HTML rendering in the new modules;
- only the planned documentation files remain uncommitted;
- no whitespace errors.

- [ ] **Step 7: Perform the manual acceptance matrix**

Verify in a browser against mocked or development Iconify responses:

- desktop split layout and mobile stacked layout;
- light and dark themes;
- one multicolor icon and one monochrome icon;
- search, result selection, license link, load more, replace, remove, and cancel;
- simulated search 5xx and offline icon load with Service CRUD still usable;
- an existing production Service with `icon = null`;
- Pro Tenant, Master Support Context, and Pro Demo Account;
- subscription selector/table and Client dashboard fallback behavior.

Record any discovered defect as a failing automated test before changing production code.

- [ ] **Step 8: Commit Task 10**

```bash
git add docs/architecture/database-schema.md docs/architecture/api-layer.md docs/architecture/frontend-architecture.md docs/architecture/tenant-data-export.md docs/codebase/frontend-components.md docs/project-pdr/public-api-catalog.md
git commit -m "docs(catalog): document service icon selector"
```

- [ ] **Step 9: Confirm a clean working tree**

Run:

```bash
git status --short
```

Expected: no output.
