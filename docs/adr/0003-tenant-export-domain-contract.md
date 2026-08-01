# Tenant Data Export uses a stable domain contract

Tenant Data Export is delivered as one ZIP containing `account-profile.csv`, `client-data.csv`, `service-catalog.csv`, `subscription-snapshot.csv`, `blocked-phones.csv`, `trackpal-data.json`, and a localized `README.txt`. Machine-readable filenames, CSV headers, and JSON keys remain stable in English and use semantic `snake_case` names defined from user-facing domain concepts; neither files nor fields mirror database tables and columns one-to-one. Only the README is localized. Internally the account profile belongs to the Tenant, but user-facing copy calls it "Mi cuenta" / "My account" instead of exposing Tenant jargon. The subscription snapshot contains existing subscription records, not lifecycle events or reminder logs. This makes the export predictable without exposing the persistence model as its contract.

## Stable-contract changes

The following columns were added to the export stable contract:

| File | New column | Type | Source | Notes |
|------|-----------|------|--------|-------|
| `account-profile.csv` | `currency` | string | `TenantSettings.currency` | ISO 4217 code; empty when unset |
| `service-catalog.csv` | `plan_price` | string | `Plan.price` | Formatted as `"{price:.2f}"` when set; empty when `None` |

These columns are appended after their respective logical groupings and are reflected in both CSV headers and JSON keys. Export format version remains `2`.
