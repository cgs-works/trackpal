---
name: Trackpal
description: Dark-only command center for managing WhatsApp-based service delivery.
register: product
mode: dark-only
---

# Trackpal Design.md

## 1. Design North Star

Trackpal is a dark-only command center for operators who manage tenants, clients, subscriptions, services, plans, and mailbox connections. It must feel interactive, direct, and alive without becoming decorative.

The product should not feel like a generic admin template. It should feel like a focused operations console: compact, clear, responsive, and easy to trust.

Core principles:

- **Interactive by default:** if something can be clicked, opened, edited, selected, saved, or canceled, it must look and behave that way.
- **Context is visible:** users should always understand where they are, what row/item is selected, and what action is available.
- **No inline editing for core entities:** tables are for scanning, selecting, and launching actions. Creation and editing happen in dedicated dialogs.
- **Dark-only identity:** Trackpal does not ship a light UI. The app is designed around deep black surfaces and high-contrast shadcn primitives.
- **Functional personality:** cyan, green, red, and amber exist to communicate interaction and state, not decoration.

## 2. Visual Foundation

### Theme

Trackpal is **dark mode only**.

No light theme is required. Do not design dual-mode parity. All surfaces, controls, states, and empty/error/loading screens must be optimized for dark UI.

### Surface hierarchy

Use a deep black base with subtle zinc/neutral layers.

Recommended token intent:

| Token | Role | Direction |
|---|---|---|
| `background` | App base | near-black, around `#050505` |
| `surface` | Sidebar, cards, tables, dialogs | around `#09090b` |
| `surface-raised` | Inputs, row backgrounds, inner panels | around `#0f0f10` |
| `hover` | Hovered row/control background | around `#141416` |
| `selected` | Selected row/item background | around `#1c1c20` |
| `border` | Default borders | around `#18181b` |
| `border-strong` | Selected row / stronger separation | around `#2a2a30` |
| `foreground` | Main text | near zinc-100, not pure white when avoidable |
| `muted` | Secondary text | zinc-400/zinc-500 range |

### Accent color

The primary accent is **cyan**, used discreetly.

Use cyan for:

- active navigation item
- focus rings
- links
- focused/active contextual panels
- subtle interaction indicators

Do not use cyan for:

- selected table rows
- large decorative blocks
- default metric cards
- inactive states

### Semantic colors

State colors are separate from the cyan accent.

| Color | Meaning |
|---|---|
| Green | active, connected, completed, available |
| Red | inactive, disconnected, error, destructive, failed |
| Amber | pending, warning, expiring, attention required |
| Cyan | interaction, active navigation, focus, contextual inspector |

Semantic badges must be readable on dark backgrounds and use restrained tinted backgrounds with visible borders.

## 3. App Shell

### Desktop shell

Use a compact fixed sidebar layout.

- Sidebar on the left.
- Brand visible at the top: icon + `Trackpal`.
- Navigation items are compact and easy to scan.
- Active nav item uses cyan treatment.
- Main content area uses deep black background.
- Page content sits in dark surfaces with clear border separation.

The sidebar should make the product feel branded and intentional, but not bulky. Avoid large marketing-style headers inside the authenticated app.

### Mobile shell

Mobile must be fully functional.

- Sidebar becomes a drawer.
- Navigation remains complete.
- All role surfaces remain reachable.
- No “desktop only” actions for core workflows.

## 4. Page Layout

Use the **summary-first workspace layout** for primary pages.

Default page structure:

1. **Header**
   - title
   - short description
   - primary action on the right
2. **Summary metrics**
   - 3 or 4 compact blocks
   - useful context only
   - no oversized hero-metric pattern
3. **Filters / search**
   - separate compact bar
   - shadcn inputs/selects/buttons
4. **Table / list**
   - dense, readable, action-oriented
5. **Inspector**
   - appears when an item is selected
   - read-only by default
   - cyan border when active

This layout applies to pages such as Clients, Tenants, Subscriptions, Catalog, and other data-heavy workspaces.

## 5. Tables, Selection, and Row Actions

### Tables

Tables are for reading, scanning, selecting, and launching actions. They must not become inline forms.

Rows should have:

- strong enough height for comfortable scanning
- clear status badges
- visible row actions
- hover feedback
- selected state

### Selection

Selected rows use **deep gray**, not cyan.

- Hover: subtle gray, around `#141416`.
- Selected: stronger gray, around `#1c1c20`.
- Selected border: stronger neutral border, around `#2a2a30`.

Cyan is not used to fill selected rows.

### Inspector

When a row is selected, the inspector opens on the side.

- Inspector is read-only by default.
- Inspector uses a discrete cyan border to show it is the active contextual panel.
- Inspector has an `Edit` button that opens a dialog.
- Inspector should summarize the selected entity clearly without duplicating the whole table.

### Row actions

Use visible row actions by default.

Rules:

- Important actions should be visible, not hidden behind a dropdown.
- Use compact shadcn buttons.
- Prefer up to 3 visible actions per row.
- If more than 3 actions are required, allow a `More` action.
- Destructive actions use destructive styling and clear labels.

Examples:

- Tenants: `Edit`, `Deactivate/Activate`, `Delete`
- Clients: `Edit`, `Deactivate/Activate`, `Delete`
- Subscriptions: `Renew`, `Cancel`, `Reactivate` as applicable
- Catalog: `Edit`, `Delete`

## 6. Entity Interaction

### Creation and editing

Creating and editing important entities must happen in shadcn `Dialog` components.

Applies to:

- tenants
- clients
- services
- plans
- subscriptions
- mailbox configuration where appropriate
- profile/settings forms when used as entity edits

Do not use inline editing for these entities.

### Dialog style

Dialogs for create/edit flows should be **large and sectioned**.

A good dialog has:

- clear title
- short explanatory description
- grouped sections
- visible labels, not placeholder-only fields
- contextual help where it prevents errors
- inline validation
- footer actions

Footer rules:

- left/secondary action: `Cancel`
- right/primary action: `Create`, `Save`, or the exact operation
- loading state while saving
- errors shown inside the dialog, not only as global toast

## 7. Destructive Actions

Destructive actions require confirmation with impact summary.

Default destructive pattern:

1. Open confirm dialog.
2. Show entity name.
3. Explain what will change or be lost.
4. Show affected counts or related records when available.
5. Provide `Cancel` and destructive confirmation button.

For services and plans, use the stronger existing pattern:

- load delete preview
- show affected plans/subscriptions
- show affected active rows when available
- require typed confirmation (`CONFIRM` / `CONFIRMAR`)
- only enable delete after valid confirmation

Use typed confirmation for future high-risk destructive actions when the impact is broad or irreversible.

## 8. Login

Login uses a **single compact card**.

Structure:

- one centered card
- left side: Trackpal mark, short product message
- center: vertical divider
- right side: login form

Rules:

- no two-panel landing layout
- no large brand illustration panel
- no light surface
- compact, premium, direct
- shadcn inputs and buttons

The login should communicate identity without becoming a marketing page.

## 9. Mobile Behavior

Mobile must preserve full functionality.

Desktop patterns adapt as follows:

| Desktop | Mobile |
|---|---|
| Sidebar | Drawer |
| Table | Compact list/cards |
| Inspector side panel | Bottom sheet or detail screen |
| Large dialog | Fullscreen sheet/dialog when needed |
| Row actions | Visible compact actions per item |
| Summary metrics | Horizontal scroll or stacked compact blocks |

Mobile should not become read-only. Core actions remain available.

## 10. Component Rules

Trackpal uses shadcn primitives as the interaction foundation.

Use shadcn-style components for:

- buttons
- inputs
- selects
- textareas
- dialogs
- sheets
- dropdown menus when needed
- tabs
- badges
- tables
- separators
- switches
- checkboxes
- cards only when a real container is needed

Buttons must not be invented from scratch. Use shadcn button variants and sizes.

Cards are allowed, but avoid wrapping every section in identical cards. Use surfaces only when they create useful grouping.

## 11. Feedback and States

Every async action should provide visible feedback.

Required states:

- loading
- saving
- success
- error
- disabled
- empty
- selected
- hover
- focus

Loading should be local to the area when possible. Do not block the whole page unless the whole page truly depends on the request.

Empty states should teach the next action. Avoid generic “No data” copy.

## 12. Design Bans

Do not ship these patterns:

- light mode surfaces
- white app backgrounds
- generic admin-template look
- inline editing for tenants, clients, services, plans, subscriptions
- cyan-filled selected table rows
- custom non-shadcn buttons
- decorative gradients
- glassmorphism
- oversized hero metrics
- identical card grids with icon + heading + text everywhere
- modals used without clear title, context, and footer actions
- hidden critical actions when there is room to show them
- tables that become forms

## 13. Definition of Done for UI Work

A redesigned surface is not done unless:

- the user can identify the primary action immediately
- create/edit actions open dialogs
- destructive actions show confirmation and impact
- tables have hover and selected states
- inspectors use cyan border when active
- status colors follow the semantic rules
- mobile has complete functionality
- buttons and form controls use shadcn primitives
- loading, empty, success, and error states are designed
