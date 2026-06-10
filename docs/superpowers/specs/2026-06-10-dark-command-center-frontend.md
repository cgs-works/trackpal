# Dark Command Center Frontend Redesign Spec

## Status

Approved for implementation.

This spec supersedes the previous frontend redesign direction. The prior Raycast-like / light-dark parity direction is rejected and must not guide implementation.

## Source of Truth

Primary design source:

- `DESIGN.md`

Implementation must preserve existing Trackpal business behavior while replacing the frontend presentation and interaction model.

## Problem

The previous frontend direction failed because it felt generic, lifeless, colorless, confusing, and insufficiently interactive. Several workflows also felt broken or non-obvious: buttons did not feel responsive, modals did not reliably open, and important entity edits were inline instead of clearly contained in dialogs.

Trackpal needs a frontend that feels like a dark operational command center, not a generic admin template.

## Goals

1. Make Trackpal dark-only with no white application surfaces.
2. Make the UI feel interactive, intentional, and operational.
3. Keep all current backend contracts, auth logic, Pinia stores, route protections, support-mode behavior, and API flows intact.
4. Replace inline entity editing with shadcn dialogs for create/edit flows.
5. Use summary-first pages for primary data workspaces.
6. Add selection and read-only contextual inspection for data-heavy pages.
7. Keep important row actions visible instead of hiding them behind menus by default.
8. Preserve the existing high-risk workflows:
   - master support-mode route behavior
   - mailbox OAuth handling and 404 empty-state behavior
   - subscription route-query filter hydration
   - subscription reminder settings modal visibility
   - credential reveal in subscription rows
   - service/plan delete preview with typed confirmation
9. Make mobile fully functional, not read-only.
10. Update frontend documentation after implementation.

## Non-Goals

1. Do not redesign backend APIs.
2. Do not change database schema.
3. Do not change authentication token semantics.
4. Do not replace Vue, Pinia, vue-router, Tailwind CSS v4, or shadcn-vue.
5. Do not introduce TypeScript.
6. Do not rewrite business logic when only presentation changes are needed.
7. Do not create a light theme.
8. Do not keep a theme toggle that implies light mode support.
9. Do not implement inline editing for tenants, clients, services, plans, or subscriptions.

## Design Requirements

### Visual System

The frontend must use the dark-only visual system described in `DESIGN.md`.

Required visual rules:

- App base uses deep black, near `#050505`.
- Primary surfaces use near-black/zinc layers around `#09090b` and `#0f0f10`.
- Borders are subtle neutral zinc borders.
- Selected rows/items use deep gray, not cyan.
- Cyan is reserved for active navigation, focus rings, links, and active contextual inspector borders.
- Green means active/connected/completed.
- Red means inactive/disconnected/error/destructive.
- Amber means pending/warning/attention.
- White backgrounds are forbidden.
- Decorative gradients and glassmorphism are forbidden.

### shadcn Primitive Usage

All primary controls must use existing shadcn-vue primitives from `frontend/src/components/ui/`.

Required primitives for this redesign:

- `Button`
- `Input`
- `Textarea`
- `Select`
- `Dialog`
- `Sheet`
- `Badge`
- `Table`
- `Separator`
- `Switch`
- `Checkbox`
- `Card` only where a true grouped surface is needed

Raw custom buttons are not acceptable for new or migrated UI.

### Dark-Only Theme

The app must stop presenting theme switching as a user-facing feature.

Required behavior:

- Trackpal always renders dark UI.
- Remove or disable the light-mode toggle from the authenticated shell and login screen.
- `document.documentElement` should be in dark mode for the app.
- CSS variables should describe a dark-only theme.
- Documentation should no longer describe light/dark parity as the frontend design approach.

### App Shell

Authenticated pages use a compact sidebar shell.

Desktop requirements:

- Left sidebar stays compact.
- Brand icon and `Trackpal` label are visible at the top.
- Active route uses cyan treatment.
- Sidebar surfaces are dark-only.
- Main content background is deep black.
- User and logout controls remain available.
- Master support mode remains visible and escapable.

Mobile requirements:

- Sidebar becomes a drawer/sheet.
- Full navigation remains available.
- Support mode exit remains available.
- No core workflow becomes desktop-only.

### Page Layout

Primary data pages must use the summary-first workspace pattern.

Required order:

1. Page header with title, short description, and primary action.
2. Summary metrics row with 3 or 4 compact metrics when useful data exists.
3. Filter/search bar when the page supports filtering.
4. Data table on desktop or compact list/cards on mobile.
5. Contextual inspector when a row/item is selected.

Applies to:

- master tenants
- tenant clients
- tenant catalog
- tenant subscriptions
- mailbox where applicable
- code services where applicable
- client overview where applicable

### Tables and Selection

Tables must be interactive and readable.

Requirements:

- Rows have hover feedback.
- Rows can be selected when an inspector is available.
- Selected rows use deep gray background and stronger neutral border.
- Row action clicks must not accidentally trigger row selection.
- Empty states must guide the next action.
- Loading states must be local and visible.

### Row Actions

Row actions are visible by default.

Requirements:

- Use compact shadcn buttons.
- Show important actions directly in the row.
- Prefer maximum 3 visible actions.
- If more than 3 actions are needed, expose the rest through `More`.
- Destructive actions use destructive styling.
- Actions must have clear labels.

### Contextual Inspector

The contextual inspector is a read-only detail panel for the selected entity.

Requirements:

- Opens when a row/item is selected.
- Uses cyan border when active.
- Shows key fields and status.
- Provides an `Edit` action when editing is allowed.
- `Edit` opens the corresponding create/edit dialog.
- Does not replace create/edit dialogs.
- On mobile, inspector becomes a bottom sheet or detail sheet.

### Create/Edit Dialogs

Creating and editing core entities must happen in large, sectioned shadcn dialogs.

Applies to:

- tenants
- clients
- services
- plans
- subscriptions
- relevant mailbox/settings forms when presented as entity edits

Requirements:

- Use shadcn `Dialog`.
- Use visible labels.
- Split complex forms into sections.
- Include helpful descriptions where they prevent mistakes.
- Include inline validation or inline error messages.
- Footer contains `Cancel` and primary action.
- Saving/loading state is visible.
- Closing a dialog resets stale form state.

### Destructive Actions

Default destructive actions use confirmation with impact summary.

Requirements:

- Dialog states what will change or be lost.
- Dialog names the target entity.
- Dialog shows affected counts or related records when available.
- Dialog has `Cancel` and destructive confirmation actions.

Special rule for services and plans:

- Preserve delete preview API calls.
- Preserve affected plan/subscription counts.
- Preserve active subscription preview rows.
- Preserve pagination where present.
- Preserve typed confirmation with `CONFIRM` / `CONFIRMAR`.
- Preserve delete request `?confirm=true` contract.

### Login

Login must use the approved compact single-card layout.

Requirements:

- One centered compact card.
- Left side: Trackpal mark and short product message.
- Middle: vertical divider.
- Right side: login form.
- No two-panel landing composition.
- No large decorative brand panel.
- No light surface.
- Use shadcn inputs and buttons.
- Preserve public i18n and role-based redirect behavior.

### Mobile

Mobile must be fully functional.

Requirements:

- Sidebar becomes a drawer.
- Tables become compact lists/cards.
- Inspector becomes bottom sheet or detail sheet.
- Large dialogs adapt to mobile sheet/fullscreen behavior when needed.
- Row/item actions remain available.
- Summary metrics stack or scroll horizontally.

## Functional Preservation Requirements

Implementation must not regress these behaviors:

### Auth and Routing

- `/login` remains public.
- Authenticated users redirect away from `/login`.
- Master users route to `/master/overview`.
- Tenant users route to `/admin/overview`.
- Client users route to `/client/overview`.
- Legacy dashboard redirects remain intact.
- Master support mode remains based on `activeTenantId` and `allowMasterSupport` route meta.
- `/admin/settings` remains blocked in master support mode.

### Master Tenant Management

- Master can create tenants.
- Master can edit tenants.
- Master can activate/deactivate tenants.
- Master can delete inactive tenants with confirmation.
- Master can switch into tenant support context.
- Master can exit tenant support context.

### Tenant Clients

- Tenant can create clients.
- Tenant can edit clients.
- Tenant can activate/deactivate clients.
- Tenant can delete clients with confirmation.
- Client-to-subscriptions navigation must preserve client filtering.

### Catalog

- Tenant can create/edit/delete services.
- Tenant can create/edit/delete plans.
- Service/plan delete preview remains intact.
- Typed confirmation remains intact.
- Existing backend delete contracts remain intact.

### Subscriptions

- Tenant can create/edit subscriptions.
- Tenant can renew subscriptions.
- Tenant can cancel subscriptions.
- Tenant can reactivate subscriptions.
- Filters remain hydrated from route query.
- Filter interactions do not drop initial `client_id` query state.
- Credential reveal remains available per row.
- Reminder settings modal opens and renders.

### Mailbox

- Tenant mailbox page loads mailbox configuration.
- Missing mailbox config / 404 is treated as empty configuration, not a fatal error.
- OAuth success/failure query feedback remains visible.
- Save/test/connect/disconnect flows remain available.

### Code Services

- Master global code-service toggles remain available.
- Tenant code-service selection remains available.
- Loading/error/success states remain visible.

### Client Portal

- Client overview remains available.
- Client can view their profile/subscriptions.
- Client can change password.

## Testing Requirements

Every implementation phase must update or add tests before changing implementation.

Required test coverage:

- dark-only theme behavior
- absence of theme toggle in app shell/login
- login single-card layout and role redirects
- sidebar navigation and mobile drawer
- selected row opens inspector
- row action click does not select row accidentally
- create/edit actions open dialogs
- destructive confirmation renders impact summary
- services/plans keep typed confirmation
- subscription filters hydrate from route query
- reminder settings modal opens with `isOpen`
- mailbox 404 empty state remains non-fatal
- mobile layout exposes navigation and actions

## Documentation Requirements

After implementation, update frontend docs:

- `docs/architecture/frontend-architecture.md`
- `docs/codebase/frontend-structure.md`
- `docs/code-standard/frontend-conventions.md`

Documentation must describe the dark-only command center direction and remove light/dark parity language.

## Acceptance Criteria

The redesign is complete when:

1. `DESIGN.md` and this spec agree.
2. No frontend spec for the rejected previous design remains.
3. Frontend UI is dark-only with no white application surfaces.
4. Theme toggle is removed from user-facing UI.
5. Primary pages follow summary-first layout.
6. Tables/lists are selectable where inspectors exist.
7. Inspectors render with cyan active border.
8. Create/edit flows use large sectioned dialogs.
9. Row actions are visible by default.
10. Destructive actions show impact confirmation.
11. Service/plan delete preview typed confirmation still works.
12. High-risk existing behaviors listed above are covered by tests.
13. `cd frontend && npm test` passes.
14. `cd frontend && npm run build` passes.
15. Relevant frontend docs are updated.
