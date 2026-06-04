# Catalog CRUD for WhatsApp Tenant Console and Dashboard

Date: 2026-06-03
Related: GitHub #43, Linear TPL-6
Status: Approved design

## Purpose

Tenant admins need one coherent Catalog CRUD module for services and plans across WhatsApp Tenant Console, REST API, and dashboard. Current implementation supports basic REST CRUD and partial WhatsApp browsing/editing, but lacks WhatsApp create/delete flows and dashboard-safe cascade delete previews.

## Scope

In scope:

- Tenant-scoped service and plan create, list, edit, delete behavior.
- WhatsApp Catalog menu, pagination, counts, duplicate-name retry, and cascade delete confirmation flows.
- REST delete preview endpoints and confirmation-gated delete endpoints.
- Dashboard delete preview modal using existing `CatalogPanel.vue` patterns.
- Backend and frontend user-facing strings for new behavior.
- Tests and docs for changed behavior.

Out of scope:

- Database schema changes unless implementation proves current cascade mappings insufficient.
- New dashboard page architecture beyond minimal `CatalogPanel.vue` extension.
- New bulk actions, search, filtering, or service/plan metadata fields.

## Chosen approach

Use incremental CRUD over current Catalog flow.

- Keep existing route convention under `/catalog`.
- Keep current WhatsApp Tenant Console service modules and extend `catalog_flow.py`, `_routers.py`, constants, formatters, and assignments.
- Keep `CatalogService` as backend source of catalog CRUD behavior.
- Add delete preview and confirmed cascade deletion in service layer, used by both REST and WhatsApp.
- Extend `CatalogPanel.vue` with a focused preview modal rather than rewriting dashboard UI.

Rejected alternatives:

1. Full WhatsApp Catalog rewrite: cleaner state machine, but larger risk and unnecessary for issue scope.
2. Backend-only implementation: faster, but existing dashboard Catalog UI means dashboard acceptance criteria should be satisfied.

## Backend REST design

Existing routes stay coherent with current `backend/app/api/v1/endpoints/catalog.py` style.

Add preview endpoints:

- `GET /catalog/services/{service_id}/delete-preview?page=1&page_size=10`
- `GET /catalog/services/{service_id}/plans/{plan_id}/delete-preview?page=1&page_size=10`

Change delete endpoints to require explicit confirmation:

- `DELETE /catalog/services/{service_id}?confirm=true`
- `DELETE /catalog/services/{service_id}/plans/{plan_id}?confirm=true`

If `confirm` is absent or false, return a validation-style 400 response with localized message. Existing 404 behavior remains for missing tenant-scoped resources. Duplicate create/update errors continue using existing conflict handling, with localized `UserFacingError` messages when available. Duplicate detection remains case-insensitive after trimming names: service names are unique per tenant; plan names are unique per parent service.

Preview payload includes:

- target type and target name
- affected plan count for service deletion
- total affected subscription count
- active affected subscription count
- active subscription rows for current page
- pagination metadata
- explicit note that historical, expired, cancelled, and other non-active subscriptions are also deleted even when not listed

Active subscriptions mean exactly `status == "active"`; no expiration-date filter. Active subscription rows order by `expires_at` ascending, closest expiration first. If `expires_at` is null, null dates sort after dated subscriptions.

## Service-layer design

Add CatalogService methods for:

- service delete preview
- plan delete preview
- confirmed service deletion
- confirmed plan deletion

Preview/query logic is shared by REST and WhatsApp so counts and row ordering stay consistent. Confirmed service deletion cascades through associated plans and all associated subscriptions. Confirmed plan deletion cascades through all associated subscriptions for that plan. If existing SQLAlchemy/DB cascade mappings already perform deletion safely, service methods may rely on them after collecting counts; otherwise implementation deletes dependents explicitly in tenant scope.

Subscription warning rows display:

`streaming email - client name - phone number - service/plan - expiration date`

Formatting may use existing subscription formatting helpers where practical.

## WhatsApp design

Catalog entry now starts with a menu instead of direct service selection.

When services exist:

```text
📦 *Catálogo*

1️⃣ Ver servicios
2️⃣ Crear servicio
3️⃣ Eliminar servicio
9️⃣ Volver al menú principal
0️⃣ Cancelar
```

When no services exist:

```text
📦 *Catálogo*

📭 No hay servicios registrados.

1️⃣ Crear servicio
9️⃣ Volver al menú principal
0️⃣ Cancelar
```

Behavior:

- `9` returns to main tenant menu.
- `0` cancels active flow and closes WhatsApp session through existing endpoint response status behavior.
- Service lists are alphabetical and paginated at 7 items/page.
- Service row shows: service name, plan count, active subscription count.
- Service detail hides ID and shows edit name, view plans, create plan, delete plan, and back. Delete service remains available only from Catalog menu.
- Plan lists are alphabetical and paginated at 7 items/page.
- Plan row shows: plan name and active subscription count.
- Selecting a plan row opens plan detail.
- Plan detail hides ID and shows edit name, delete plan, and back.
- If view plans finds no plans, show empty-plan menu with create plan, back, cancel.
- If delete plan is selected for a service with no plans, show no-plans-for-delete message and return to Catalog menu.

Create/edit:

- Create service asks for name, creates immediately, no confirmation.
- Create plan asks for name, creates immediately, no confirmation.
- Edit service/plan asks for new name and updates immediately.
- Empty or duplicate names show clear error and keep same name-input step for retry or `0` cancel.

Delete service:

- Requires `CONFIRMAR` or `CONFIRM`, case-insensitive after trimming.
- Warning shows affected plan count and active subscription impact.
- Active subscriptions list paginates at 7/page, ordered by `expires_at` ascending.
- `8` advances to next warning page when available.
- `9` returns to previous screen inside delete warning context.
- `CONFIRMAR` or `CONFIRM` works from any warning page.
- Warning explicitly states historical/expired/cancelled subscriptions are deleted too.
- Success message includes deleted service name plus deleted plan/subscription summary.

Delete plan:

- Requires `CONFIRMAR` or `CONFIRM`, case-insensitive after trimming.
- Warning shows active subscription impact and paginated active rows at 7/page.
- `CONFIRMAR` or `CONFIRM` works from any warning page.
- Warning explicitly states historical/expired/cancelled subscriptions are deleted too.
- Success message includes deleted plan name plus deleted subscription summary when applicable.

After any successful create/edit/delete mutation, WhatsApp shows the specific success text plus:

```text
1️⃣ Volver al menú principal
0️⃣ Cancelar
```

`1` clears the flow and shows main menu. `0` clears the session and closes the WhatsApp session.

## Dashboard design

Extend existing `frontend/src/components/CatalogPanel.vue` minimally.

- Replace `window.confirm` deletion with preview modal.
- Fetch service or plan delete preview before showing modal.
- Show target name, affected counts, warning note, and active subscription rows.
- Paginate active rows at 10/page by re-fetching preview with requested page.
- Require typed `CONFIRMAR` or `CONFIRM` before enabling final delete button.
- Submit delete with `?confirm=true`.
- Preserve existing create/rename forms and error display patterns.
- Surface duplicate-name and delete errors via current `getApiError` helper.

No new dashboard route or global modal framework is required unless implementation finds an existing reusable modal pattern nearby.

## I18n and docs

Backend WhatsApp strings must be added to ES and EN catalogs for:

- catalog menu and empty menu
- create/edit prompts and success/error messages
- duplicate/empty retry copy where missing
- delete warning, pagination, confirmation, and cascade summary messages
- REST confirmation-required error where applicable

Frontend strings must follow existing frontend i18n store/catalog pattern for modal labels, warning text, confirm input, pagination, and errors.

Project docs should be updated for changed Catalog behavior, especially tenant dashboard and WhatsApp Tenant Console behavior.

## Testing plan

Backend tests:

- REST preview returns required counts, note, ordered active rows, and pagination metadata.
- REST delete without `confirm=true` fails.
- Confirmed service delete removes service, plans, and all related subscriptions in tenant scope.
- Confirmed plan delete removes plan and all related subscriptions in tenant scope.
- Duplicate service/plan names return validated conflict errors.
- WhatsApp Catalog starts with menu and reduced empty menu.
- WhatsApp service and plan lists are alphabetical, paginated at 7, and include counts.
- WhatsApp create/edit duplicate-name paths keep retry step.
- WhatsApp delete warnings require confirmation and support pagination.
- WhatsApp post-success prompt handles `1` and `0` correctly.

Frontend tests/build:

- Add/adjust Vitest coverage for delete preview modal if current frontend test setup supports component interaction.
- Run frontend tests/build after frontend changes.

Verification commands:

- `cd backend && uv run pytest`
- `cd frontend && npm test`

## Acceptance mapping

This design covers all GitHub #43 acceptance criteria: WhatsApp menu/list/detail/create/edit/delete behavior, duplicate retry, cascade delete confirmations, REST/dashboard preview confirmation, i18n additions, docs update, and backend/frontend verification.
