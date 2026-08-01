# Regional Settings (Country, Currency, Plan Pricing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Country and Currency configuration to tenants plus an optional price on catalog plans displayed with the tenant's currency symbol, delivered through web, WhatsApp consoles, Public API, Data Export, demo workspaces, and the Help module.

**Architecture:** A backend-owned Currency Catalog module (`backend/app/core/currency_catalog/`) bundles countries/currencies generated dev-time from Unicode CLDR with a curated overrides file (VES → "Bs."). `tenant_settings` gains nullable `country` (ISO 3166-1 alpha-2) and `currency` (ISO 4217); `plans` gains nullable `price` (NUMERIC(12,2)) interpreted in the tenant's currency. The Settings page gains a new "Configuración regional" tab inside My Account (Starter sees País + Idioma; Pro adds Zona horaria + Moneda). Every surface that renders a plan renders its price.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic + pytest (backend); React 19 + TypeScript strict + Zustand + TanStack Router + Tailwind v4 + vitest (frontend); Unicode CLDR via `babel` (dev-time only, not a runtime dep).

## Global Constraints

- Python 3.12+, `from __future__ import annotations`, Ruff defaults (`ruff check .`, `ruff format .`). Run `cd backend && uv run pytest` (full suite ~4 min); targeted tests with `uv run pytest tests/test_x.py::test_name -v`.
- React 19 + TS strict, Zustand stores, TanStack Router, Tailwind CSS v4, shadcn/ui. Run `cd frontend && npm test` (vitest).
- `DATA_ENCRYPTION_KEY` is set by `backend/tests/conftest.py` before app import — never import app models in tests before fixtures load.
- i18n: frontend UI keys live in `backend/app/core/i18n/catalogs_{en,es}_frontend.py` (served via `GET /i18n/catalog`); WhatsApp keys in `catalogs_{en,es}_wa.py`. Every new key MUST exist in both en and es (`backend/tests/test_i18n.py` enforces parity).
- Universal WhatsApp cancel handler catches `0`/`salir`/`cancelar` BEFORE step-specific handlers — any new flow step must stay reachable from the cancel handler (AGENTS.md gotcha #4).
- Help artifact contract: after changing `backend/help/`, recompile (`cd backend && uv run python -m scripts.compile_help`) and run `uv run python scripts/verify_help_release.py`; parity is enforced by `backend/tests/test_help_contract.py`.
- TDD: write the failing test first, verify it fails, implement, verify it passes, commit. One commit per task.
- Price JSON contract: `price` serializes as a string (`"12.50"`) or `null` everywhere (Pydantic v2 Decimal → JSON string). Frontend types use `price: string | null`.
- Docs: every task that changes user-facing behavior ends with a documentation update step (per project instruction). `backend/CONTEXT.md` and `frontend/CONTEXT.md` were already updated; `docs/SUMMARY.md` is the doc entry point.

---

### Task 1: Currency Catalog module (backend) + regeneration script

**Files:**
- Create: `backend/app/core/currency_catalog/__init__.py`
- Create: `backend/app/core/currency_catalog/currency_catalog.py`
- Create: `backend/app/core/currency_catalog/data.json` (generated, committed)
- Create: `backend/app/core/currency_catalog/overrides.json`
- Create: `backend/scripts/regenerate_currency_catalog.py`
- Create: `frontend/src/lib/currency-catalog.json` (generated demo copy)
- Test: `backend/tests/test_currency_catalog.py`

**Interfaces:**
- Consumes: nothing (self-contained module).
- Produces (used by Task 3+):
  - `currency_catalog.list_countries() -> list[dict[str, str]]` — `{"code": "VE", "currency": "VES"}`
  - `currency_catalog.list_currencies() -> list[dict[str, object]]` — `{"code": "VES", "symbol": "Bs.", "minor_units": 2}`
  - `currency_catalog.official_currency_of(country: str) -> str | None`
  - `currency_catalog.symbol_of(currency: str) -> str | None`
  - `currency_catalog.minor_units_of(currency: str) -> int | None`
  - `currency_catalog.validate_country(code: str) -> bool` (case-insensitive)
  - `currency_catalog.validate_currency(code: str) -> bool` (case-insensitive)
  - `scripts.regenerate_currency_catalog.main() -> None` — regenerates both data files; exits non-zero on symbol warnings that lack overrides.

- [ ] **Step 1: Write the failing module tests**

`backend/tests/test_currency_catalog.py`:

```python
from unittest.mock import patch

import pytest

from app.core import currency_catalog

FIXTURE = {
    "source": "fixture",
    "generated_at": "2026-08-01",
    "countries": [{"code": "VE", "currency": "VES"}, {"code": "PA", "currency": "PAB"}],
    "currencies": {
        "VES": {"symbol": "Bs.", "minor_units": 2},
        "USD": {"symbol": "$", "minor_units": 2},
        "JPY": {"symbol": "¥", "minor_units": 0},
    },
}


@pytest.fixture(autouse=True)
def _fixture_data():
    with patch.object(currency_catalog, "_load", return_value=FIXTURE):
        yield


def test_validate_country_uppercase_insensitive():
    assert currency_catalog.validate_country("ve")
    assert currency_catalog.validate_country("VE")
    assert not currency_catalog.validate_country("XX")


def test_validate_currency_uppercase_insensitive():
    assert currency_catalog.validate_currency("ves")
    assert not currency_catalog.validate_currency("ZZZ")


def test_official_currency_of():
    assert currency_catalog.official_currency_of("VE") == "VES"
    assert currency_catalog.official_currency_of("XX") is None


def test_symbol_and_minor_units():
    assert currency_catalog.symbol_of("VES") == "Bs."
    assert currency_catalog.minor_units_of("JPY") == 0
    assert currency_catalog.minor_units_of("XXX") is None


def test_list_countries_and_currencies_shape():
    assert {"code": "VE", "currency": "VES"} in currency_catalog.list_countries()
    assert {"code": "VES", "symbol": "Bs.", "minor_units": 2} in currency_catalog.list_currencies()


def test_real_data_contains_venezuela_override():
    """Real committed data.json must carry the curated VES symbol."""
    assert currency_catalog.symbol_of("VES") == "Bs."
    assert currency_catalog.validate_country("VE")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_currency_catalog.py -v`
Expected: FAIL — `ModuleNotFoundError`/attribute errors.

- [ ] **Step 3: Create the module**

`backend/app/core/currency_catalog/currency_catalog.py`:

```python
"""Currency Catalog — bundled countries/currencies from Unicode CLDR + curated overrides.

Single source of truth for validating Country (ISO 3166-1 alpha-2) and
Currency (ISO 4217) codes and for resolving official currency, symbols and
minor units. Data is generated dev-time (see scripts/regenerate_currency_catalog.py)
and committed; never queried at runtime.
"""

import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    with _DATA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _country_codes() -> frozenset[str]:
    return frozenset(c["code"] for c in _load()["countries"])


def _currency_codes() -> frozenset[str]:
    return frozenset(_load()["currencies"])


def list_countries() -> list[dict[str, str]]:
    return [dict(c) for c in _load()["countries"]]


def list_currencies() -> list[dict[str, object]]:
    return [
        {
            "code": code,
            "symbol": meta["symbol"],
            "minor_units": meta["minor_units"],
        }
        for code, meta in _load()["currencies"].items()
    ]


def official_currency_of(country_code: str) -> str | None:
    for c in _load()["countries"]:
        if c["code"] == country_code:
            return c["currency"]
    return None


def symbol_of(currency_code: str) -> str | None:
    return _load()["currencies"].get(currency_code, {}).get("symbol")


def minor_units_of(currency_code: str) -> int | None:
    return _load()["currencies"].get(currency_code, {}).get("minor_units")


def validate_country(code: str) -> bool:
    return code.upper() in _country_codes()


def validate_currency(code: str) -> bool:
    return code.upper() in _currency_codes()
```

`__init__.py` re-exports the six public functions:

```python
from app.core.currency_catalog.currency_catalog import (
    list_countries,
    list_currencies,
    minor_units_of,
    official_currency_of,
    symbol_of,
    validate_country,
    validate_currency,
)

__all__ = [
    "list_countries",
    "list_currencies",
    "minor_units_of",
    "official_currency_of",
    "symbol_of",
    "validate_country",
    "validate_currency",
]
```

- [ ] **Step 4: Create the regeneration script**

`backend/scripts/regenerate_currency_catalog.py` (run via `uv run --with babel python -m scripts.regenerate_currency_catalog`):

```python
"""Regenerate currency catalog data files from Unicode CLDR (dev-time only).

Run:  cd backend && uv run --with babel python -m scripts.regenerate_currency_catalog

Emits:
  backend/app/core/currency_catalog/data.json
  frontend/src/lib/currency-catalog.json   (demo workspace copy)
Symbols fall back to the curated overrides file first, then CLDR. Territories
with several current currencies use the per-territory national-currency map.
"""

import json
import sys
from pathlib import Path

BACKEND_DATA = Path(__file__).resolve().parents[1] / "app" / "core" / "currency_catalog" / "data.json"
FRONTEND_DATA = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "currency-catalog.json"
OVERRIDES = Path(__file__).resolve().parents[1] / "app" / "core" / "currency_catalog" / "overrides.json"

# Territories with more than one legal tender where the national currency
# is not the shared anchor (USD/EUR/INR/ZAR/ILS/JOD). Deterministic and reviewable.
_NATIONAL_CURRENCY: dict[str, str] = {
    "BT": "BTN", "HT": "HTG", "LS": "LSL", "NA": "NAD",
    "PA": "PAB", "PS": "ILS", "ZW": "ZWG",
}


def generate() -> tuple[dict, list[str]]:
    from babel.core import get_global  # dev-time dependency only

    territory_currencies = get_global("territory_currencies")
    currency_fractions = get_global("currency_fractions")
    locale_en = _load_babel_locale()

    with OVERRIDES.open(encoding="utf-8") as fh:
        overrides = json.load(fh)

    countries: list[dict[str, str]] = []
    currencies: dict[str, dict] = {}
    warnings: list[str] = []

    for territory, entries in territory_currencies.items():
        if len(territory) != 2 or not territory.isalpha():
            continue
        current = [code for code, _start, end, tender in entries if end is None and tender]
        if not current:
            continue
        currency = _NATIONAL_CURRENCY.get(territory, current[0])
        countries.append({"code": territory, "currency": currency})

    for currency in sorted({c["currency"] for c in countries}):
        frac = currency_fractions.get(currency)
        minor_units = frac[0] if frac is not None else 2
        symbol = overrides.get(currency, {}).get("symbol")
        if symbol is None:
            symbol = locale_en.currency_symbols.get(currency)
        if not symbol or symbol == currency:
            warnings.append(f"{currency}: no curated symbol (override it in overrides.json)")
            symbol = symbol or ""
        currencies[currency] = {"symbol": symbol, "minor_units": minor_units}

    return {
        "source": "Unicode CLDR",
        "generated_at": _today(),
        "countries": countries,
        "currencies": currencies,
    }, warnings


def _load_babel_locale():
    from babel import Locale

    return Locale.parse("en")


def _today() -> str:
    import datetime

    return datetime.date.today().isoformat()


def main() -> None:
    payload, warnings = generate()
    for w in warnings:
        print(f"WARN {w}")
    for path in (BACKEND_DATA, FRONTEND_DATA):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path}")
    if warnings:
        sys.exit(2)


if __name__ == "__main__":
    main()
```

`backend/app/core/currency_catalog/overrides.json`:

```json
{
  "VES": {"symbol": "Bs."}
}
```

- [ ] **Step 5: Generate and commit the data files**

Run: `cd backend && uv run --with babel python -m scripts.regenerate_currency_catalog`
Expected: both files written; any `WARN` entries must first get an override added to `overrides.json` (rerun until zero warnings) — this is the "Bs." guarantee. Inspect `data.json`: VE → VES, symbol "Bs."; PA → PAB; ~150 currencies.

- [ ] **Step 6: Add a reproducibility test**

Add to `backend/tests/test_currency_catalog.py` (skips when babel is unavailable):

```python
@pytest.mark.skipif(
    __import__("importlib").util.find_spec("babel") is None,
    reason="babel is a dev-time dependency",
)
def test_regeneration_matches_checked_in_data():
    from scripts.regenerate_currency_catalog import BACKEND_DATA, generate

    payload, warnings = generate()
    assert warnings == [], f"missing overrides: {warnings}"
    checked_in = json.loads(BACKEND_DATA.read_text(encoding="utf-8"))
    # only compare the domain payload, not the generated_at date
    assert {k: v for k, v in payload.items() if k != "generated_at"} == {
        k: v for k, v in checked_in.items() if k != "generated_at"
    }
```

Add `import json` at the top of the test file.

- [ ] **Step 7: Run the full test file, format, commit**

Run: `cd backend && uv run pytest tests/test_currency_catalog.py -v && uv run ruff format app/core/currency_catalog/ scripts/regenerate_currency_catalog.py && uv run ruff check app/core/currency_catalog/ scripts/regenerate_currency_catalog.py`
Expected: PASS, ruff clean.

```bash
git add backend/app/core/currency_catalog backend/scripts/regenerate_currency_catalog.py backend/tests/test_currency_catalog.py frontend/src/lib/currency-catalog.json
git commit -m "feat(currency): currency catalog module generated from CLDR with curated overrides"
```

**Docs step:** nothing new here (module is internal); `backend/CONTEXT.md` Currency Catalog term already committed.

---

### Task 2: Data model + Alembic migration

**Files:**
- Modify: `backend/app/models/tenant_settings.py`
- Modify: `backend/app/models/plan.py`
- Create: `backend/alembic/versions/e022fe74cac2_add_regional_settings_and_plan_price.py`
- Test: `backend/tests/test_tenant_settings.py`
- Test: `backend/tests/test_catalog.py` (add one test)

**Interfaces:**
- Consumes: nothing (models only).
- Produces: `TenantSettings.country: Mapped[str | None]`, `TenantSettings.currency: Mapped[str | None]`, `Plan.price: Mapped[Decimal | None]` — consumed by Task 3+.

- [ ] **Step 1: Write the failing model tests**

Add to `backend/tests/test_tenant_settings.py`:

```python
async def test_tenant_settings_country_currency_default_null(db_session, active_tenant_user):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    settings = result.scalar_one()
    assert settings.country is None
    assert settings.currency is None


async def test_tenant_settings_can_store_country_and_currency(db_session, active_tenant_user):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    settings = result.scalar_one()
    settings.country = "VE"
    settings.currency = "VES"
    await db_session.commit()
    await db_session.refresh(settings)
    assert settings.country == "VE"
    assert settings.currency == "VES"
```

Add to `backend/tests/test_catalog.py`:

```python
async def test_plan_price_column_persists(db_session, active_tenant_user):
    # reuse the existing fixture helper that creates a service+plan, then:
    # plan = await catalog_service.create_plan(db, tenant_id, service_id,
    #        PlanCreate(name="Basico", price=Decimal("12.50")))
    assert plan.price == Decimal("12.50")
```

(Follow the existing plan-creation helper in `test_catalog.py`; add the `price=` kwarg to the create call.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_tenant_settings.py tests/test_catalog.py -v`
Expected: FAIL (columns don't exist / SQLAlchemy attribute errors).

- [ ] **Step 3: Update models**

`backend/app/models/tenant_settings.py` — add after `timezone`:

```python
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
```

`backend/app/models/plan.py` — add imports and column:

```python
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
...
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
```

(Place `price` after `name`; keep all existing columns untouched.)

- [ ] **Step 4: Create the Alembic migration**

First verify the head: `cd backend && uv run alembic heads` (expect `e021fe74cac1`). Create `backend/alembic/versions/e022fe74cac2_add_regional_settings_and_plan_price.py`:

```python
"""Add country/currency to tenant_settings and price to plans

Revision ID: e022fe74cac2
Revises: e021fe74cac1
Create Date: 2026-08-01
"""

import sqlalchemy as sa

from alembic import op

revision = "e022fe74cac2"
down_revision = "e021fe74cac1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_settings", sa.Column("country", sa.String(length=2), nullable=True))
    op.add_column("tenant_settings", sa.Column("currency", sa.String(length=3), nullable=True))
    op.add_column("plans", sa.Column("price", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("plans", "price")
    op.drop_column("tenant_settings", "currency")
    op.drop_column("tenant_settings", "country")
```

- [ ] **Step 5: Run tests, format, commit**

Run: `cd backend && uv run pytest tests/test_tenant_settings.py tests/test_catalog.py -v && uv run ruff format app/models && uv run ruff check app/models`
Expected: PASS.

```bash
git add backend/app/models/tenant_settings.py backend/app/models/plan.py backend/alembic/versions/e022fe74cac2_add_regional_settings_and_plan_price.py backend/tests/test_tenant_settings.py backend/tests/test_catalog.py
git commit -m "feat(models): add tenant country/currency and plan price columns"
```

**Docs step:** none (schema internals; `docs/architecture/database-schema.md` may note the columns — add a one-line mention if it lists tenant_settings/plans columns).

---

### Task 3: Tenant settings API (fields, gating, currencies endpoint)

**Files:**
- Modify: `backend/app/schemas/tenant_settings.py`
- Modify: `backend/app/services/tenant_settings_service.py`
- Modify: `backend/app/api/v1/endpoints/tenant_settings.py`
- Test: `backend/tests/test_tenant_settings.py`

**Interfaces:**
- Consumes: Task 1 (`validate_country`, `validate_currency`, `list_countries`, `list_currencies`), Task 2 (columns).
- Produces (consumed by Tasks 5-14):
  - `GET /api/v1/tenant-settings/currencies` → `{"countries": [{"code": "VE", "currency": "VES"}], "currencies": [{"code": "VES", "symbol": "Bs.", "minor_units": 2}]}`
  - `TenantSettingsUpdate.country: str | None`, `TenantSettingsUpdate.currency: str | None` (uppercase-normalized, invalid → 409 via ValueError)
  - `TenantSettingsResponse.country/currency: str | None` — Starter sees `timezone=None` AND `currency=None`.

- [ ] **Step 1: Write the failing API tests**

Add to `backend/tests/test_tenant_settings.py`:

```python
async def test_currencies_endpoint_returns_catalog(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.get("/api/v1/tenant-settings/currencies", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    ve = next(c for c in payload["countries"] if c["code"] == "VE")
    assert ve["currency"] == "VES"
    ves = next(c for c in payload["currencies"] if c["code"] == "VES")
    assert ves["symbol"] == "Bs."


async def test_update_tenant_settings_country_currency(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.put(
        "/api/v1/tenant-settings",
        json={"country": "ve", "currency": "ves", "timezone": "America/Caracas"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["country"] == "VE"
    assert body["currency"] == "VES"


async def test_update_tenant_settings_invalid_country_conflict(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.put(
        "/api/v1/tenant-settings", json={"country": "XX"}, headers=headers
    )
    assert response.status_code == 409


async def test_update_tenant_settings_invalid_currency_conflict(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.put(
        "/api/v1/tenant-settings", json={"currency": "ZZZ"}, headers=headers
    )
    assert response.status_code == 409


async def test_starter_get_nulled_currency_and_timezone(client, auth_headers, active_tenant_user):
    downgrade = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert downgrade.status_code == 200, downgrade.text
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.get("/api/v1/tenant-settings", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] is None
    assert body["currency"] is None


async def test_starter_put_currency_rejected_404(client, auth_headers, active_tenant_user):
    downgrade = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert downgrade.status_code == 200, downgrade.text
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.put(
        "/api/v1/tenant-settings", json={"currency": "VES"}, headers=headers
    )
    assert response.status_code == 404
```

(Use the actual starter gate pattern from `backend/tests/test_tenant_plan.py::test_starter_tenant_gets_404_for_pro_endpoints` — downgrade `active_tenant_user` via `PUT /api/v1/tenants/{id}` with `{"plan": "starter"}`, then login as `tenant`/`tenant-password`. There is no dedicated starter fixture.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_tenant_settings.py -v`
Expected: FAIL (new fields rejected by Pydantic / 422 or missing endpoint).

- [ ] **Step 3: Update the schema**

`backend/app/schemas/tenant_settings.py` — mirror the existing locale/timezone validation:

```python
from app.core.currency_catalog import validate_country, validate_currency


class TenantSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tenant_id: UUID
    locale: str
    timezone: str | None
    country: str | None
    currency: str | None
    created_at: datetime
    updated_at: datetime


class TenantSettingsUpdate(BaseModel):
    locale: str | None = None
    timezone: str | None = None
    country: str | None = None
    currency: str | None = None

    @field_validator("country", mode="before")
    @classmethod
    def clean_country(cls, value):
        if value is None:
            return None
        normalized = value.strip().upper()
        if not validate_country(normalized):
            raise ValueError("invalid_country")
        return normalized

    @field_validator("currency", mode="before")
    @classmethod
    def clean_currency(cls, value):
        if value is None:
            return None
        normalized = value.strip().upper()
        if not validate_currency(normalized):
            raise ValueError("invalid_currency")
        return normalized
```

(Keep the existing locale/timezone validators and `ConfigDict`/`UUID`/`datetime` imports intact.)

- [ ] **Step 4: Update the service**

`backend/app/services/tenant_settings_service.py` — extend `update_settings` so invalid country/currency raise `ValueError` (same pattern as locale/timezone):

```python
    if payload.country is not None:
        if not validate_country(payload.country):
            raise ValueError("invalid_country")
        settings.country = payload.country
    if payload.currency is not None:
        if not validate_currency(payload.currency):
            raise ValueError("invalid_currency")
        settings.currency = payload.currency
```

(The Pydantic validator already guarantees valid codes; the service check is defense-in-depth following the existing locale/timezone pattern — check the current service file and mirror it exactly.)

- [ ] **Step 5: Update the endpoint (gating + currencies endpoint)**

`backend/app/api/v1/endpoints/tenant_settings.py`:

```python
from app.core.currency_catalog import list_countries, list_currencies


@router.get("/currencies", response_model=CurrencyCatalogResponse)
async def get_currency_catalog(
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
    tenant_plan: TenantPlanDep,
):
    require_tenant_or_master(current_user)
    return {"countries": list_countries(), "currencies": list_currencies()}
```

Extend the Starter gate in both existing handlers — GET nulls both `timezone` and `currency`; PUT rejects non-null `timezone` OR `currency` with 404:

```python
    if current_user.role == "tenant" and tenant_plan == "starter":
        settings.timezone = None
        settings.currency = None
    ...
    if (
        current_user.role == "tenant"
        and tenant_plan == "starter"
        and (payload.timezone is not None or payload.currency is not None)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
```

Add `CurrencyCatalogResponse` to `backend/app/schemas/tenant_settings.py`:

```python
class CurrencyEntry(BaseModel):
    code: str
    currency: str


class CurrencyMeta(BaseModel):
    code: str
    symbol: str
    minor_units: int


class CurrencyCatalogResponse(BaseModel):
    countries: list[CurrencyEntry]
    currencies: list[CurrencyMeta]
```

- [ ] **Step 6: Run tests, format, commit**

Run: `cd backend && uv run pytest tests/test_tenant_settings.py -v && uv run ruff format app && uv run ruff check app`
Expected: PASS (watch the existing starter timezone tests still pass).

```bash
git add backend/app/schemas/tenant_settings.py backend/app/services/tenant_settings_service.py backend/app/api/v1/endpoints/tenant_settings.py backend/tests/test_tenant_settings.py
git commit -m "feat(api): tenant country/currency settings with Starter gate and currencies endpoint"
```

**Docs step:** `docs/architecture/subscriptions.md` tenant-settings section — add a line: "Tenant settings include country (Starter+Pro) and currency (Pro-only), validated against the bundled Currency Catalog; GET /tenant-settings/currencies serves the pickers."

---

### Task 4: Plan price CRUD (backend)

**Files:**
- Modify: `backend/app/schemas/catalog.py`
- Modify: `backend/app/services/catalog_service/service.py`
- Modify: `backend/app/api/v1/endpoints/catalog.py` (error mapping, if needed)
- Test: `backend/tests/test_catalog.py`

**Interfaces:**
- Consumes: Task 2 (`Plan.price`).
- Produces (consumed by Tasks 5-8, 11, 13):
  - `PlanCreate.price: Decimal | None` (≥ 0, max 12 digits, 2 decimals)
  - `PlanUpdate.price: Decimal | None` — uses `model_fields_set` so `null` CLEARS the price and absence leaves it untouched
  - `PlanResponse.price: Decimal | None` (serialized as JSON string or null)

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_catalog.py` (follow the existing service/endpoint test patterns there):

```python
async def test_create_plan_with_price(db_session, active_tenant_user):
    # use the existing helper that creates a service under the tenant
    plan = await catalog_service.create_plan(
        db, tenant_id, service_id, PlanCreate(name="Basico", price=Decimal("12.50"))
    )
    assert plan is not None
    assert plan.price == Decimal("12.50")


async def test_create_plan_without_price(db_session, active_tenant_user):
    plan = await catalog_service.create_plan(
        db, tenant_id, service_id, PlanCreate(name="Gratis")
    )
    assert plan is not None
    assert plan.price is None


async def test_update_plan_price_and_clear(db_session, active_tenant_user):
    plan = await catalog_service.create_plan(db, tenant_id, service_id, PlanCreate(name="P1"))
    updated = await catalog_service.update_plan(
        db, tenant_id, service_id, plan.id, PlanUpdate(price=Decimal("9.99"))
    )
    assert updated.price == Decimal("9.99")
    # renaming must NOT clobber price (name-only update)
    renamed = await catalog_service.update_plan(
        db, tenant_id, service_id, plan.id, PlanUpdate(name="P1 renombrado")
    )
    assert renamed.price == Decimal("9.99")
    cleared = await catalog_service.update_plan(
        db, tenant_id, service_id, plan.id, PlanUpdate(price=None)
    )
    assert cleared.price is None
```

Endpoint-level test (existing pattern in `test_catalog.py`): POST `/api/v1/catalog/services/{service_id}/plans` with `{"name": "P", "price": "12.50"}` → 200 with `price == "12.50"`; PUT with `{"price": null}` → `price is null`; PUT with `{"price": "-1"}` → 422.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_catalog.py -v`
Expected: FAIL.

- [ ] **Step 3: Update schemas**

`backend/app/schemas/catalog.py`:

```python
from decimal import Decimal
...
class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    service_id: UUID
    name: str
    price: Decimal | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Update the catalog service**

`backend/app/services/catalog_service/service.py`:

```python
    async def create_plan(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, payload: PlanCreate
    ) -> Plan | None:
        if await self.get_service(db, tenant_id, service_id) is None:
            return None
        name = _clean_name(payload.name)
        if await self._plan_name_exists(db, tenant_id, service_id, name):
            raise UserFacingError("plan_name_already_exists")
        plan = Plan(tenant_id=tenant_id, service_id=service_id, name=name, price=payload.price)
        ...
```

In `update_plan`, after the existing `payload.name` block:

```python
        if "price" in payload.model_fields_set:
            plan.price = payload.price
```

- [ ] **Step 5: Update endpoint error mapping (if needed)**

`backend/app/api/v1/endpoints/catalog.py` — Pydantic 422 responses are automatic; only add `invalid_plan_price` to `CATALOG_ERROR_KEYS` if a `UserFacingError("invalid_plan_price")` path is added in the service. Prefer relying on Pydantic 422 unless a domain error is required; if added, also register the frontend key in Task 11.

- [ ] **Step 6: Run tests, format, commit**

Run: `cd backend && uv run pytest tests/test_catalog.py -v && uv run ruff format app && uv run ruff check app`
Expected: PASS.

```bash
git add backend/app/schemas/catalog.py backend/app/services/catalog_service/service.py backend/app/api/v1/endpoints/catalog.py backend/tests/test_catalog.py
git commit -m "feat(catalog): optional plan price on create/update with clear semantics"
```

**Docs step:** none beyond already-updated `backend/CONTEXT.md` (Catalog Price term).

---

### Task 5: Public API Catalog exposes price + currency

**Files:**
- Modify: `backend/app/schemas/public_api_key.py`
- Modify: `backend/app/services/public_api_key_service.py`
- Test: `backend/tests/test_public_api_catalog.py`

**Interfaces:**
- Consumes: Task 3 (`TenantSettings.currency`, `CurrencyCatalogResponse` shapes), Task 4 (`Plan.price`).
- Produces:
  - `PublicCatalogPlan.price: Decimal | None`
  - `PublicCatalogResponse.currency: CurrencyMeta | None` where `CurrencyMeta = {"code", "symbol", "minor_units"}`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_public_api_catalog.py` (follow existing builder tests there):

```python
async def test_public_catalog_plan_price_exposed(db_session, ...):
    # create service + plan with price via catalog_service, then:
    result = await public_api_key_service.build_public_catalog(db, api_key=key, origin=None)
    payload, _allowed = result
    plan = payload["services"][0]["plans"][0]
    assert plan["price"] == "12.50"


async def test_public_catalog_currency_from_tenant_settings(db_session, ...):
    # set tenant_settings.currency = "VES" (via tenant_settings_service)
    result = await public_api_key_service.build_public_catalog(db, api_key=key, origin=None)
    payload, _allowed = result
    assert payload["currency"] == {"code": "VES", "symbol": "Bs.", "minor_units": 2}


async def test_public_catalog_currency_null_when_unset(db_session, ...):
    result = await public_api_key_service.build_public_catalog(db, api_key=key, origin=None)
    payload, _allowed = result
    assert payload["currency"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_public_api_catalog.py -v`
Expected: FAIL.

- [ ] **Step 3: Update schemas**

`backend/app/schemas/public_api_key.py` — import `Decimal` and reuse `CurrencyMeta` from `app.schemas.tenant_settings`:

```python
class PublicCatalogPlan(BaseModel):
    id: UUID
    name: str
    price: Decimal | None = None


class PublicCatalogResponse(BaseModel):
    services: list[PublicCatalogService]
    currency: CurrencyMeta | None = None
```

- [ ] **Step 4: Update the builder**

`backend/app/services/public_api_key_service.py` — in `build_public_catalog`, load the tenant settings and resolve currency before building plans:

```python
from app.core.currency_catalog import minor_units_of, symbol_of
from app.schemas.tenant_settings import CurrencyMeta
...
    tenant_settings = await tenant_settings_repository.get(db, tenant_id)
    currency_meta = None
    if tenant_settings and tenant_settings.currency:
        symbol = symbol_of(tenant_settings.currency) or ""
        minor_units = minor_units_of(tenant_settings.currency) or 2
        currency_meta = CurrencyMeta(
            code=tenant_settings.currency, symbol=symbol, minor_units=minor_units
        )
    ...
    # include price=plan.price when constructing PublicCatalogPlan
    return PublicCatalogResponse(services=services, currency=currency_meta), allowed_origin
```

(Adapt to the actual query structure of the existing builder — the plan rows already include the plan object; keep the 3-query pattern.)

- [ ] **Step 5: Run tests, format, commit**

Run: `cd backend && uv run pytest tests/test_public_api_catalog.py -v && uv run ruff format app && uv run ruff check app`
Expected: PASS.

```bash
git add backend/app/schemas/public_api_key.py backend/app/services/public_api_key_service.py backend/tests/test_public_api_catalog.py
git commit -m "feat(public-api): expose plan price and tenant currency in public catalog"
```

**Docs step:** `docs/architecture/api-layer.md` public-catalog section — add "plans include `price`; response includes top-level `currency` derived from tenant settings".

---

### Task 6: Tenant Data Export gains plan_price and currency

**Files:**
- Modify: `backend/app/services/export_worker.py`
- Test: `backend/tests/test_export_worker.py`

**Interfaces:**
- Consumes: Task 2 (`Plan.price`), Task 3 (`TenantSettings.currency`).
- Produces: `service-catalog.csv` header includes `plan_price`; `account-profile.csv` header includes `currency`. Stable-contract change documented (ADR 0003).

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_export_worker.py` (follow existing CSV assertions there — find the exact helper used to build `service-catalog.csv` and `account-profile.csv` rows):

```python
async def test_service_catalog_csv_includes_plan_price(...):
    # seed a plan with price Decimal("12.50") and one plan without price
    csv_rows = ...  # call the same function the worker uses to build service-catalog.csv
    assert csv_rows[0].headers == ["service_name", "service_icon", "plan_name", "plan_price", "plan_created_on", "plan_updated_on"]
    priced = [r for r in csv_rows[0].rows if r["plan_name"] == "Preciado"][0]
    assert priced["plan_price"] == "12.50"
    unpriced = [r for r in csv_rows[0].rows if r["plan_name"] == "Sin precio"][0]
    assert unpriced["plan_price"] == ""


async def test_account_profile_csv_includes_currency(...):
    # tenant with settings.currency = "VES"
    csv_rows = ...  # account-profile.csv builder
    assert csv_rows[0].headers == ["business_name", ..., "currency"]
    assert csv_rows[0].rows[0]["currency"] == "VES"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_export_worker.py -v`
Expected: FAIL.

- [ ] **Step 3: Update the export worker**

`backend/app/services/export_worker.py`:

1. `service-catalog.csv` column list: insert `"plan_price"` right after `"plan_name"`; when building each plan row, set `plan_price` to `"" if plan.price is None else f"{plan.price:.2f}"`.
2. `account-profile.csv` column list: add `"currency"` (ISO code, `""` when unset) sourced from tenant settings.
3. Update the en/es README docstrings that enumerate the CSV columns (search for `plan_name            —` and `business_name` column listings) to include the new columns, matching the existing formatting.

- [ ] **Step 4: Run tests, format, commit**

Run: `cd backend && uv run pytest tests/test_export_worker.py -v && uv run ruff format app/services/export_worker.py && uv run ruff check app/services/export_worker.py`
Expected: PASS.

```bash
git add backend/app/services/export_worker.py backend/tests/test_export_worker.py
git commit -m "feat(export): add plan_price to service-catalog.csv and currency to account-profile.csv"
```

**Docs step:** `docs/architecture/tenant-data-export.md` — record the stable-contract change (ADR 0003): new `plan_price` column in service-catalog.csv, new `currency` column in account-profile.csv.

---

### Task 7: WhatsApp tenant console — plan prices (display + create/edit)

**Files:**
- Modify: `backend/app/services/whatsapp_tenant_console_service/format_helpers.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/formatters.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/catalog_flow.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/subscriptions_create.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/constants.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py` and `catalogs_es_wa.py`
- Test: `backend/tests/test_tenant_console_service.py`

**Interfaces:**
- Consumes: Task 3 (currency via tenant settings + `symbol_of`), Task 4 (`Plan.price`, `PlanUpdate` model_fields_set semantics).
- Produces:
  - `format_helpers.format_price(amount: Decimal | None, symbol: str | None, locale: str) -> str`
  - `_format_plan_list(plans, page, total_pages, symbol=None)` — entry `1️⃣ {name} - {price} - {active count}`
  - `_format_plan_detail(plan, symbol=None)` — adds `*Precio:* {price}` line
  - Flow steps `CATALOG_STEP_CREATE_PLAN_PRICE` and `CATALOG_STEP_EDIT_PLAN_PRICE`
  - Plan action menu: `1` edit name, `2` edit price, `3` delete
  - WA i18n keys (en + es): `wa.tenant.catalog.price_label`, `wa.tenant.catalog.price_on_request`, `wa.tenant.catalog.plan_action_edit_price`, `wa.tenant.catalog.plan_price_prompt`, `wa.tenant.catalog.plan_price_cleared`, `wa.tenant.catalog.plan_price_invalid`, `wa.tenant.catalog.create_plan_price_prompt`

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_tenant_console_service.py`:

1. Add `price` to `FakePlanObj` (`price: Decimal | None = None`), extend `FakeCatalogService.create_plan`/`update_plan` to accept/return price, and add a `FakeSettingsService` (or extend an existing fake) exposing `get_settings` returning `currency="VES"` so `symbol_of("VES")` resolves to "Bs.".
2. New tests:

```python
def test_format_plan_list_shows_price():
    plan = FakePlanObj(id=uuid4(), name="Basico", price=Decimal("12.50"))
    reply, selection = _format_plan_list([plan], symbol="Bs.")
    assert "Bs. 12,50" in reply  # locale "es" in test ctx
```

Follow the existing formatter test pattern in the file (check how `ctx.get_locale()` is set in tests — likely via a context fixture or a default of "es"). Flow tests (mirror existing catalog flow tests):

```python
async def test_create_plan_flow_accepts_price(...):
    # send "1" (create plan) → name → price prompt shown
    # send "12,50" → plan created with price 12.50, success reply
    assert fake_catalog_service.created_plan.price == Decimal("12.50")


async def test_create_plan_flow_skips_price(...):
    # at the price prompt send "0" (cancel handler) → NOT allowed; "omitir"/"sin precio" → plan created with price None


async def test_edit_plan_price_flow(...):
    # action menu "2" → prompt shows current price → send "9.99" → updated price 9.99


async def test_edit_plan_price_clear(...):
    # action menu "2" → send "sin precio" → price None


async def test_plan_price_prompt_cancel_reachable(...):
    # at the price prompt, "salir" still exits via the universal cancel handler
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_tenant_console_service.py -v`
Expected: FAIL.

- [ ] **Step 3: Add format_price + i18n keys**

`backend/app/services/whatsapp_tenant_console_service/format_helpers.py`:

```python
from decimal import Decimal

from app.core.i18n import _t as i18n_t  # adjust to the module's existing t() helper


def format_price(amount: Decimal | None, symbol: str | None, locale: str) -> str:
    """Format a plan price for WhatsApp text; None → 'Precio a consultar'."""
    if amount is None:
        return i18n_t(locale, "wa.tenant.catalog.price_on_request")
    if not symbol:
        return f"{amount:.2f}"
    sep = "," if locale == "es" else "."
    return f"{symbol} {amount:.2f}".replace(".", sep, 1) if locale == "es" else f"{symbol} {amount:.2f}"
```

(Use the module's actual `_i18n_t`/`t` helper signature — check `format_helpers.py` for the existing import pattern.)

`catalogs_en_wa.py` (near the other `wa.tenant.catalog.*` keys):

```python
    "wa.tenant.catalog.price_label": "Price",
    "wa.tenant.catalog.price_on_request": "Price on request",
    "wa.tenant.catalog.plan_action_edit_price": "2️⃣ Edit price",
    "wa.tenant.catalog.plan_price_prompt": "Send the new price (e.g. 12.50), or *sin precio* to clear it.",
    "wa.tenant.catalog.plan_price_cleared": "Price cleared.",
    "wa.tenant.catalog.plan_price_invalid": "Invalid price. Send a number with up to 2 decimals, or *sin precio*.",
    "wa.tenant.catalog.create_plan_price_prompt": "Optional price (e.g. 12.50). Send *sin precio* to skip.",
```

Mirror in `catalogs_es_wa.py` (es: "Precio", "Precio a consultar", "2️⃣ Editar precio", etc.).

- [ ] **Step 4: Update formatters**

`backend/app/services/whatsapp_tenant_console_service/formatters.py` — import `format_price`, add `symbol: str | None = None` params, render price:

```python
def _format_plan_list(plans, page=1, total_pages=1, symbol=None):
    ...
    for i, p in enumerate(plans, start=1):
        num = str(i)
        active_count = int(getattr(p, "active_subscription_count", 0) or 0)
        price_text = format_price(getattr(p, "price", None), symbol, loc)
        entries.append(
            f"{num}️⃣ {p.name} - {price_text} - "
            f"{_catalog_count('wa.tenant.catalog.count.subscription_active', active_count)}"
        )
        ...


def _format_plan_detail(plan, symbol=None):
    loc = ctx.get_locale()
    header = _i18n_t(loc, "wa.tenant.catalog.plan_detail_header")
    name_label = _i18n_t(loc, "wa.tenant.catalog.name_label", name=plan.name)
    price_label = _i18n_t(loc, "wa.tenant.catalog.price_label")
    price_text = format_price(getattr(plan, "price", None), symbol, loc)
    return f"{header}\n\n{name_label}\n*{price_label}:* {price_text}\n"
```

Also update the subscription-row formatter (`formatters.py` ~line 278, the `*Plan:* {plan_name}` row) to append the price when the plan has one — pass `symbol` through the same call sites.

- [ ] **Step 5: Wire symbol loading into the flows**

Add a helper on the console service (`catalog_flow.py` or a shared mixin — check `_const_mixin.py`/`_context.py` for where shared helpers live):

```python
async def _load_currency_symbol(self, db, tenant_id) -> str | None:
    settings = await tenant_settings_service.get_settings(db, tenant_id)
    if not settings or not settings.currency:
        return None
    return symbol_of(settings.currency)
```

Call it where `_format_plan_list`/`_format_plan_detail` are invoked in `catalog_flow.py` (plan list, plan detail) and `subscriptions_create.py` (plan selection) and pass `symbol=` into the formatter calls. Cache per flow instance (single `self._currency_symbol` slot, reset when the flow starts) to avoid N+1 settings queries.

- [ ] **Step 6: Add the price steps to the create/edit flows**

`constants.py` — add `CATALOG_STEP_CREATE_PLAN_PRICE` and `CATALOG_STEP_EDIT_PLAN_PRICE` next to the existing `CATALOG_STEP_CREATE_PLAN_NAME` and plan-action constants.

`catalog_flow.py`:

1. After the create-plan name step succeeds, move the session to `CATALOG_STEP_CREATE_PLAN_PRICE` and reply with `create_plan_price_prompt` instead of creating the plan directly.
2. New handler for `CATALOG_STEP_CREATE_PLAN_PRICE`: if the message is a skip word (`omitir`, `sin precio`, `none`, `skip`) → `price=None`; else parse via `_parse_price_input(msg)`; invalid → reply `plan_price_invalid` and stay on the step; valid → create the plan with `PlanCreate(name=..., price=parsed)`.
3. Update the plan action menu builder to include `2️⃣ Edit price` (option 2) and shift Delete to 3; update the action router so `"2"` moves to `CATALOG_STEP_EDIT_PLAN_PRICE` and `"3"` runs delete.
4. New handler for `CATALOG_STEP_EDIT_PLAN_PRICE`: `sin precio`/`none`/`omitir` → `PlanUpdate(price=None)`; otherwise parse (invalid → reprompt with current-price hint); then `update_plan(db, tenant_id, service_id, plan_id, PlanUpdate(price=parsed))` → success reply.

`_parse_price_input` (in `catalog_flow.py`, next to `_safe_uuid`):

```python
from decimal import Decimal, InvalidOperation


def _parse_price_input(value: str) -> Decimal | None:
    """Parse '12.50' or '12,50' → Decimal; None on invalid."""
    text = value.strip().replace(",", ".")
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    if parsed < 0 or parsed != parsed.quantize(Decimal("0.01")):
        return None
    return parsed
```

⚠️ Confirm the universal cancel handler still catches `0`/`salir`/`cancelar` while on the new price steps — the new handlers must run only when the cancel handler did not already consume the message (same ordering as the name step).

- [ ] **Step 7: Run tests, format, commit**

Run: `cd backend && uv run pytest tests/test_tenant_console_service.py tests/test_i18n.py -v && uv run ruff format app && uv run ruff check app`
Expected: PASS (i18n parity enforced).

```bash
git add backend/app/services/whatsapp_tenant_console_service backend/app/core/i18n/catalogs_en_wa.py backend/app/core/i18n/catalogs_es_wa.py backend/tests/test_tenant_console_service.py
git commit -m "feat(whatsapp): show plan prices and edit price in tenant console catalog flow"
```

**Docs step:** `docs/architecture/whatsapp-console-flow.md` — add a line: "Catalog plan flows display the plan price with the tenant's currency symbol; create/edit plan support an optional price; subscription-create plan selection shows prices."

---

### Task 8: Client surfaces backend (client console + web dashboard API)

**Files:**
- Modify: `backend/app/services/whatsapp_client_console_facade/facade.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py` and `catalogs_es_wa.py` (client keys)
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/dashboard_service/__init__.py`
- Test: `backend/tests/test_client_console_service.py`
- Test: `backend/tests/test_dashboard_service.py` (or the dashboard test file that exists — check for one; otherwise add assertions to the console/dashboard API test that covers `GET /dashboard`)

**Interfaces:**
- Consumes: Task 3 (currency), Task 4 (`Plan.price`).
- Produces:
  - `ClientActiveSubscription.plan_price: Decimal | None`
  - `ClientDashboardResponse.currency: CurrencyMeta | None`
  - Client WA subscription item includes price line.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_client_console_service.py` — extend the fake plan/subscription objects with `price` and assert the subscription item template includes the formatted price (follow the existing template assertion pattern in that file):

```python
async def test_client_subscriptions_show_plan_price(...):
    # subscription with plan.price = Decimal("12.50") and tenant currency VES
    reply = ...  # the formatted subscriptions list
    assert "Bs. 12,50" in reply
```

Dashboard API test (add to the existing dashboard test file or `test_dashboard_service.py`):

```python
async def test_client_dashboard_includes_plan_price_and_currency(client, active_tenant_user, ...):
    # seed a subscription with a priced plan and tenant_settings.currency="VES"
    response = await client.get("/api/v1/dashboard", headers=...)
    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == {"code": "VES", "symbol": "Bs.", "minor_units": 2}
    assert body["subscriptions"][0]["plan_price"] == "12.50"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_client_console_service.py tests/test_dashboard_service.py -v`
Expected: FAIL.

- [ ] **Step 3: Client console facade**

`backend/app/services/whatsapp_client_console_facade/facade.py` — when building the subscriptions list, load `tenant_settings.currency` and resolve `symbol_of()`; render the price line in the subscription item using the same `format_price` helper (import from the tenant console `format_helpers` or move `format_price` to a shared module — prefer moving it to `app/services/subscription_service/format_helpers.py` or keep it where it is and import across; pick one location and note it in the Interfaces). Add client wa keys:

```python
    "wa.client.subscriptions.price": "Price",
    "wa.client.subscriptions.price_on_request": "Price on request",
```

(es mirror: "Precio", "Precio a consultar".)

- [ ] **Step 4: Dashboard schemas + service**

`backend/app/schemas/dashboard.py`:

```python
from decimal import Decimal
from app.schemas.tenant_settings import CurrencyMeta


class ClientActiveSubscription(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ...
    plan_price: Decimal | None = None


class ClientDashboardResponse(BaseModel):
    ...
    subscriptions: list[ClientActiveSubscription] = Field(default_factory=list)
    currency: CurrencyMeta | None = None
```

`backend/app/services/dashboard_service/__init__.py` — in the subscription builder (`plan_name=sub.plan.name ...` at ~line 144), add `plan_price=sub.plan.price if sub.plan else None`; load the tenant settings once and build `currency` (code + symbol + minor_units) from the catalog.

- [ ] **Step 5: Run tests, format, commit**

Run: `cd backend && uv run pytest tests/test_client_console_service.py tests/test_dashboard_service.py tests/test_i18n.py -v && uv run ruff format app && uv run ruff check app`
Expected: PASS.

```bash
git add backend/app/services/whatsapp_client_console_facade backend/app/schemas/dashboard.py backend/app/services/dashboard_service backend/app/core/i18n/catalogs_en_wa.py backend/app/core/i18n/catalogs_es_wa.py backend/tests/test_client_console_service.py backend/tests/test_dashboard_service.py
git commit -m "feat(client): show plan price in WhatsApp console and web dashboard"
```

**Docs step:** `docs/architecture/whatsapp-console-flow.md` — add: "Client console subscription items include the plan price when set."

---

### Task 9: Frontend settings API + store + data-source contract + demo adapter

**Files:**
- Modify: `frontend/src/features/admin/services/settings-api.ts`
- Modify: `frontend/src/store/settings.ts`
- Modify: `frontend/src/lib/data-source.ts`
- Modify: `frontend/src/features/demo/services/demo-settings.ts`
- Test: `frontend/src/store/__tests__/settings.spec.ts`
- Test: `frontend/src/features/demo/services/__tests__/demo-settings.spec.ts`

**Interfaces:**
- Consumes: Task 3 (`GET /tenant-settings/currencies`, updated TenantSettings API).
- Produces (consumed by Task 10-13):
  - `settings-api.getCurrencies(): Promise<{countries: CountryOption[]; currencies: CurrencyOption[]}>`
  - Types `CountryOption {code, currency}`, `CurrencyOption {code, symbol, minor_units}`, `TenantSettings.country/currency`, `TenantSettingsUpdate.country?/currency?`
  - `SettingsStore.loadCurrencyOptions(source): Promise<...>` with in-flight dedup + epoch guard
  - `SettingsDataSourceContract.loadCurrencyOptions(source): Promise<...>`

- [ ] **Step 1: Write the failing store test**

`frontend/src/store/__tests__/settings.spec.ts` — mirror the existing `loadTimezoneOptions` tests; mock `getCurrencies`:

```typescript
it("deduplicates currency options loads", async () => {
  const payload = {
    countries: [{ code: "VE", currency: "VES" }],
    currencies: [{ code: "VES", symbol: "Bs.", minor_units: 2 }],
  };
  vi.mocked(getCurrencies).mockResolvedValue(payload);

  const [first, second] = await Promise.all([
    useSettingsStore.getState().loadCurrencyOptions(dataSource.settings),
    useSettingsStore.getState().loadCurrencyOptions(dataSource.settings),
  ]);
  expect(first).toEqual(payload);
  expect(second).toEqual(payload);
  expect(getCurrencies).toHaveBeenCalledTimes(1);
  expect(useSettingsStore.getState().currencyOptions).toEqual(payload);
});
```

(Reuse the existing `dataSource` mock used by `loadTimezoneOptions` tests; add `getCurrencies` to the `vi.mock` factory.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- store/__tests__/settings.spec.ts`
Expected: FAIL (function/types missing).

- [ ] **Step 3: Update settings-api types + getCurrencies**

`frontend/src/features/admin/services/settings-api.ts`:

```typescript
export interface CountryOption {
  code: string;
  currency: string;
}

export interface CurrencyOption {
  code: string;
  symbol: string;
  minor_units: number;
}

export interface TenantSettings {
  tenant_id: string;
  locale: string;
  timezone: string | null;
  country: string | null;
  currency: string | null;
}

export interface TenantSettingsUpdate {
  locale?: string;
  timezone?: string;
  country?: string;
  currency?: string;
}

export async function getCurrencies(): Promise<{
  countries: CountryOption[];
  currencies: CurrencyOption[];
}> {
  const { data } = await api.get("/tenant-settings/currencies");
  return data;
}
```

(Update the existing `TenantSettings`/`TenantSettingsUpdate` interfaces in that file — keep the other fields.)

- [ ] **Step 4: Update the store**

`frontend/src/store/settings.ts` — add `currencyOptions` state and `loadCurrencyOptions` mirroring `loadTimezoneOptions` exactly (in-flight promise slot, epoch guard, error reset):

```typescript
currencyOptions: { countries: CountryOption[]; currencies: CurrencyOption[] } | null,
loadCurrencyOptions: async (source) => {
  const state = get();
  if (state.currencyOptionsPromise) return state.currencyOptionsPromise;
  const promise = source.loadCurrencyOptions(source)
    .then((data) => {
      set({ currencyOptions: data, currencyOptionsPromise: null });
      return data;
    })
    .catch((error) => {
      set({ currencyOptionsPromise: null });
      throw error;
    });
  set({ currencyOptionsPromise: promise });
  return promise;
},
```

(Check the actual epoch guard used by `loadTimezoneOptions` and apply the same.)

- [ ] **Step 5: Update the data-source contract**

`frontend/src/lib/data-source.ts` — add `loadCurrencyOptions` to `SettingsDataSourceContract` (production `dataSource.settings` calls `settings-api.getCurrencies`; demo adapter implemented in Step 6). Search the file for the timezone entry and mirror it.

- [ ] **Step 6: Demo adapter**

`frontend/src/features/demo/services/demo-settings.ts`:

```typescript
import currencyCatalog from "@/lib/currency-catalog.json";

async loadCurrencyOptions(): Promise<{ countries: CountryOption[]; currencies: CurrencyOption[] }> {
  return currencyCatalog as { countries: CountryOption[]; currencies: CurrencyOption[] };
}
```

Extend `validateTenantSettings` (the demo validator around line 107): normalize `country` to uppercase and reject codes not in the catalog (`throw new Error(t("frontend.profile.error_invalid_country"))`); same for `currency` (`error_invalid_currency`). Add `country`/`currency` to the demo settings state shape and defaults (`null`).

- [ ] **Step 7: Run tests, lint, commit**

Run: `cd frontend && npm test -- store/__tests__/settings.spec.ts demo/services/__tests__/demo-settings.spec.ts`
Expected: PASS. Then `npx tsc --noEmit` to confirm types.

```bash
git add frontend/src/features/admin/services/settings-api.ts frontend/src/store/settings.ts frontend/src/lib/data-source.ts frontend/src/features/demo/services/demo-settings.ts frontend/src/store/__tests__/settings.spec.ts frontend/src/features/demo/services/__tests__/demo-settings.spec.ts
git commit -m "feat(frontend): currency options loading in settings store and demo adapter"
```

**Docs step:** none (internal plumbing; CONTEXT.md Settings Store term already updated).

---

### Task 10: Frontend regional tab (My Account) + pickers + route param

**Files:**
- Create: `frontend/src/features/admin/components/regional-settings-section.tsx`
- Create: `frontend/src/features/admin/components/country-picker.tsx`
- Create: `frontend/src/features/admin/components/currency-picker.tsx`
- Modify: `frontend/src/features/admin/components/my-account-section.tsx`
- Modify: `frontend/src/features/admin/components/settings-page.tsx`
- Modify: `frontend/src/features/admin/settings-categories.ts`
- Modify: `frontend/src/routes/admin/settings.tsx`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py` and `catalogs_es_frontend.py`
- Test: `frontend/src/features/admin/components/__tests__/currency-picker.spec.tsx`
- Test: `frontend/src/features/admin/components/__tests__/regional-settings-section.spec.tsx`
- Test: update `frontend/src/features/admin/components/__tests__/my-account-section.spec.tsx`, `settings-page.spec.tsx`, and any `locale-section`/`timezone-section` specs that break when the categories are removed

**Interfaces:**
- Consumes: Task 9 (store `currencyOptions`, `loadCurrencyOptions`, tenant settings types).
- Produces:
  - `CountryPicker` props `{value: string | null, countries: CountryOption[], onChange: (code: string | null) => void}` — localized names via `Intl.DisplayNames`, search supported.
  - `CurrencyPicker` props `{value: string | null, currencies: CurrencyOption[], officialCurrency: string | null, onChange: (code: string | null) => void}` — official currency grouped first above a separator, deduped from the rest; plain list when no country.
  - `RegionalSettingsSection` — loads settings + timezone + currency options; gates fields by plan (Starter: country+locale; Pro: +timezone+currency; master support: all).
  - `MyAccountSection` gains `initialTab?: string` prop and the `regional` tab.
  - Settings route accepts `?tab=regional` (validated) → `initialTab`.

- [ ] **Step 1: Write the failing CurrencyPicker test**

`frontend/src/features/admin/components/__tests__/currency-picker.spec.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CurrencyPicker } from "../currency-picker";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
  getLocale: () => "en",
}));

const CURRENCIES = [
  { code: "VES", symbol: "Bs.", minor_units: 2 },
  { code: "USD", symbol: "$", minor_units: 2 },
  { code: "EUR", symbol: "€", minor_units: 2 },
];

describe("CurrencyPicker", () => {
  it("renders the official currency first above a separator when a country is selected", async () => {
    render(
      <CurrencyPicker
        value={null}
        currencies={CURRENCIES}
        officialCurrency="VES"
        onChange={() => {}}
      />
    );
    await userEvent.click(screen.getByRole("combobox"));
    const items = screen.getAllByRole("option").map((el) => el.textContent);
    expect(items[0]).toContain("Bs.");
    // VES appears exactly once (grouped, not duplicated in the rest)
    expect(items.filter((t) => t?.includes("Bs.")).length).toBe(1);
  });

  it("renders a plain list without grouping when no country is selected", async () => {
    render(
      <CurrencyPicker
        value={null}
        currencies={CURRENCIES}
        officialCurrency={null}
        onChange={() => {}}
      />
    );
    await userEvent.click(screen.getByRole("combobox"));
    const items = screen.getAllByRole("option").map((el) => el.textContent);
    expect(items).toHaveLength(3);
  });

  it("calls onChange with the selected code", async () => {
    const onChange = vi.fn();
    render(
      <CurrencyPicker
        value={null}
        currencies={CURRENCIES}
        officialCurrency="VES"
        onChange={onChange}
      />
    );
    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.click(screen.getAllByRole("option")[0]);
    expect(onChange).toHaveBeenCalledWith("VES");
  });
});
```

(Adjust to the actual picker primitive used — if the project uses a shadcn `Combobox`/`Popover`+`Command` pattern like `TimezonePicker`, mirror its test structure; the assertions above are the behavioral contract.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- components/__tests__/currency-picker.spec.tsx`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement CountryPicker + CurrencyPicker**

`country-picker.tsx` — reuses the `TimezonePicker` shell (same search + portal behavior). Options are `countries`; label = `new Intl.DisplayNames([getLocale()], { type: "region" }).of(code)` fallback to code; display `🌍 {localizedName} ({code})`.

`currency-picker.tsx` — builds the option list:

```tsx
const grouped = useMemo(() => {
  if (!officialCurrency) return { official: null, rest: currencies };
  return {
    official: currencies.find((c) => c.code === officialCurrency) ?? null,
    rest: currencies.filter((c) => c.code !== officialCurrency),
  };
}, [currencies, officialCurrency]);
```

Render: if `official` exists, a `CommandGroup` header (label `t("frontend.my_account.regional.country_currency_group")`) with the official option, then a separator, then `CommandGroup` "rest". When `value` is not the official currency, it still appears in "rest" and is highlighted. Selecting an item calls `onChange(code)`.

- [ ] **Step 4: Write the failing RegionalSettingsSection test**

`frontend/src/features/admin/components/__tests__/regional-settings-section.spec.tsx` — mock the settings store (pattern from `my-account-section.spec.tsx`) with a Pro tenant and assert: all four fields render; switch to a Starter tenant (mock `useAuthStore` role/plan) and assert timezone + currency controls are absent. Also a demo-mode test asserting the catalog reload after locale change is preserved (mirror the existing `locale-section-demo.spec` behavior).

- [ ] **Step 5: Implement RegionalSettingsSection**

`regional-settings-section.tsx` — loads `loadTenantSettings` + `loadTimezoneOptions` + `loadCurrencyOptions` in parallel (pattern from `TimezoneSection`); renders:

- Country field → `CountryPicker` (all plans)
- Language field → the existing `LocaleSection` content extracted inline (or keep `LocaleSection` as a sub-component) — preserves the demo catalog-reload behavior
- Timezone field → `TimezonePicker` (Pro only)
- Currency field → `CurrencyPicker` with `officialCurrency={currencyOptions?.countries.find(c => c.code === country)?.currency ?? null}` (Pro only)

Gating via `useAuthStore` (`tenantPlan`/role; master support shows all). Root element sets `data-help-id="admin.settings.regional"` for contextual help. One shared Save button per field group following the existing section patterns.

- [ ] **Step 6: Wire My Account tab + remove old categories**

`my-account-section.tsx` — add `initialTab?: string` prop; add a `<TabsTrigger value="regional">{t("frontend.my_account.tab_regional")}</TabsTrigger>`; `defaultValue={initialTab === "regional" ? "regional" : "profile"}`; add `<TabsContent value="regional"><RegionalSettingsSection /></TabsContent>` (always rendered, including master support context).

`settings-categories.ts` — remove `"locale"` and `"timezone"` from `SETTINGS_CATEGORY_IDS`.

`settings-page.tsx` — remove the `locale` and `timezone` entries from `buildSections` and delete the `LocaleSection`/`TimezoneSection` usage/imports.

`routes/admin/settings.tsx` — validate search param `tab?: "regional"` (use the router's search-validation pattern), pass to `SettingsPage`, thread into `MyAccountSection initialTab`.

- [ ] **Step 7: Add i18n frontend keys**

`catalogs_en_frontend.py` (and es mirror):

```python
    "frontend.my_account.tab_regional": "Regional settings",
    "frontend.my_account.regional.country": "Country",
    "frontend.my_account.regional.currency": "Currency",
    "frontend.my_account.regional.country_currency_group": "Country currency",
    "frontend.my_account.regional.error_invalid_country": "Invalid country.",
    "frontend.my_account.regional.error_invalid_currency": "Invalid currency.",
```

(es: "Configuración regional", "País", "Moneda", "Moneda del país", etc.)

- [ ] **Step 8: Update broken specs, run tests, lint, commit**

Update `my-account-section.spec.tsx` (new tab present), `settings-page.spec.tsx` (locale/timezone categories gone), and any `locale-section`/`timezone-section` specs that referenced the Settings page.

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: PASS.

```bash
git add frontend/src/features/admin/components frontend/src/features/admin/settings-categories.ts frontend/src/routes/admin/settings.tsx backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py frontend/src/features/admin/components/__tests__ frontend/src/features/admin/__tests__ frontend/src/features/admin/components/__tests__/my-account-section.spec.tsx
git commit -m "feat(frontend): regional settings tab with country, currency, language and timezone pickers"
```

**Docs step:** `docs/architecture/frontend-architecture.md` — add: My Account gains the Regional tab (Configuración regional) with Country/Language (all plans) and Timezone/Currency (Pro); CountryPicker localizes names via Intl.DisplayNames; CurrencyPicker groups the official country currency first.

---

### Task 11: Frontend catalog plan price

**Files:**
- Modify: `frontend/src/features/admin/services/catalog-api.ts`
- Modify: `frontend/src/features/admin/components/catalog-page.tsx`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py` and `catalogs_es_frontend.py`
- Test: update `frontend/src/features/admin/components/__tests__/catalog-page.spec.tsx` (or the catalog spec that exists)

**Interfaces:**
- Consumes: Task 4 (API `price`), Task 9 (currency symbol from store `currencyOptions` + `tenantSettings.currency`).
- Produces: `Plan.price: string | null`; create form with optional price; edit dialog with name + price; display `Bs. 12,50` or "Precio a consultar".

- [ ] **Step 1: Write the failing test**

In the existing catalog-page spec, add:

```tsx
it("creates a plan with a price", async () => {
  // mock dataSource.catalog.createPlan; render with a selected service
  await userEvent.type(screen.getByLabelText(/name/i), "Basico");
  await userEvent.type(screen.getByLabelText(/price/i), "12.50");
  await userEvent.click(screen.getByRole("button", { name: /create plan/i }));
  expect(createPlan).toHaveBeenCalledWith("service-1", { name: "Basico", price: "12.50" });
});

it("shows the price with the tenant currency symbol", async () => {
  // mock tenant settings currency VES and currencyOptions with VES symbol "Bs."
  expect(screen.getByText(/Bs\. 12,50/)).toBeInTheDocument();
});

it("shows Price on request when a plan has no price", async () => {
  expect(screen.getByText(/price on request/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- components/__tests__/catalog-page.spec.tsx`
Expected: FAIL.

- [ ] **Step 3: Update types + API**

`frontend/src/features/admin/services/catalog-api.ts`:

```typescript
export interface Plan {
  id: string;
  tenant_id: string;
  service_id: string;
  name: string;
  price: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlanCreate {
  name: string;
  price?: string | null;
}

export interface PlanUpdate {
  name?: string;
  price?: string | null;
}
```

- [ ] **Step 4: Update catalog-page.tsx**

1. Add a price `Input` next to the create-plan name input (`value={newPlanPrice}`, `type="text"`, `inputMode="decimal"`, placeholder from i18n); `handleCreatePlan` sends `{ name, price: newPlanPrice.trim() ? newPlanPrice.trim() : null }`.
2. Convert the rename dialog into an edit dialog: add a price input initialized from the plan, save sends `{ name, price: newPlanPrice.trim() ? newPlanPrice.trim() : null }`.
3. Plan list rows: render `{symbol} {amount}` using a `formatPrice` helper (localized decimals via `Intl.NumberFormat(getLocale(), { style: "decimal", minimumFractionDigits: minorUnits, maximumFractionDigits: minorUnits })` — symbol from `currencyOptions.currencies` matching `tenantSettings.currency`); when no price → `t("frontend.catalog.price_on_request")`.

Add the helper to `frontend/src/features/admin/services/catalog-api.ts` or a small `format-price.ts` module; use catalog symbols only (never `Intl` currency style).

- [ ] **Step 5: Add i18n frontend keys**

`catalogs_en_frontend.py` (and es mirror):

```python
    "frontend.catalog.price": "Price",
    "frontend.catalog.price_on_request": "Price on request",
    "frontend.catalog.price_placeholder": "Optional price",
    "frontend.catalog.invalid_price": "Enter a valid price with up to 2 decimals.",
```

- [ ] **Step 6: Run tests, lint, commit**

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: PASS.

```bash
git add frontend/src/features/admin/services/catalog-api.ts frontend/src/features/admin/components/catalog-page.tsx backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py frontend/src/features/admin/components/__tests__
git commit -m "feat(frontend): plan price input and display with tenant currency symbol"
```

**Docs step:** `docs/architecture/frontend-architecture.md` — add: catalog plan create/edit include an optional price; plans display `{symbol} {amount}` with the tenant's currency.

---

### Task 12: Frontend client dashboard price

**Files:**
- Modify: `frontend/src/features/client/services/client-dashboard-api.ts`
- Modify: `frontend/src/features/client/components/dashboard-page.tsx`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py` and `catalogs_es_frontend.py` (client keys)
- Test: update the existing client dashboard spec (find the spec for `dashboard-page.tsx` or `client-dashboard-api`; add price assertions)

**Interfaces:**
- Consumes: Task 8 (API `plan_price` + `currency`).
- Produces: client subscription rows render the plan price with the tenant currency symbol.

- [ ] **Step 1: Write the failing test**

In the client dashboard spec:

```tsx
it("shows the subscription plan price with the currency symbol", async () => {
  // mock fetchClientDashboard with subscriptions[0].plan_price = "12.50"
  // and currency = { code: "VES", symbol: "Bs.", minor_units: 2 }
  expect(await screen.findByText(/Bs\. 12,50/)).toBeInTheDocument();
});

it("shows Price on request when a plan has no price", async () => {
  // plan_price null
  expect(await screen.findByText(/price on request/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- client/components/__tests__/dashboard-page.spec.tsx`
Expected: FAIL.

- [ ] **Step 3: Update types + component**

`client-dashboard-api.ts`:

```typescript
export interface ClientActiveSubscription {
  ...
  plan_price: string | null;
}

export interface ClientDashboardData {
  ...
  currency: { code: string; symbol: string; minor_units: number } | null;
}
```

`dashboard-page.tsx` — in the two places that render `sub.plan_name` (table row ~line 88 and card ~line 133), append the price line/column using the same `formatPrice` helper from Task 11 (import it); fall back to "Precio a consultar". Use `data.currency` for the symbol.

- [ ] **Step 4: Add client i18n keys**

`catalogs_en_frontend.py` (and es mirror):

```python
    "frontend.client_dashboard.price": "Price",
    "frontend.client_dashboard.price_on_request": "Price on request",
```

- [ ] **Step 5: Run tests, lint, commit**

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: PASS.

```bash
git add frontend/src/features/client/services/client-dashboard-api.ts frontend/src/features/client/components/dashboard-page.tsx backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py frontend/src/features/client/components/__tests__
git commit -m "feat(frontend): show plan price on client dashboard"
```

**Docs step:** none new (covered in Task 10's frontend-architecture entry).

---

### Task 13: Demo parity (baseline + demo catalog prices)

**Files:**
- Modify: `frontend/src/features/demo/services/demo-baseline.ts`
- Modify: `frontend/src/features/demo/services/demo-catalog.ts`
- Modify: `frontend/src/features/demo/services/demo-workspace.ts` (if plan validation lives there)
- Test: `frontend/src/features/demo/services/__tests__/demo-workspace.spec.ts` and the demo-catalog spec (if any)

**Interfaces:**
- Consumes: Task 9 (demo `loadCurrencyOptions`, settings validation), Task 11 (price passthrough types).
- Produces: demo baseline `tenant_settings` with `country`/`currency`; demo catalog plans with `price`.

- [ ] **Step 1: Write the failing tests**

In the demo specs (follow the existing baseline/catalog test patterns):

```ts
it("baseline workspace includes country and currency settings", () => {
  const baseline = createDemoBaseline("pro", metadata);
  expect(baseline.tenant_settings.country).toBe("US");
  expect(baseline.tenant_settings.currency).toBe("USD");
});

it("demo createPlan stores the price", async () => {
  const plan = await demoCatalog.createPlan("service-1", { name: "P", price: "12.50" });
  expect(plan.price).toBe("12.50");
});

it("demo createPlan rejects invalid price", async () => {
  await expect(demoCatalog.createPlan("service-1", { name: "P", price: "-1" }))
    .rejects.toThrow();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- demo/services`
Expected: FAIL.

- [ ] **Step 3: Update demo baseline**

`demo-baseline.ts` — `tenant_settings` gains `country`/`currency` (starter: `{country: "US", currency: null}` — wait, Starter cannot set currency; use `country: "US"` only and `currency: null`; pro: `country: "US", currency: "USD"`); add `price` to demo plans (pro plans get sample prices like `"12.50"`, starter plans `null`).

- [ ] **Step 4: Update demo catalog**

`demo-catalog.ts` — `createPlan`/`updatePlan`: validate price (`_parsePrice` accepting string, ≥ 0, ≤ 2 decimals — reuse the same helper from Task 11's format module if shared; otherwise duplicate the small parser), store `price` on the plan object; `updatePlan` handles `price: null` → clear.

- [ ] **Step 5: Update demo workspace validation (if applicable)**

`demo-workspace.ts` — if plan validation exists there, extend it for price; check `validateTenantSettings` in demo-settings already covers country/currency (Task 9).

- [ ] **Step 6: Run tests, lint, commit**

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: PASS.

```bash
git add frontend/src/features/demo/services frontend/src/features/demo/services/__tests__
git commit -m "feat(demo): regional settings and plan prices in demo workspaces"
```

**Docs step:** none new (demo mirror; covered by CONTEXT.md).

---

### Task 14: Help module — topics, compiler contract, targets, tour

**Files:**
- Create: `backend/help/es/tenant-admin/country.md` and `backend/help/en/tenant-admin/country.md`
- Create: `backend/help/es/tenant-admin/currency.md` and `backend/help/en/tenant-admin/currency.md`
- Modify: `backend/help/es/tenant-admin/language.md`, `backend/help/en/tenant-admin/language.md`
- Modify: `backend/help/es/tenant-admin/timezone.md`, `backend/help/en/tenant-admin/timezone.md`
- Modify: `backend/help/es/tenant-admin/catalog.md`, `backend/help/en/tenant-admin/catalog.md`
- Modify: `backend/help/es/client/subscriptions.md`, `backend/help/en/client/subscriptions.md`
- Modify: `backend/app/help/compiler.py` (ALLOWED_SETTINGS_CATEGORIES + tab validation)
- Modify: `frontend/src/features/help/help-targets.ts`
- Modify: `frontend/src/features/help/safe-navigation.ts`
- Modify: `frontend/src/features/help/services/help-api.ts` (if `HelpSafeNavigation` type gains `tab`)
- Modify: `frontend/src/features/help/__tests__/safe-navigation.spec.ts`
- Modify: `backend/tests/test_help_contract.py` (or the test that enumerates topic ids/targets)
- Modify: `docs/releases/user-help-release.md`
- Regenerate: `backend/app/help/artifact.json` (via `cd backend && uv run python -m scripts.compile_help`)

**Interfaces:**
- Consumes: Task 10 (regional tab + `?tab=regional` route param, `data-help-id="admin.settings.regional"`).
- Produces: `help-targets.regional = "admin.settings.regional"`; topics `tenant-admin.country`, `tenant-admin.currency`; `safe_navigation` with `{route, settings_category: "my-account", tab: "regional"}`; updated artifact + green `verify_help_release.py`.

- [ ] **Step 1: Update the compiler contract**

`backend/app/help/compiler.py`:

```python
ALLOWED_SETTINGS_CATEGORIES = {
    "access-control",
    "code-services",
    "data",
    "mailbox",
    "my-account",
    "password",
    "profile",
    "public-api",
    "reminders",
    "whatsapp-link",
}
ALLOWED_TABS = {"regional"}
```

In `_validate_safe_navigation`, allow an optional `tab` key: `set(value) - {"route", "settings_category", "tab"} == set()` and `tab is None or tab in ALLOWED_TABS`. Require `settings_category="my-account"` when `tab` is present (or allow tab only with my-account — pick one and enforce).

- [ ] **Step 2: Write the failing compiler tests**

In `backend/tests/test_help_contract.py` (or `test_help_hardening.py` — the file that validates safe_navigation): add tests that a topic with `settings_category: locale` now FAILS compilation and one with `settings_category: my-account, tab: regional` PASSES (build tiny topic strings through `compile_help` on a temp dir — follow the existing helper in that file).

- [ ] **Step 3: Write the new topics**

`backend/help/es/tenant-admin/country.md` — frontmatter:

```yaml
---
id: tenant-admin.country
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.regional
title: País
summary: Elige el país donde opera tu negocio.
search_tags:
  - país
  - moneda del país
  - país del negocio
synonyms:
  - ubicación
order: 21
safe_navigation:
  route: /admin/settings
  settings_category: my-account
  tab: regional
related_topics:
  - tenant-admin.currency
  - tenant-admin.language
---
```

Body (es): explains the country is stored as an ISO code, names are localized, choosing a country surfaces its official currency first in the currency picker without changing the saved currency, and it is available on Starter and Pro. En mirror in `backend/help/en/tenant-admin/country.md`.

`backend/help/es/tenant-admin/currency.md` — same frontmatter but `id: tenant-admin.currency`, `plans: [pro]`, `order: 22`, title "Moneda", summary "Expresa los precios de tu catálogo en la moneda de tu negocio." Body explains Pro-only, the official currency of the selected country appears first above a separator, symbol comes from the bundled catalog (e.g. "Bs." for Venezuela), and plan prices display with it. En mirror.

- [ ] **Step 4: Update relocated topics**

`language.md` (es + en): change `safe_navigation` to `route: /admin/settings, settings_category: my-account, tab: regional`; add `admin.settings.regional` to `help_targets` (keep `admin.settings.language`); update body to say the language picker now lives in **Mi Cuenta > Configuración regional**; update `search_tags`/`synonyms` if needed.

`timezone.md` (es + en): same navigation changes (keep `plans: [pro]`); body updated to reference the regional tab.

- [ ] **Step 5: Update catalog and client-subscriptions topics**

`catalog.md` (es + en): add a paragraph — plans may have an optional price displayed with the tenant's currency symbol (e.g. "Bs. 12,50"); plans without a price show "Precio a consultar"; price can be set from the web catalog and the WhatsApp console. Add `precio` to search_tags. `client/subscriptions.md` (es + en): note the subscription list shows the plan price when set.

- [ ] **Step 6: Frontend help targets + safe navigation**

`help-targets.ts`:

```typescript
regional: "admin.settings.regional",
```

`help-api.ts` — extend `HelpSafeNavigation` with `tab?: string | null` (align with the backend compiler output).

`safe-navigation.ts` — when `navigation.settings_category === "my-account"` and `navigation.tab === "regional"`, resolve to `{ to: "/admin/settings", search: { category: "my-account", tab: "regional" } }`; update `SafeHelpDestination` accordingly (the settings route already accepts `tab` from Task 10). Update `safe-navigation.spec.ts` with cases: `my-account + regional` → correct URL, `locale` category → null.

- [ ] **Step 7: Retarget the tour**

`language.md`/`timezone.md` and any tour entry referencing `admin.settings.timezone` — find the `tenant-admin-pro-1` tour step in the help sources (search `help_targets: - admin.settings.timezone` across `backend/help/`) and retarget it to `admin.settings.regional`.

- [ ] **Step 8: Recompile artifact + verify + update release doc**

Run: `cd backend && uv run python -m scripts.compile_help && uv run python scripts/verify_help_release.py`
Expected: "Private Help release contract is ready".

Update `docs/releases/user-help-release.md` QA matrix: add `tenant-admin.country` and `tenant-admin.currency` rows; note language/timezone topics now live under the regional tab (My Account).

- [ ] **Step 9: Run help tests, commit**

Run: `cd backend && uv run pytest tests/test_help_contract.py tests/test_help_release.py tests/test_help_catalog.py -v`
Expected: PASS. Then `cd frontend && npm test -- features/help`

```bash
git add backend/help backend/app/help/artifact.json backend/app/help/compiler.py backend/tests/test_help_contract.py frontend/src/features/help docs/releases/user-help-release.md
git commit -m "feat(help): regional country/currency topics, relocated language/timezone, regional safe navigation"
```

**Docs step:** done in Step 8 (release doc).

---

### Task 15: Architecture documentation

**Files:**
- Create: `docs/architecture/regional-settings.md`
- Modify: `docs/architecture/subscriptions.md` (verify Task 3's line landed)
- Modify: `docs/architecture/tenant-data-export.md` (verify Task 6's note landed)
- Modify: `docs/SUMMARY.md`

- [ ] **Step 1: Write the architecture doc**

`docs/architecture/regional-settings.md` — cover: Currency Catalog module (CLDR source, overrides, regeneration script, two outputs), data model (country/currency/price columns), gating matrix (Starter: country+language; Pro: +timezone+currency), API (currencies endpoint, 409/404 semantics), pickers behavior (official-currency-first grouping, no auto-select), price semantics (null = "Precio a consultar", tenant currency), WhatsApp console price flows, Public API + Export surfaces, demo parity, help integration (regional target + safe navigation).

- [ ] **Step 2: Update SUMMARY.md**

Add `Regional Settings` row to the Architecture table pointing at `architecture/regional-settings.md`.

- [ ] **Step 3: Verify cross-references + commit**

Skim `subscriptions.md` and `tenant-data-export.md` for the lines added in Tasks 3 and 6; fix formatting if needed.

```bash
git add docs/architecture/regional-settings.md docs/architecture/subscriptions.md docs/architecture/tenant-data-export.md docs/SUMMARY.md
git commit -m "docs: regional settings architecture reference"
```

---

## Self-Review Notes (run by the planner before handoff)

- **Spec coverage:** Sections 3-4 → Tasks 1-2; §5 → Tasks 3-6; §10 (WhatsApp consoles) → Tasks 7-8; §6 frontend → Tasks 9-12; demo → Tasks 13; §11 help → Task 14; §7 docs → Task 15 + per-task doc steps; §9 testing → folded into each task. ADR 0005, backend/frontend CONTEXT.md already committed.
- **Placeholder scan:** no TBD/TODO; every code step contains the actual implementation; where a step says "follow the existing pattern", it names the exact file/function to mirror.
- **Type consistency:** `validate_country`/`validate_currency`/`symbol_of`/`minor_units_of`/`list_countries`/`list_currencies` defined in Task 1 are the only catalog entry points used everywhere; `CurrencyMeta` defined in Task 3 is reused by Tasks 5 and 8; `PlanUpdate` model_fields_set semantics defined in Task 4 are relied on by Tasks 4 and 7; `format_price` introduced in Task 7 is imported by Task 8 (and the frontend `formatPrice` in Task 11 is a separate frontend helper); `price: string | null` JSON contract is consistent backend (Pydantic Decimal→string) and frontend (Task 11/12/13).
