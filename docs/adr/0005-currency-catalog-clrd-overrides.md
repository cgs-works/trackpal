# Currency Catalog sources from Unicode CLDR with curated symbol overrides

TrackPal's selectable countries and currencies come from a static, versioned JSON catalog generated at development time from Unicode CLDR (via `babel`) and committed to the repo — no runtime calls to an external provider. CLDR is authoritative for ISO 4217 codes, the country-to-current-currency mapping, and most symbols, but its symbols are locale-dependent and sometimes outdated or missing (e.g. the `es_VE` locale renders VES as "Bs.S" and generic locales omit it entirely, while the official BCV usage is "Bs."); a small hand-maintained overrides file therefore takes precedence over CLDR symbols. Decimal digits default to 2 with CLDR overrides where they differ. Regeneration is a manual dev-time script run roughly twice a year when CLDR data changes, and it emits both the backend `data.json` and the frontend demo copy from one source.

## Considered Options

- **Runtime external provider** (Open Exchange Rates, etc.): rejected — network dependency and rate limits in runtime, and TrackPal needs offline selectable data, not live conversion.
- **Frontend-only catalog** (TypeScript module in the SPA): rejected — the backend must validate country/currency codes on write, and the demo adapter needs the same data; a single backend-owned file keeps one source of truth.
- **Raw CLDR symbols without overrides**: rejected — would surface wrong symbols like "Bs.S" for VES in some locales and no symbol in others.
