# Currency, Country & Plan Pricing — Design

**Status**: Draft (pending user review)
**Date**: 2026-07-31
**Scope**: Backend (FastAPI), Frontend (React), Docs

## 1. Problem

TrackPal tenants need to configure their business country and currency, and catalog plans need an optional price displayed with the tenant's currency symbol. Currency data (countries, official currency per country, symbols, minor units) must be selectable without per-request calls to an external provider.

## 2. Decisions (resolved with user)

| Decision | Choice |
|---|---|
| Currency data source | Bundled static file committed to repo, regenerated ~2×/year from Unicode CLDR (via `babel` dev-time). No daily worker, no external API in runtime. |
| Country ↔ currency coupling | Independent fields. Selecting a country surfaces its official currency first in the currency picker (grouped above a separator), without overwriting a manually chosen currency. |
| Price | Optional single `Decimal` per plan, no per-plan currency. Null = "Precio a consultar". Displayed with the tenant's currency symbol. |
| Plan gate | Country/currency Pro-only (identical to timezone gate). Price only visible where catalog exists (Pro). |
| Demo tenants | Full parity: Demo Workspace gets country/currency pickers and demo catalog plans with sample prices. |
| Price surfaces | Catalog CRUD/display, Public API Catalog (plans expose `price` + `currency`), Tenant Data Export (`service-catalog.csv` adds `plan_price`; `account-profile.csv` adds `currency`). Export schema change is a documented stable-contract change (ADR 0003). |
| Tab name | "País y moneda" / "Country & currency" in Mi Cuenta. |

## 3. Currency Catalog module (backend)

Deep module at `backend/app/core/currency_catalog/`:

- `data.json` — centralized committed file:

```json
{
  "source": "Unicode CLDR <version>",
  "generated_at": "YYYY-MM-DD",
  "countries": [{"code": "VE", "currency": "VES"}],
  "currencies": {"VES": {"symbol": "Bs.", "minor_units": 2}}
}
```

- `currency_catalog.py` — small interface, dense implementation (loads file once, memory cache):

```
list_countries()          → [{"code": "VE", "currency": "VES"}, ...]   # ISO 3166-1 alpha-2 only
list_currencies()         → [{"code": "VES", "symbol": "Bs.", "minor_units": 2}, ...]
official_currency_of(code) → "VES" | None
symbol_of(code)           → "Bs." | None
validate_currency(code)   → bool
validate_country(code)    → bool
```

- No external-provider seam: exactly one real adapter (the bundled file). The timezone catalog's external-provider stub is not copied (`one adapter means a hypothetical seam`).
- `backend/scripts/regenerate_currency_catalog.py` — dev-time only, run via `uv run --with babel`. Uses `babel.core.get_global("territory_currencies")` (territory → current currency), `babel.numbers.get_currency_symbol(code, "en")` (symbol), `babel.core.get_global("currency_fractions")` (minor units). Filters territories to `^[A-Z]{2}$` (excludes 001, EU, …). `babel` is NOT a runtime dependency.

## 4. Data model & migration

New Alembic migration, 3 columns (no RLS changes — tables already tenant-scoped):

| Table | Column | Type | Notes |
|---|---|---|---|
| `tenant_settings` | `country` | VARCHAR(2) nullable | ISO 3166-1 alpha-2; NULL = not chosen |
| `tenant_settings` | `currency` | VARCHAR(3) nullable | ISO 4217; NULL = not chosen (UI shows no symbol) |
| `plans` | `price` | NUMERIC(12,2) nullable | Optional; inherited tenant currency |

Nullable without defaults (unlike `timezone`/`locale` which default): "not configured" is distinct from USD.

## 5. Backend API

- `GET /api/v1/tenant-settings/currencies` → `{countries: [...], currencies: [...]}`. Auth: `require_tenant_or_master` + `DemoGuardedUser` (precedent: `/tenant-settings/timezones`).
- `TenantSettingsResponse` / `TenantSettingsUpdate`: add `country`, `currency`. Validators call `validate_country` / `validate_currency`; invalid → 409.
- Gate identical to timezone: Starter tenant role → fields nulled in GET, non-null rejected (404) in PUT. Master support bypasses.
- `PlanCreate` / `PlanUpdate` / `PlanResponse`: add `price: Decimal | None` (`condecimal(max_digits=12, decimal_places=2)`, min 0). Catalog service passes the field through.
- Public API Catalog: nested plans expose `price` and `currency` (derived from tenant settings).
- Tenant Data Export: `service-catalog.csv` adds `plan_price`; `account-profile.csv` adds `currency`. Documented as a stable-contract change.

## 6. Frontend

- New Mi Cuenta tab `regional` — "País y moneda" / "Country & currency". Hidden for Starter tenant admin (timezone pattern); Master support sees it.
- **CountryPicker**: countries from catalog; localized names via `Intl.DisplayNames` with active locale (ISO codes stored, browser localizes — no duplicated i18n catalogs).
- **CurrencyPicker**: currencies from catalog with symbols. If a country is selected, its official currency renders first in a "Moneda del país" group, then a separator, then all others (reuses `TimezonePicker` `group` option pattern). If no country is selected, the plain full list renders without groups. Changing country never overwrites currency. If currency is set but country is not (or vice versa), each field is displayed independently.
- **Catalog**: optional price input (2 decimals) in `service-form-dialog.tsx`; display `{symbol} {amount}` in `catalog-page.tsx` using tenant settings currency + catalog symbol.
- Settings store: `loadCurrencyOptions` (pattern: `loadTimezoneOptions`).
- i18n: new es/en keys (tab name, labels).
- Demo: adapter-based parity — demo Pro workspace shows functional tab and demo catalog plans with sample prices; Demo Baseline includes sample country/currency and plan prices.

## 7. Documentation & domain model

- `backend/CONTEXT.md`: **Catalog** definition updated (prices are now part of the catalog — current text says otherwise). New terms: **Currency**, **Country**, **Regional Settings**, **Currency Catalog**, **Official Currency**. Starter/Pro table: country/currency Pro-only.
- `frontend/CONTEXT.md`: "País y moneda" tab + pickers terms.
- New `docs/architecture/regional-settings.md`; update `subscriptions.md` (tenant-settings section) and `tenant-data-export.md` (contract change).
- This design doc committed to git.

## 8. Out of scope

- Exchange rates / multi-currency conversion.
- Per-plan currency.
- Daily refresh worker (deferred by decision; regeneration is manual/PR).
- Currency formatting via `Intl.NumberFormat` full i18n placement — v1 uses `{symbol} {amount}` with catalog symbol.

## 9. Testing

- Backend (pytest + aiosqlite): catalog module unit tests (file load, validation, official currency, symbol); tenant-settings endpoint tests (get/put, gate nulling for Starter, 409 invalid codes); plan price in catalog CRUD; public catalog includes price+currency; export contract includes new fields.
- Frontend (vitest): picker grouping/separator behavior, tab gating, price input/display, demo parity specs.
