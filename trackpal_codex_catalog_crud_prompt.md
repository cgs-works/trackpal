# Codex Implementation Prompt — TrackPal Catalog CRUD

## Repository

Work in:

`wilfredocamacho/trackpal`

Implement GitHub issue:

**#43 — [Feature]: Catalog CRUD for services and plans across WhatsApp and dashboard**  
https://github.com/wilfredocamacho/trackpal/issues/43

Also keep **Linear TPL-6** linked as the related product issue.

---

## Branch and PR Requirements

- Create/use branch: `feature/43-catalog-crud-whatsapp-dashboard`
- Base branch: `main`
- Use multiple logical commits, not one giant commit.
- Open a single **Draft PR**.
- Keep the PR as draft until human review.
- Link the Draft PR to:
  - GitHub issue `#43`
  - Linear issue `TPL-6`

The Draft PR description must be organized by phases/checklist:

- Backend service/repository/API
- WhatsApp Catalog flow + i18n
- Frontend dashboard, if applicable
- Tests
- Docs

Include test results in the PR description. If any command cannot be run, state exactly why.

---

## Before Coding

1. Read `AGENTS.md`.
2. Read `docs/SUMMARY.md`.
3. Inspect the existing:
   - Catalog REST endpoints
   - Dashboard Catalog UI, if any
   - Models and migrations
   - Service/repository patterns
   - WhatsApp Tenant Console flow
   - i18n catalogs
4. Do **not** assume endpoint shapes if the repo already has conventions.
5. Preserve existing style.
6. Make surgical changes only.
7. Do not refactor unrelated code.

---

## Goal

Expand Tenant Catalog from the current partial WhatsApp flow into a full CRUD module for tenant services and plans across:

- Tenant WhatsApp Console
- REST/dashboard, following existing backend/frontend conventions

---

## Product Rules

- Catalog means CRUD for services and plans.
- Services and plans do **not** get active/inactive status.
- All existing services count as active services.
- All existing plans count as active plans.
- “Active subscription” means exactly `status == "active"`.
- Do not additionally filter active subscriptions by expiration date.
- Service names are unique within a tenant.
- Plan names are unique within the same service, not globally across the tenant.
- Service list rows count all plans under the service.
- Service active subscription count is the sum of active subscriptions across all plans under that service.
- Plan rows count active subscriptions under that plan.
- Use correct singular/plural in WhatsApp and dashboard/frontend if touched.

Examples:

- `1 plan`
- `3 planes`
- `1 suscripción activa`
- `12 suscripciones activas`

---

## WhatsApp Catalog Main Menu

When the tenant has services:

```text
📦 *Catálogo*

1️⃣ Ver servicios
2️⃣ Crear servicio
3️⃣ Eliminar servicio
9️⃣ Volver al menú principal
0️⃣ Cancelar
```

When the tenant has no services:

```text
📦 *Catálogo*

📭 No hay servicios registrados.

1️⃣ Crear servicio
9️⃣ Volver al menú principal
0️⃣ Cancelar
```

Behavior:

- `0` closes the full WhatsApp session.
- `9` returns to the main menu.

---

## WhatsApp Navigation Rules

In all Catalog screens:

- `0` closes the full WhatsApp session.
- Respect the existing Evolution/n8n close contract wherever applicable:
  - `status="closed"`
  - `close_jid`
- `9` returns to the previous logical screen or main menu depending on context.
- Paginated Catalog lists use:
  - `8️⃣ Siguiente` to advance
  - `9️⃣ Regresar` to return to the previous screen
  - `0️⃣ Cancelar` to close/cancel according to the Catalog rule above
- Do not implement previous-page navigation with `9`; `9` means back, not previous page.
- `CONFIRMAR` or `CONFIRM` can be entered from any delete-warning page.

---

## Pagination

### WhatsApp

Maximum 7 items per page for:

- Services
- Plans
- Active subscriptions shown in delete warnings

### Dashboard / REST

Maximum 10 active subscription rows per page in delete previews.

---

## Ordering

- Services: alphabetical by name.
- Plans: alphabetical by name.
- Active subscriptions in delete warnings/previews: `expires_at ASC`, closest expiration first.

---

## WhatsApp Service List

Triggered from:

`Catálogo → 1️⃣ Ver servicios`

Rows must show:

```text
1️⃣ Netflix - 3 planes - 12 suscripciones activas
```

Rules:

- Paginate at max 7 items/page.
- Services must be alphabetized.
- Show plan count.
- Show active subscription count.
- Use correct singular/plural.
- Use i18n-compatible helpers/strings.
- Do not hardcode final user-facing strings outside i18n.

---

## WhatsApp Service Detail

Do **not** show service ID.

Format:

```text
📦 *Servicio*

*Nombre:* Netflix

*Acciones disponibles:*
1️⃣ Editar nombre
2️⃣ Ver planes
3️⃣ Crear plan
4️⃣ Eliminar plan
9️⃣ Volver
```

Rules:

- Delete service must only be available from the Catalog menu.
- Do not add delete service to service detail.

---

## WhatsApp Plan List

Triggered from:

`Service detail → 2️⃣ Ver planes`

Rows must show:

```text
1️⃣ Premium - 8 suscripciones activas
```

Rules:

- Paginate at max 7 items/page.
- Plans must be alphabetized.
- Show active subscription count.
- Use correct singular/plural.

If `Ver planes` is selected and the service has no plans, show:

```text
📭 Este servicio no tiene planes.

1️⃣ Crear plan
9️⃣ Volver
0️⃣ Cancelar
```

If `Eliminar plan` is selected and the service has no plans:

- Show a no-plans-for-delete message.
- Return to the Catalog menu.

---

## WhatsApp Plan Detail

Do **not** show plan ID.

Format:

```text
📄 *Plan*

*Nombre:* Premium

*Acciones disponibles:*
1️⃣ Editar nombre
2️⃣ Eliminar plan
9️⃣ Volver
```

---

## Create/Edit Behavior

### Create Service

- Ask for name.
- Create directly.
- No confirmation step.

### Create Plan

- Ask for name.
- Create directly.
- No confirmation step.

### Edit Service/Plan Name

- Ask for the new name.
- Apply directly after receiving it.

### Empty Names

- Show validation error.
- Remain in the same input step.

### Duplicate Names

- Show a clear validated error.
- Keep the WhatsApp flow in the same name-input step so the user can retry or send `0` to cancel.
- REST/dashboard must also return/show validated duplicate-name errors.

---

## Post-Success WhatsApp Behavior

After any successful create/edit/delete mutation for service or plan, show:

1. Specific success message.
2. Then:

```text
1️⃣ Volver al menú principal
0️⃣ Cancelar
```

Behavior:

- `1` clears the flow and shows the main menu.
- `0` clears the session and closes the WhatsApp session.

---

## Delete Service Behavior

Deleting a service always requires confirmation via:

- `CONFIRMAR`
- `CONFIRM`

Before confirmation:

- If the service has plans, warn that it has plans.
- If the service has active subscriptions, warn that it has active subscriptions.
- Show active subscriptions associated to the service, paginated at max 7 items/page in WhatsApp.
- Explicitly state that historical/expired/cancelled subscriptions associated with the service will also be deleted, even if they are not listed.
- Show counts:
  - Active subscriptions
  - Historical/non-active subscriptions
  - Total affected subscriptions
  - Affected plans

Active subscription row format:

```text
streaming@email.com - Cliente Demo - 584241234567 - Netflix/Premium - expira 2026-07-15
```

Confirmation:

- `CONFIRMAR` or `CONFIRM` can happen from any warning page.

On confirm, delete in cascade:

- Service
- Associated plans
- All associated subscriptions, active and historical/non-active

Codex must inspect current models/constraints and choose the minimum safe cascade strategy:

- Service-layer explicit cascade
- DB-level cascade
- Or a combination

Requirements:

- Preserve referential integrity.
- If migrations/foreign keys/model changes are necessary, implement Alembic migrations.
- Do not make schema changes if the existing model can safely support this in service/repository code.
- Explain the cascade strategy in the PR description.

---

## Delete Service Warning — Plans but Zero Subscriptions

General format:

```text
⚠️ *Eliminar servicio*

El servicio *Netflix* tiene 3 planes asociados.
No tiene suscripciones activas asociadas.
No tiene suscripciones históricas asociadas.

Si confirmas, se eliminarán:
- El servicio
- 3 planes asociados

Escribe *CONFIRMAR* para eliminar o *0* para cancelar.
```

---

## Delete Service Success

Include summary when applicable:

```text
✅ Servicio *Netflix* eliminado exitosamente.

También se eliminaron:
- 3 planes
- 12 suscripciones asociadas
```

---

## Delete Plan Behavior

Deleting a plan always requires confirmation via:

- `CONFIRMAR`
- `CONFIRM`

Before confirmation:

- If the plan has active subscriptions, show a strong warning.
- Show active subscriptions associated to the plan, paginated at max 7 items/page in WhatsApp.
- Explicitly state that historical/expired/cancelled subscriptions associated with the plan will also be deleted, even if they are not listed.
- Show counts:
  - Active subscriptions
  - Historical/non-active subscriptions
  - Total affected subscriptions

Confirmation:

- `CONFIRMAR` or `CONFIRM` can happen from any warning page.

On confirm, delete in cascade:

- Plan
- All associated subscriptions, active and historical/non-active

---

## Delete Plan Warning — No Subscriptions

If a plan has no active or historical subscriptions, confirmation format should generally be:

```text
⚠️ *Eliminar plan*

El plan *Premium* no tiene suscripciones asociadas.

Si confirmas, se eliminará:
- El plan

Escribe *CONFIRMAR* para eliminar o *0* para cancelar.
```

---

## Delete Plan Success

Include summary when applicable.

---

## REST / Dashboard Behavior

Scope includes REST/backend and dashboard review.

Rules:

- Inspect current REST Catalog route conventions.
- Keep route naming/style coherent.
- Deletion must use a preview + confirmation pattern.
- Do not invent a parallel route convention if one already exists.
- Dashboard delete preview must show max 10 active subscription rows per page.

REST/dashboard preview must include:

- Target service/plan name
- Affected plan count when deleting a service
- Active affected subscription count
- Historical/non-active affected subscription count
- Total affected subscription count
- Paginated active subscription list
- Explicit note that historical/expired/cancelled subscriptions are also deleted even if not listed

Dashboard confirmation UI:

- Reuse the project’s existing modal/confirmation pattern.
- If none exists, implement the minimum coherent confirmation pattern.

Frontend/dashboard:

- Inspect current UI.
- If a Catalog UI exists, minimally extend it.
- If no clear Catalog UI exists, implement backend REST only and document the UI gap.
- If frontend is touched, use the frontend i18n pattern and correct singular/plural.

---

## Backend Implementation Notes

Existing `CatalogService` already has create/update methods; extend only as needed.

Update consistently:

- Service layer
- Repository layer
- Protocols
- Fakes
- Tests
- REST schemas/routes
- WhatsApp Tenant Console handlers
- i18n catalogs

The WhatsApp Tenant Console currently has modular files such as:

- constants
- mixin
- router
- assignments
- service
- catalog flow
- formatters
- i18n catalogs

Match existing style.

Rules:

- Tenant WhatsApp strings must be backend i18n strings in both Spanish and English catalogs.
- Avoid hardcoded user-facing WhatsApp strings except where the existing code already has an established pattern and changing it would be out of scope.
- Preserve tenant scoping and RLS behavior.
- Do not infer tenant scope from arbitrary payload IDs.
- Be careful with `DATA_ENCRYPTION_KEY` and app import timing in tests.

---

## Docs

Documentation of behavior belongs under `/docs`.

Requirements:

- Update docs under `/docs`.
- Update `docs/SUMMARY.md` when behavior, architecture, codebase overview, or flow docs change.
- Update README only if setup/general usage changes.
- Do not create docs outside `/docs`.

---

## Tests and Verification

Add focused backend tests for:

- Catalog menu with services.
- Catalog empty menu.
- Service list pagination at 7 items/page.
- Service row counts for plans and active subscriptions.
- Service detail hides ID.
- Create service direct flow.
- Duplicate service name keeps retry step.
- Edit service name post-success prompt.
- Delete service warning with plans only.
- Delete service warning with active + historical subscriptions.
- Delete service pagination and confirm from any warning page.
- Delete service cascade summary.
- Plan list pagination at 7 items/page.
- Plan row active subscription count.
- Plan detail hides ID.
- Empty plans path offers create plan for “Ver planes”.
- Delete plan with no plans returns to Catalog menu.
- Create plan direct flow.
- Duplicate plan name scoped to same service.
- Delete plan warning/cascade.
- Post-success `1` returns main menu.
- Post-success `0` closes session.

Add/adjust API tests for:

- Delete preview behavior.
- Confirmed delete behavior.
- Duplicate validation behavior.
- Tenant scoping/RLS where applicable.

Add frontend tests if frontend is changed.

Run:

```bash
cd backend && uv run pytest
```

If frontend changes are made, inspect `package.json` first, then run the existing frontend test/build commands. Likely:

```bash
cd frontend && npm test
cd frontend && npm run build
```

If a command cannot be run, state exactly why in the Draft PR description.

---

## Acceptance Criteria

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

---

## Do Not

- Do not implement soft-delete or `is_active` for services/plans.
- Do not add unrelated refactors.
- Do not change navigation conventions outside the requested Catalog behavior.
- Do not hardcode a new REST routing convention if existing Catalog routes already establish one.
- Do not leave orphaned references after deleting services/plans.
- Do not skip i18n for user-facing text.
