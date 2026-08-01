# Regional Settings (Country, Currency, Plan Pricing) — Design

**Status**: Draft (pending user review)
**Date**: 2026-08-01
**Scope**: Backend (FastAPI), Frontend (React), Docs

## 1. Problem

Tenants need to configure their business **Country** and **Currency**, and catalog Plans need an optional **price** displayed with the tenant's currency symbol. Currency data (countries, official currency per country, symbols, minor units) must be selectable offline without per-request calls to an external provider, with **correct official symbols** (e.g. Venezuela uses "Bs." — CLDR's `es_VE` locale incorrectly says "Bs.S" and generic locales omit the symbol).

## 2. Decisions (resolved with user)

| Decision | Choice |
|---|---|
| Currency data source | Bundled static files committed to repo, regenerated ~2×/year from Unicode CLDR (dev-time `babel`). No runtime external calls. |
| Symbol overrides | Small curated `overrides.json` wins over CLDR symbols (initially `VES → "Bs."`). |
| Price scope | **All surfaces**: catalog UI, Public API Catalog (plan `price` + top-level `currency`), Tenant Data Export (`plan_price` in `service-catalog.csv`, `currency` in `account-profile.csv` — documented stable-contract change, ADR 0003). |
| Regional tab | New tab "Configuración regional" / "Regional settings" inside My Account. `Idioma` and `Zona horaria` move out of Settings categories into this tab. |
| Plan gate | **Starter**: country + language visible/editable; timezone + currency hidden (GET nulled, PUT non-null rejected 404). **Pro / Master support**: all four. |
| Country ↔ currency | Independent fields. Official currency of the selected country renders first in the picker (grouped above a separator), never auto-selected, never overwrites a manually chosen currency. |
| Price | Optional single `Decimal` per plan (NUMERIC(12,2), nullable, ≥ 0). `NULL` = "Precio a consultar". Always interpreted in the tenant's currency. |
| Demo parity | Full: Demo Pro workspace gets functional regional tab and demo catalog plans with sample prices; Demo Baseline includes country/currency and plan prices. |
| Formatting | `{symbol} {amount}` using catalog symbol + `Intl.NumberFormat` decimal with active locale and the currency's minor units. Never browser CLDR symbols (would risk "Bs.S"). |
| Tab order | My Account tabs become Profile, Security, Regional, Data. |

## 3. Currency Catalog module (backend)

Deep module at `backend/app/core/currency_catalog/`:

```
currency_catalog/
├── data.json          # generated dev-time, committed (~15-20KB)
├── overrides.json     # curated symbol fixes (VES → "Bs.")
├── currency_catalog.py
└── __init__.py
```

**`data.json`** shape:

```json
{
  "source": "Unicode CLDR <version>",
  "generated_at": "YYYY-MM-DD",
  "countries": [{"code": "VE", "currency": "VES"}],
  "currencies": {"VES": {"symbol": "Bs.", "minor_units": 2}}
}
```

Generation rules (dev-time script `backend/scripts/regenerate_currency_catalog.py`, run via `uv run --with babel`; `babel` is NOT a runtime dependency):

- **Countries**: territories matching `^[A-Z]{2}$` (excludes 001, EU, …). Official currency = current one (`end_date is None` and `is_tender`). For territories with multiple current currencies (BT, HT, LS, NA, PA, PS, ZW) choose the national one (the non-USD/EUR/INR/ZAR/ILS/JOD entry; e.g. PA → PAB).
- **Symbols**: `overrides.json` wins over CLDR. Missing symbols or symbols falling back to the code are logged as warnings at generation time and left for curation.
- **Minor units**: default 2; CLDR `currency_fractions` overrides where present (JPY→0, KWD/BHD→3, CLF→4).
- **Two outputs**: `backend/app/core/currency_catalog/data.json` and `frontend/src/lib/currency-catalog.json` (demo adapter copy) — one source, two files, both committed.

**`currency_catalog.py`** — small interface, dense implementation (module-level cache, loads once):

```
list_countries()           → [{"code": "VE", "currency": "VES"}, ...]
list_currencies()          → [{"code": "VES", "symbol": "Bs.", "minor_units": 2}, ...]
official_currency_of(code) → "VES" | None
symbol_of(code)            → "Bs." | None
validate_country(code)     → bool
validate_currency(code)    → bool
```

No external-provider seam (one real adapter: the bundled file). Not copied from the timezone catalog's provider stub.

## 4. Data model & migration

New Alembic migration, 3 columns (tables already tenant-scoped; no RLS changes):

| Table | Column | Type | Notes |
|---|---|---|---|
| `tenant_settings` | `country` | VARCHAR(2) nullable | ISO 3166-1 alpha-2; NULL = not chosen |
| `tenant_settings` | `currency` | VARCHAR(3) nullable | ISO 4217; NULL = not chosen (UI shows no symbol) |
| `plans` | `price` | NUMERIC(12,2) nullable | Optional; inherited tenant currency |

Nullable without defaults (unlike `locale`/`timezone`): "not configured" is distinct from any concrete code.

## 5. Backend API

- `GET /api/v1/tenant-settings/currencies` → `{countries: [...], currencies: [...]}`. Auth: `require_tenant_or_master` + `DemoGuardedUser` (precedent: `/tenant-settings/timezones`).
- `TenantSettingsResponse` / `TenantSettingsUpdate`: add `country`, `currency`. Validators normalize uppercase and call `validate_country` / `validate_currency` from the catalog; invalid → 409 (existing ValueError pattern). `country` accepts `None` to clear.
- **Gate in endpoint** (same place as today's timezone gate): Starter role → `timezone` and `currency` nulled in GET; PUT with non-null `timezone` or `currency` → 404. `country` and `locale` always allowed. Master support bypasses.
- `PlanCreate` / `PlanUpdate` / `PlanResponse`: add `price: Decimal | None` (`condecimal(max_digits=12, decimal_places=2)`, min 0). Catalog service passes the field through. Error key `invalid_plan_price` added to catalog error mapping.
- Public API Catalog: `PublicCatalogPlan` gains `price`; `PublicCatalogResponse` gains top-level `currency: {"code", "symbol", "minor_units"} | None` derived from tenant settings via the catalog. `PublicApiKeyService.build_public_catalog` reads `tenant_settings.currency`.
- Tenant Data Export (`export_worker.py`): `service-catalog.csv` adds column `plan_price` (plain decimal `"12.50"`, empty when NULL); `account-profile.csv` adds column `currency` (ISO code, empty when not set). Documented as a stable-contract change under ADR 0003.

## 6. Frontend

**Navigation changes:**
- `my-account-section.tsx`: new tab `regional` (Profile, Security, Regional, Data). `Tabs defaultValue` stays `"profile"`.
- `settings-categories.ts` + `settings-page.tsx`: remove `locale` and `timezone` categories and their entries in `buildSections`; delete `LocaleSection`/`TimezoneSection` usage from Settings (components move into the regional tab).

**RegionalSettingsSection** (new, in `features/admin/components/`):
- Loads `tenantSettings` + `timezoneOptions` + `currencyOptions` in parallel (pattern: `TimezoneSection`).
- Renders Country (all plans), Language (all plans), Timezone (Pro), Currency (Pro). Master support sees all four. Starter sees only Country + Language.
- Preserves `LocaleSection` behavior: reloads catalog after locale change in demo mode.
- Help targets `language`/`timezone` re-anchor to the corresponding fields inside the tab.

**CountryPicker** (new): options from catalog; localized names via `Intl.DisplayNames` with the active locale (ISO codes stored — no duplicated i18n catalogs). Search support (pattern: `TimezonePicker`).

**CurrencyPicker** (new): currencies with symbols. With a selected country, renders "Moneda del país" group (official currency first), separator, then all others (official deduped from the second group). No country → plain full list, no groups. Changing country never overwrites currency; each field displayed independently. Builds on the `TimezonePicker` portal/search pattern; renders the `group` field that the timezone picker type already carries but does not yet render.

**Catalog price:**
- `catalog-api.ts`: `Plan` / `PlanCreate` / `PlanUpdate` gain `price: number | null`.
- `catalog-page.tsx`: create-plan form gains optional price input (2 decimals); plan list rows display `{symbol} {amount}` (catalog symbol + `Intl.NumberFormat` decimal with active locale and minor units) or "Precio a consultar" when NULL. Rename dialog becomes an edit dialog (name + price).
- Symbol sourced from the **backend catalog** (never browser CLDR) so "Bs." is guaranteed.

**Settings store (`settings.ts`):** `loadCurrencyOptions(source)` → `{ countries, currencies }` mirroring `loadTimezoneOptions` (in-flight dedup, epoch guard). `TenantSettings`/`TenantSettingsUpdate` types gain `country`/`currency`; `SettingsDataSourceContract` gains `loadCurrencyOptions`.

**Demo parity:**
- `demo-settings.ts`: `loadCurrencyOptions` returns the bundled `frontend/src/lib/currency-catalog.json` copy; `validateTenantSettings` gains country/currency validation.
- `demo-baseline.ts`: `tenant_settings` gains `country`/`currency`; demo catalog plans gain sample prices.
- `demo-catalog.ts` / `demo-workspace.ts`: `price` passthrough with same validation (≥ 0, 2 decimals).

**i18n (es/en):** new keys — tab name, País/Country, Moneda/Currency, "Moneda del país"/"Country currency", "Precio a consultar"/"Price on request", group labels, errors.

## 7. Documentation & domain model

- `docs/adr/0005-currency-catalog-clrd-overrides.md` — written and committed (CLDR + overrides; rejected alternatives).
- `backend/CONTEXT.md` — updated: **Catalog** definition (prices are now part of the catalog); new terms **Catalog Price**, **Currency Catalog**, **Country**, **Currency**, **Official Currency**, **Regional Settings**; **Public API Catalog** exposes price + currency; plan-behavior table row for Regional Settings.
- `frontend/CONTEXT.md` — updated: **My Account** tabs include Regional; new terms **Regional Tab**, **CountryPicker**, **CurrencyPicker**; **Settings Store** includes currency options; Product Labels add "Configuración regional" and "Moneda del país".
- New `docs/architecture/regional-settings.md`; update `subscriptions.md` (tenant-settings section) and `tenant-data-export.md` (contract change).

## 8. Out of scope

- Exchange rates / multi-currency conversion / per-plan currency.
- Daily refresh worker (regeneration is manual/PR-driven).
- Auto-selecting currency when a country is chosen.
- Starter upsell hints inside the regional tab (Pro fields hidden entirely).

## 9. Testing

**Backend (pytest + aiosqlite):**
- Catalog module: file load + overrides, `validate_country`/`validate_currency`, `official_currency_of`, `symbol_of` (VES → "Bs."), multi-currency territory selection.
- Regeneration script: golden-file test (stable output for a given CLDR snapshot).
- Tenant-settings endpoint: GET/PUT country/currency; Starter gate (timezone+currency nulled in GET, 404 on non-null PUT); 409 invalid codes; Master support bypass.
- Catalog CRUD: price create/update/response, validation (≥ 0, 2 decimals).
- Public API: plans expose `price`; top-level `currency` derived from tenant settings.
- Export: `service-catalog.csv` includes `plan_price`; `account-profile.csv` includes `currency`.

**Frontend (vitest):**
- CurrencyPicker: grouped + separator behavior (official first, deduped), plain list without country.
- RegionalSettingsSection: Starter hides tz/currency; Pro/Master show all; demo locale-change catalog reload preserved.
- Settings store: `loadCurrencyOptions` dedup + epoch.
- Catalog page: price input, symbol display, "Precio a consultar".
- Demo: baseline country/currency/prices; adapter price validation.
- Update existing specs broken by the move (`settings-page.spec`, `my-account-section.spec`, `locale-section-demo.spec`, `timezone-*`).
