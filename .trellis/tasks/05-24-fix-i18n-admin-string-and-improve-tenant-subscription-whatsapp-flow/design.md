# Design — i18n + WhatsApp subscriptions interactive flow

## Scope

- Frontend admin/club clientes label migration to i18n (`Contraseña` / `Password`).
- Backend WhatsApp tenant subscriptions: remove hardcoded header/status texts.
- Backend WhatsApp tenant subscriptions list UX: enforce interactive navigation and pagination.

## Affected Areas

- `frontend/src/views/TenantDashboardView.vue`
- `backend/app/core/i18n/catalogs_es_frontend.py`
- `backend/app/core/i18n/catalogs_en_frontend.py`
- `backend/app/services/whatsapp_tenant_console_service/formatters.py`
- `backend/app/core/i18n/catalogs_es_wa.py`
- `backend/app/core/i18n/catalogs_en_wa.py`
- Subscription flow handlers in `backend/app/services/whatsapp_tenant_console_service/*` that manage filter/select navigation.

## Behavior Contract

### Frontend
- Replace hardcoded label with i18n key.
- ES shows `Contraseña`; EN shows `Password`.

### WhatsApp subscriptions list
- Header and status labels resolved via i18n keys only.
- Pagination unit = 7 subscriptions per page.
- Reserved commands in filtered list step:
  - `0`: cancel/exit to tenant main menu.
  - `8`: previous page (when available).
  - `9`: next page (when available).
- Selection map for subscriptions limited to keys `1..7` per page.

## State Model

Use session temp state in subscription flow:
- `status` filter selected
- `page` (1-based)
- optional `total_pages` derived at render time

`selection_map` rebuilt each page render using only visible page items.

## Edge Cases

- <=7 subscriptions: no pagination options shown.
- First page: hide `8`.
- Last page: hide `9`.
- Invalid page command: return localized error + keep same page.
- `0` from any list page: always reset/exit flow.

## Risks

- Existing global command handling can intercept `0`; must preserve expected reset path.
- Must avoid collisions between pagination commands and subscription index commands.
- i18n key additions must exist in ES/EN catalogs to avoid fallback issues.

## Verification

- Focused tests for tenant WhatsApp subscriptions flow navigation and selection map.
- Focused tests for i18n message rendering where available.
- Optional full backend test pass for regression confidence.
- Frontend build for template/i18n integrity.