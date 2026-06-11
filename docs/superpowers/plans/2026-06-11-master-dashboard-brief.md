# Design Brief: Master Dashboard Redesign

## 1. Feature Summary

Redesign the master dashboard from a monolithic 800-line component with generic metric cards into a refined operations surface. Overview stats first (compact, not dominating), business list as the main event, Code Services moved to a slide-out sidebar. Carries the calm-operator aesthetic from the login page into the authenticated experience. Includes dark mode audit and fixes for both login and dashboard — hardcoded colors, missing `dark:` variants, and contrast issues.

## 2. Primary User Action

Scan the health of the business portfolio at a glance, then manage individual businesses (edit, activate/deactivate, switch context, delete).

## 3. Design Direction

**Color strategy:** Restrained. Same token system as login. Dark surfaces when dark mode is active, clean porcelain when light. No decorative color — status badges carry the only hue (emerald/amber).

**Scene sentence:** A master operator opens the dashboard each morning — dark room, coffee, screen glow — to check which businesses are active, which need attention, and whether any code services are down. The page should feel like a calm control panel, not a marketing report.

**Anchor references:**
- **Linear sidebar + list** — compact overview, dense but readable list, slide-out detail panels
- **Vercel dashboard** — clean table hierarchy, restrained status indicators, no metric-card fluff

**Theme:** Follows global user preference (dark or light). No page-level override.

## 4. Scope

- **Fidelity:** Production-ready
- **Breadth:** One page (master dashboard) + sidebar panel for Code Services
- **Interactivity:** Full — table actions, create/edit dialog, delete confirmation, sidebar toggle, loading/empty/error states
- **Time intent:** Ship it

## 5. Layout Strategy

**Top: Compact status bar (not cards).**
A single horizontal strip with inline stats: "12 businesses · 10 active · 2 inactive". Text-based, not card-based. Uses muted-foreground for labels, bold foreground for numbers. Optionally a subtle divider below. This replaces the three summary cards — it's information, not decoration.

**Middle: Business table (the main event).**
Full-width table on desktop, card list on mobile. Same columns as current (name, prefix, email, phone, instance, status, actions) but with better visual hierarchy:
- Row hover with subtle background shift
- Status badge with dot indicator (not just color)
- Action buttons with tooltip labels, consistent sizing
- Empty state with illustration or icon, not just text

**Right: Code Services sidebar (slide-out).**
A sheet/drawer that slides in from the right when triggered by a button in the status bar or table header. Contains the Code Services toggle list with save button. This keeps the main view clean while making the configuration accessible.

**Bottom of status bar: Create Business button.**
Prominent but not loud. Outline or ghost variant, positioned in the status bar row (right-aligned). Not a floating action button.

## 6. Key States

| State | What the user sees |
|-------|-------------------|
| Default (data loaded) | Status bar with stats, full table, sidebar button |
| Loading | Status bar skeleton, table skeleton rows (3-4 rows) |
| Empty (no businesses) | Status bar at zero, centered empty state with icon + "Create your first business" CTA |
| Error loading | Status bar hidden, inline error alert with retry |
| Success action | Brief toast-style confirmation (not a persistent alert banner) |
| Sidebar open | Table pushes left or overlays, Code Services panel slides in from right |
| Delete confirmation | AlertDialog (keep current pattern) |
| Create/Edit | Dialog (keep current pattern, refine styling) |

## 7. Interaction Model

- **Status bar:** Read-only overview. Clickable stats could filter the table (future), but for now they're informational.
- **Table row hover:** Subtle background shift. Row is not clickable (actions are explicit buttons).
- **Action buttons:** Ghost variant, icon + tooltip. Edit opens dialog, Settings opens sidebar, Power toggles status (with confirmation for deactivate), Trash opens delete dialog (disabled when active).
- **Sidebar:** Triggered by a button (e.g., gear icon in the status bar area). Slides in from right. Closes on X, Escape, or clicking outside. Save button at bottom.
- **Create Business:** Button in the status bar row. Opens the same create dialog.
- **Toast notifications:** Replace persistent alert banners for success messages. Auto-dismiss after 3-4 seconds. Error messages stay until dismissed.

## 8. Content Requirements

- **Status bar:** "{n} businesses · {n} active · {n} inactive" — reactive to data
- **Empty state:** "No businesses yet" + "Create your first business to get started." + Create button
- **Table headers:** Business, Prefix, Email, Phone, Instance, Status, Actions
- **Sidebar title:** "Code Services" + description
- **Toast copy:** "Business created", "Business updated", "Business deactivated", "Business deleted", "Code services saved"
- **Error copy:** API error detail or generic fallback

## 9. Recommended References

- `layout.md` — for the status bar + table + sidebar spatial arrangement
- `animate.md` — for sidebar slide-in, toast enter/exit, row hover transitions
- `clarify.md` — for toast copy, empty state messaging, tooltip labels
- `polish.md` — for final quality pass after implementation

## 10. Dark Mode Integration (Login + Dashboard)

Both pages need dark mode fixes before the dashboard redesign ships. These are pre-requisites — the new layout inherits these tokens, so they must work in both themes.

### Issues found

| # | Page | Element | Problem |
|---|------|---------|----------|
| 1 | Dashboard | Code Services success alert | Hardcoded `bg-emerald-50 text-emerald-800` — no `dark:` variant. White-green flash on dark surface. |
| 2 | Dashboard | Mobile badges (active/inactive) | Hardcoded `bg-emerald-100 text-emerald-800` / `bg-amber-100 text-amber-800` — no `dark:` variant. |
| 3 | Dashboard | Code Services active badge | Same hardcoded emerald without dark variant. |
| 4 | Dashboard | Summary card icons | `text-emerald-600` / `text-amber-600` — low contrast on dark card background (`oklch(0.205)`). |
| 5 | Login | `select` element | Browser may inject white background in dark mode. Needs `dark:bg-transparent` or `appearance-none` with custom styling. |
| 6 | Login | Focus ring | Hardcoded `oklch(0.65 0.15 260/0.4)` — works on dark but should use semantic token for consistency. |

### Fix plan

**Dashboard:**
- Add `dark:bg-emerald-900 dark:text-emerald-300` to all emerald badges (active status, Code Services, mobile cards)
- Add `dark:bg-amber-900 dark:text-amber-300` to all amber badges (inactive status, mobile cards)
- Add `dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300` to Code Services success alert
- Replace hardcoded icon colors with semantic tokens or add dark variants: `dark:text-emerald-400`, `dark:text-amber-400`

**Login:**
- Add `dark:bg-transparent` to `select` element to prevent browser-injected white background
- Replace hardcoded focus ring with semantic token: `focus-visible:ring-ring` (already maps to `--ring` in both themes)

### Verification

After fixes, toggle dark/light on login page and verify:
- [ ] All badges visible with correct contrast in both themes
- [ ] Success/error alerts readable in both themes
- [ ] Select dropdown doesn't flash white in dark mode
- [ ] Focus rings visible on inputs and buttons in both themes
- [ ] Summary card numbers and labels readable in both themes
- [ ] No hardcoded `bg-emerald-*` or `bg-amber-*` without matching `dark:` variant

## 11. Open Questions

None — direction is locked. Compact status bar, full-width table, slide-out sidebar for Code Services, global theme, toast notifications. Dark mode fixes are pre-requisites.
