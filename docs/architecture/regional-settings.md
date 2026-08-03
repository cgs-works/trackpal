# Regional Settings

Regional Settings configure tenant-specific locale, timezone, country, and currency preferences. These settings control language selection, time-based operations (subscription reminders), price display, and data export formatting.

## Currency Catalog

### Source and Generation

The Currency Catalog is a static, versioned JSON catalog generated at development time from Unicode CLDR (via `babel`). It is committed to the repo and never queried at runtime.

**Two outputs from one source:**
- `backend/app/core/currency_catalog/data.json` — Backend catalog
- `frontend/src/lib/currency-catalog.json` — Frontend demo workspace copy

**Generation script:** `backend/scripts/regenerate_currency_catalog.py`

```bash
cd backend && uv run --with babel python -m scripts.regenerate_currency_catalog
```

**Override mechanism:** A hand-maintained `overrides.json` file takes precedence over CLDR symbols for cases where CLDR output is locale-dependent or outdated (e.g., VES symbol rendering).

**Regeneration frequency:** Roughly twice a year when CLDR data changes.

### Module API

File: `backend/app/core/currency_catalog/currency_catalog.py`

| Function | Description |
|----------|-------------|
| `validate_country(code)` | Check if ISO 3166-1 alpha-2 code exists in catalog |
| `validate_currency(code)` | Check if ISO 4217 code exists in catalog |
| `symbol_of(currency_code)` | Get currency symbol (e.g., "Bs." for VES) |
| `minor_units_of(currency_code)` | Get decimal places (e.g., 2 for USD, 0 for JPY) |
| `list_countries()` | Return all country entries with official currency mapping |
| `list_currencies()` | Return all currency entries with symbol and minor units |
| `official_currency_of(country_code)` | Get official currency for a country |

### Data Model

File: `backend/app/models/tenant_settings.py`

```
tenant_settings
├── tenant_id (UUID, PK, FK → tenants.id CASCADE)
├── locale (VARCHAR(10), default "en", not null)
├── timezone (VARCHAR(100), default "UTC", not null)
├── country (VARCHAR(2), nullable)  -- ISO 3166-1 alpha-2
├── currency (VARCHAR(3), nullable) -- ISO 4217
├── created_at (TIMESTAMPTZ)
└── updated_at (TIMESTAMPTZ)
```

**Validation:** Country and currency codes are validated against the Currency Catalog on write. Invalid codes return `409 Conflict` with `"invalid_country"` or `"invalid_currency"`.

## Gating Matrix

| Setting | Starter Plan | Pro Plan |
|---------|--------------|----------|
| Country | ✅ | ✅ |
| Language (locale) | ✅ | ✅ |
| Timezone | ❌ (hidden, returned as null) | ✅ |
| Currency | ❌ (hidden, returned as null) | ✅ |

**Master Support Context:** When Master views a Starter tenant via support context, Pro-only fields are visible and editable.

**Backend enforcement:** `GET/PUT /api/v1/tenant-settings` returns `404` for timezone/currency on Starter tenants (when Tenant Admin role). Master always has full access.

## API

### GET /api/v1/tenant-settings

Returns tenant settings with plan-aware field filtering:

```json
{
  "tenant_id": "uuid",
  "locale": "es",
  "timezone": "America/Bogota",
  "country": "CO",
  "currency": "COP",
  "created_at": "2026-01-15T10:30:00Z",
  "updated_at": "2026-08-01T14:20:00Z"
}
```

**Starter response:** `timezone` and `currency` are `null`.

### PUT /api/v1/tenant-settings

Updates settings with validation:

```json
{
  "locale": "es",
  "country": "VE",
  "currency": "VES"
}
```

**Error responses:**
- `409 Conflict` — Invalid country/currency code
- `404 Not Found` — Starter tenant attempting to set timezone/currency

### GET /api/v1/tenant-settings/currencies

Returns the full Currency Catalog:

```json
{
  "countries": [
    { "code": "CO", "currency": "COP" },
    { "code": "VE", "currency": "VES" }
  ],
  "currencies": [
    { "code": "COP", "symbol": "$", "minor_units": 2 },
    { "code": "VES", "symbol": "Bs.", "minor_units": 2 }
  ]
}
```

**Auth:** Tenant or Master with ActiveTenantId.

## Frontend Pickers

### CountryPicker

File: `frontend/src/features/admin/components/country-picker.tsx`

- Searchable dropdown with `Intl.DisplayNames` for localized country names
- Includes "— None —" option to clear selection
- Displays country code in parentheses (e.g., "Colombia (CO)")
- No auto-select on load; defaults to `null`

### CurrencyPicker

File: `frontend/src/features/admin/components/currency-picker.tsx`

- **Official-currency-first grouping:** When a country is selected, its official currency appears in a separate "Country Currency" group at the top
- Searchable by code or symbol
- Displays format: "CODE · SYMBOL" (e.g., "VES · Bs.")
- No auto-select on load; defaults to `null`
- Manual selection required even when country has an official currency

### TimezonePicker

File: `frontend/src/features/admin/components/timezone-picker.tsx`

- Lists IANA timezones from `GET /api/v1/tenant-settings/timezones`
- Grouped by region (e.g., "America", "Europe")
- Includes UTC offset in label

## Price Semantics

### Null Price Handling

When `Plan.price` is `null`:

- **WhatsApp Console:** Displayed as "Precio a consultar" (locale-aware: "Price on request" in English)
- **Frontend Catalog:** Shows "A consultar" badge
- **Public API:** Returns `"price": null`
- **Export:** Empty string in CSV, `null` in JSON

### Tenant Currency Display

**Backend formatting:** `format_price(amount, symbol, locale)` in `backend/app/services/whatsapp_tenant_console_service/format_helpers.py`

- Spanish locale: Comma as decimal separator (e.g., "Bs. 12,50")
- English locale: Dot as decimal separator (e.g., "Bs. 12.50")
- Missing symbol: Falls back to raw amount (e.g., "12.50")

**Frontend formatting:** `formatPrice()` helper mirrors backend logic.

### Price Input Parsing

`_parse_price_input(value)` accepts:
- Dot separator: "12.50"
- Comma separator: "12,50"
- Rejects negative values and amounts with more than 2 decimal places

## WhatsApp Console Integration

### Price Display in Catalog Flow

When listing services/plans in WhatsApp:
- Prices load tenant currency symbol from `TenantSettings.currency`
- `format_price()` renders locale-appropriate display
- Missing price shows "Precio a consultar"

### Price Input in Create/Edit Flows

When creating/editing plans via WhatsApp:
- Prompt asks for price in tenant's configured currency
- Validates against `_parse_price_input()`
- Stores as `Decimal` in database

## Public API

File: `backend/app/api/v1/endpoints/public_catalog.py`

### GET /api/v1/public/catalog

Returns catalog with currency metadata:

```json
{
  "services": [
    {
      "id": "uuid",
      "name": "Netflix",
      "icon": "simple-icons:netflix",
      "plans": [
        { "id": "uuid", "name": "Premium", "price": "15.99" }
      ]
    }
  ],
  "currency": {
    "code": "USD",
    "symbol": "$",
    "minor_units": 2
  }
}
```

**Currency resolution:** Reads `TenantSettings.currency`, resolves symbol and minor units from Currency Catalog.

**Plan price:** Returns `null` when price is not set; consumers must handle "on request" case.

## Export

File: `docs/architecture/tenant-data-export.md`

### Currency in Export

| File | Column | Source | Format |
|------|--------|--------|--------|
| `account-profile.csv` | `currency` | `TenantSettings.currency` | ISO 4217 code (empty when unset) |
| `service-catalog.csv` | `plan_price` | `Plan.price` | `"{price:.2f}"` when set; empty when `null` |

**Export format version:** 2 (unchanged by regional settings).

**JSON representation:**
```json
{
  "account_profile": {
    "currency": "VES"
  },
  "service_catalog": [
    {
      "plan_price": "12.50"
    }
  ]
}
```

## Demo Parity

File: `frontend/src/features/demo/services/demo-settings.ts`

Demo workspaces use the same Currency Catalog as production:

```typescript
import currencyCatalog from "@/lib/currency-catalog.json";
```

**Validation:** Demo mode validates country/currency codes against the catalog before storing in browser-local state.

**Initial locale:** The Master selects `en` or `es` when creating the Demo Tenant. The backend returns that creation locale during Demo authentication so the first browser-local baseline starts in the selected language.

**Locale changes:** Demo Settings can change the locale later. The updated locale is stored only in the browser-local workspace and reloads the authenticated catalog immediately; Demo Reset restores the selected creation locale.

**Timezone options:** Demo uses `Intl.supportedValuesOf("timeZone")` with fallback to curated list.

## Help Integration

### Regional Settings Help Target

The Settings page includes `data-help-id="admin.settings.regional"` for contextual help.

### Help Topics

The authenticated Tenant Admin Help artifact includes regional topics:
- Country selection guidance
- Currency configuration (Pro-only)
- Timezone configuration (Pro-only)

### Safe Navigation

Help links use safe navigation patterns:
- Regional settings links target `/admin/settings` section
- No mutation operations in help content
- Plan-aware filtering enforced by Help API

## Related Documentation

- [Subscriptions](subscriptions.md) — Timezone usage for reminder scheduling
- [Tenant Data Export](tenant-data-export.md) — Currency in export bundle
- [I18n System](i18n-system.md) — Locale resolution and translations
- [User Help System](user-help-system.md) — Help integration patterns
- [ADR-0005: Currency Catalog](../adr/0005-currency-catalog-clrd-overrides.md) — Design decision for CLDR-based catalog
