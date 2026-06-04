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
- Soft-delete, `is_active`, or active/inactive lifecycle for services/plans.

## Product rules from prompt

- Catalog means CRUD for services and plans.
- Services and plans do not get active/inactive status; all existing services count as active services and all existing plans count as active plans.
- Active subscription means exactly `status == "active"`; do not additionally filter by expiration date.
- Service names are unique within a tenant.
- Plan names are unique within the same service, not globally across the tenant.
- Service list rows count all plans under the service.
- Service active subscription count is the sum of active subscriptions across all plans under that service.
- Plan rows count active subscriptions under that plan.
- Use correct singular/plural in WhatsApp and dashboard/frontend if touched.
- User-facing WhatsApp text must use backend i18n catalogs unless preserving an existing established hardcoded pattern is narrower and safer.

## Execution and PR requirements

- Work on branch `feature/43-catalog-crud-whatsapp-dashboard` from `main`.
- Use multiple logical commits, not one giant commit.
- Open one Draft PR and keep it draft until human review.
- Link GitHub issue `#43` and Linear issue `TPL-6` in the Draft PR.
- Organize PR description by phases/checklist: backend service/repository/API, WhatsApp Catalog flow + i18n, frontend dashboard if applicable, tests, docs.
- Include verification results in the PR description. If a command cannot run, state exactly why.
- Explain the chosen cascade strategy in the PR description.
- Before coding, inspect `AGENTS.md`, `docs/SUMMARY.md`, current Catalog REST endpoints, dashboard Catalog UI, models/migrations, service/repository patterns, WhatsApp Tenant Console flow, and i18n catalogs.
- Preserve existing style, tenant scoping, and RLS behavior. Do not infer tenant scope from arbitrary payload IDs.
- Keep test imports safe with `DATA_ENCRYPTION_KEY` set before app imports.

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
- active affected subscription count
- historical/non-active affected subscription count
- total affected subscription count
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

Preview/query logic is shared by REST and WhatsApp so counts and row ordering stay consistent. Confirmed service deletion cascades through associated plans and all associated subscriptions. Confirmed plan deletion cascades through all associated subscriptions for that plan. Implementation must inspect current models, constraints, and migrations, then choose the minimum safe cascade strategy: service-layer explicit cascade, DB-level cascade, or a combination. If existing SQLAlchemy/DB cascade mappings already perform deletion safely, service methods may rely on them after collecting counts; otherwise implementation deletes dependents explicitly in tenant scope. If migrations/foreign keys/model changes prove necessary, add Alembic migrations; do not make schema changes if service/repository code is sufficient. Update service layer, repository layer, protocols, fakes, tests, REST schemas/routes, WhatsApp handlers, and i18n catalogs consistently where those abstractions exist.

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

- In the Catalog main menu, `9` returns to main tenant menu.
- In all Catalog screens, `0` closes the full WhatsApp session and must respect the Evolution/n8n close contract wherever applicable: `status="closed"` and `close_jid`.
- In other Catalog screens, `9` returns to the previous logical screen or main menu depending on context.
- Paginated Catalog lists use `8️⃣ Siguiente` to advance, `9️⃣ Regresar` to return to the previous logical screen, and `0️⃣ Cancelar` to close/cancel according to Catalog rule above.
- Do not implement previous-page pagination with `9`; `9` means back, not previous page.
- Service lists are alphabetical and paginated at 7 items/page.
- Service row shows: service name, plan count, active subscription count, with correct singular/plural.
- Service detail hides ID and shows edit name, view plans, create plan, delete plan, and back. Delete service remains available only from Catalog menu.
- Plan lists are alphabetical and paginated at 7 items/page.
- Plan row shows: plan name and active subscription count, with correct singular/plural.
- Selecting a plan row opens plan detail.
- Plan detail hides ID and shows edit name, delete plan, and back.
- If view plans finds no plans, show empty-plan menu with create plan, back, cancel.
- If delete plan is selected and the service has no plans, show a no-plans-for-delete message and return to the Catalog menu.

Create/edit:

- Create service asks for name, creates immediately, no confirmation.
- Create plan asks for name, creates immediately, no confirmation.
- Edit service/plan asks for new name and updates immediately.
- Empty or duplicate names show clear error and keep same name-input step for retry or `0` cancel.

Delete service:

- Requires `CONFIRMAR` or `CONFIRM`, case-insensitive after trimming.
- If the service has plans, warn that it has plans.
- If the service has active subscriptions, warn that it has active subscriptions.
- Warning shows counts for active subscriptions, historical/non-active subscriptions, total affected subscriptions, and affected plans.
- Active subscriptions list paginates at 7/page, ordered by `expires_at` ascending.
- `8` advances to next warning page when available.
- `9` returns to previous screen inside delete warning context.
- `CONFIRMAR` or `CONFIRM` works from any warning page.
- Warning explicitly states historical/expired/cancelled subscriptions are deleted too, even if not listed.
- If the service has plans but zero subscriptions, still require confirmation and state that it has associated plans, no active subscriptions, no historical subscriptions, and that confirming deletes the service plus associated plans.
- On confirm, delete service, associated plans, and all associated subscriptions, active and historical/non-active.
- Success message includes deleted service name plus deleted plan/subscription summary when applicable.

Delete plan:

- Requires `CONFIRMAR` or `CONFIRM`, case-insensitive after trimming.
- If the plan has active subscriptions, show a strong warning.
- Warning shows counts for active subscriptions, historical/non-active subscriptions, and total affected subscriptions.
- Active subscriptions list paginates at 7/page, ordered by `expires_at` ascending.
- `CONFIRMAR` or `CONFIRM` works from any warning page.
- Warning explicitly states historical/expired/cancelled subscriptions are deleted too, even if not listed.
- If the plan has no active or historical subscriptions, still require confirmation and state that confirming deletes the plan only.
- On confirm, delete plan and all associated subscriptions, active and historical/non-active.
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
- Show target name, affected plan count for service deletion, active affected subscription count, historical/non-active affected subscription count, total affected subscription count, warning note, and active subscription rows.
- Paginate active rows at 10/page by re-fetching preview with requested page.
- Use frontend i18n pattern and correct singular/plural for displayed counts.
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
- singular/plural variants for plan and subscription counts
- delete warning, pagination, confirmation, zero-subscription cases, and cascade summary messages
- REST confirmation-required error where applicable

Frontend strings must follow existing frontend i18n store/catalog pattern for modal labels, warning text, confirm input, pagination, singular/plural count display, and errors.

Project docs under `/docs` must be updated for changed Catalog behavior, especially tenant dashboard and WhatsApp Tenant Console behavior. Update `docs/SUMMARY.md` when behavior, architecture, codebase overview, or flow docs change. README changes are only needed if setup/general usage changes.

## Testing plan

Focused backend tests must cover:

- Catalog menu with services.
- Catalog empty menu.
- Service list pagination at 7 items/page.
- Service row counts for plans and active subscriptions.
- Service detail hides ID.
- Create service direct flow.
- Duplicate service name keeps retry step.
- Edit service name post-success prompt.
- Delete service warning with plans only.
- Delete service warning with active and historical/non-active subscriptions.
- Delete service pagination and confirm from any warning page.
- Delete service cascade summary.
- Plan list pagination at 7 items/page.
- Plan row active subscription count.
- Plan detail hides ID.
- Empty plans path offers create plan for `Ver planes`.
- Delete plan with no plans returns to Catalog menu.
- Create plan direct flow.
- Duplicate plan name scoped to same service.
- Delete plan warning and cascade.
- Post-success `1` returns main menu.
- Post-success `0` closes session and preserves Evolution/n8n close contract at endpoint layer.

API tests must cover:

- Delete preview behavior for services and plans, including active, historical/non-active, total, plan count, ordered active rows, note, and pagination metadata.
- Delete without `confirm=true` fails.
- Confirmed delete behavior cascades in tenant scope.
- Duplicate validation behavior for service and plan names.
- Tenant scoping/RLS where applicable.

Frontend tests/build:

- Add/adjust Vitest coverage for delete preview modal if current frontend test setup supports component interaction.
- If frontend changes are made, inspect `frontend/package.json` first, then run existing frontend test/build commands.

Verification commands:

- `cd backend && uv run pytest`
- `cd frontend && npm test`
- `cd frontend && npm run build`

If a command cannot be run, final PR description must state exactly why.

## Acceptance checklist

- [ ] Tenant WhatsApp Catalog starts with a Catalog menu, not direct service selection.
- [ ] Empty Catalog shows reduced create-service menu.
- [ ] `0` closes the WhatsApp session throughout Catalog and respects the Evolution close contract where applicable.
- [ ] WhatsApp service lists are alphabetized and paginated at 7 items/page.
- [ ] Service rows show plan count and active subscription count.
- [ ] Singular/plural is correct for plan/subscription counts.
- [ ] Service detail hides ID and exposes edit name, view plans, create plan, delete plan.
- [ ] Delete service is only available from Catalog menu.
- [ ] WhatsApp plan lists are alphabetized and paginated at 7 items/page.
- [ ] Plan rows show active subscription count.
- [ ] Plan detail hides ID and exposes edit name and delete plan.
- [ ] Create service and create plan work directly after name input.
- [ ] Duplicate service/plan names show validated error and keep retry state.
- [ ] Delete service requires `CONFIRMAR` or `CONFIRM` and supports paginated active-subscription warnings.
- [ ] Delete plan requires `CONFIRMAR` or `CONFIRM` and supports paginated active-subscription warnings.
- [ ] Delete warnings show active, historical/non-active, and total subscription counts.
- [ ] Delete warnings state that historical/non-active subscriptions are also deleted.
- [ ] Confirmed service deletion cascades to plans and all related subscriptions.
- [ ] Confirmed plan deletion cascades to all related subscriptions.
- [ ] Post-success prompt offers `1` main menu and `0` cancel/close session.
- [ ] REST/dashboard deletion uses preview + confirmation in the style of existing endpoints.
- [ ] Dashboard preview paginates active subscriptions at 10 items/page.
- [ ] Existing dashboard Catalog UI is minimally extended if present; otherwise backend-only scope is documented.
- [ ] New user-facing WhatsApp strings are in ES and EN backend i18n catalogs.
- [ ] New frontend strings, if any, use the frontend i18n catalog pattern.
- [ ] Relevant docs under `/docs` are updated.
- [ ] Draft PR links GitHub issue `#43` and Linear `TPL-6`.
- [ ] Draft PR explains the chosen cascade strategy.
- [ ] Backend tests pass.
- [ ] Frontend tests/build pass if frontend changed.

## Do not

- Do not implement soft-delete or `is_active` for services/plans.
- Do not add unrelated refactors.
- Do not change navigation conventions outside the requested Catalog behavior.
- Do not hardcode a new REST routing convention if existing Catalog routes already establish one.
- Do not leave orphaned references after deleting services/plans.
- Do not skip i18n for user-facing text.
