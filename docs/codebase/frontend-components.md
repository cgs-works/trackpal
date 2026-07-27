# Frontend Components

React 19 components using TypeScript, shadcn/ui (Radix), and Tailwind CSS. Organized by feature module.

## Admin Feature Components

### SettingsPage (`features/admin/components/settings-page.tsx`)

`SettingsPage` renders tenant settings as a flat category list plus a single active detail panel. No category opens by default; the panel shows a guide message until the user selects a category. Desktop uses a lateral category menu, mobile uses a `Sheet` category picker, long sections scroll inside the detail panel, and the common Cancelar action closes the active section so unsaved local edits are discarded by unmounting the section component.

**The first category is My Account**, replacing the old separate Profile and Password entries. It uses role-aware horizontal tabs.

| Section | Component | Data Source |
|---------|-----------|-------------|
| My Account | `MyAccountSection` (tabs) | Profile + Export APIs |
| Reminder Settings | `ReminderSettingsSection` (inline panel) | `settingsStore.reminderSettings` |
| Language | `LocaleSection` | `settingsStore.tenantSettings` |
| Timezone | `TimezoneSection` | `settingsStore.tenantSettings` + `timezoneOptions` |
| Code Services | `CodeServicesSection` | API direct |
| Code Mailbox | `MailboxSection` | `settingsStore.mailbox` |
| Public API Catalog | `PublicApiSection` | Public API Key management API |
| WhatsApp | `WhatsappLinkSection` | Status polling, pairing code, or QR code |
| Control de acceso | `AccessControlSection` | API direct |
| Profile | `ProfileSection` (inside My Account) | `getProfile()` API |
| Password | `PasswordSection` (inside My Account Security tab) | API direct |

### MyAccountSection (`features/admin/components/my-account-section.tsx`)

Role-aware horizontal tabs inside Settings. Renders different content based on role and context:

| Tab | Tenant Admin | Master Support Context |
|-----|-------------|------------------------|
| Profile | `ProfileSection` — identity fields | `ProfileSection` with `updateTenantProfile()` targeting selected business |
| Security | `PasswordSection` — password change | Not rendered |
| Data | `DataTabContent` — export status/actions + deletion danger zone | `DataTabContent` — export status/actions only (no danger zone) |

### DataTabContent (`features/admin/components/data-tab-content.tsx`)

Data tab for Tenant Data Export and self-service Tenant Deletion. Connected to `useExportStore` for state management.

**Export section:**
- Production empty state with description and "Request export" button (triggers password dialog)
- Demo Accounts keep export and self-deletion discoverable but render both actions disabled and never call their APIs
- Status display: pending, processing (with spinner), ready (with download button), failed (with retry option), cancelled
- Previous version download while replacement is pending
- Actor attribution: localized "You" / "Support" label
- Cooldown countdown, expiry countdown
- Cancel button for pending/processing jobs
- Login to download (or navigate to Data tab)

**Danger zone (Tenant Admin only):**
- Description of irreversible deletion scope
- "Delete account permanently" button opens confirmation dialog
- Dialog requires current password + locale-aware destructive word (ELIMINAR/DELETE)
- Loading state, error display, successful redirect to login
- Master Support Context replaces danger zone with guidance to Master Dashboard

### ProfileSection (`features/admin/components/profile-section.tsx`)

Identity fields only (name, email, phone). Locale and timezone removed — now in dedicated sections.

- Loads profile via `getProfile()` on mount
- Saves via `updateProfile()` (identity only)
- No locale/timezone fields

### LocaleSection (`features/admin/components/locale-section.tsx`)

Standalone locale selector with save button.

- Reads `tenantSettings.locale` from `settingsStore`
- Dropdown with `en`/`es` options
- Saves via `updateTenantSettings({ locale })`
- On locale change, calls `loadCatalog()` for immediate UI update

### TimezoneSection (`features/admin/components/timezone-section.tsx`)

Standalone timezone picker with save button.

- Reads `tenantSettings.timezone` from `settingsStore`
- Uses `TimezonePicker` component (portal-based dropdown)
- Saves via `updateTenantSettings({ timezone })`

### TimezonePicker (`features/admin/components/timezone-picker.tsx`)

Searchable timezone dropdown using `createPortal` to escape parent overflow containers.

- Renders dropdown in `document.body` via portal
- Search input filters by timezone label and IANA name
- Quick UTC button at bottom
- Positioned relative to trigger button using `getBoundingClientRect()`
- Closes on click outside (checks both trigger and portal element)

### ReminderSettingsSection (`features/admin/components/reminder-settings-section.tsx`)

Inline panel for reminder configuration (warning days, reminder time, recipient mode, enabled toggle, custom messages).

- Timezone displayed as read-only (edited via TimezoneSection)
- Loads via `loadReminderSettings()` + `loadTenantSettings()` on mount
- Saves via `updateReminderSettings()`
- Resets local state via `useEffect` when `reminderSettingsLoaded` changes
- Shows template preview for custom messages using placeholder values

### MailboxSection (`features/admin/components/mailbox-section.tsx`)

IMAP/OAuth mailbox configuration.

- Cached in `settingsStore.mailbox`
- Provider selection: Google, Microsoft, IMAP custom
- OAuth flow: opens provider auth URL in popup
- IMAP form: host, port, SSL toggle, password
- Test connection, disconnect actions
- After mutations: `clearSettingsCache()` + reload

### PublicApiSection (`features/admin/components/public-api-section.tsx`)

Pro-only Settings section for Public API Catalog configuration. It shows the visible Public API Key, allows editing exact Allowed Origins, regenerates the key while preserving origins, and revokes the public API configuration.

### WhatsappLinkSection (`features/admin/components/whatsapp-link-section.tsx`)

Settings section for managing WhatsApp connection (status badge, pairing code, QR scanning, and disconnect). Available for both Starter and Pro tenant admins, and master support context. Uses the `useWhatsAppLinkPolling` hook to fetch status every 5 seconds. Demo Accounts render a fixed connected simulated state and an accessible link to the Demo WhatsApp Simulator without provider controls.

### AccessControlSection (`features/admin/components/access-control-section.tsx`)

Lists active WhatsApp access blocks, blocks a phone, and unblocks existing entries through `/access-control/blocks`. This affects bot/code interactions only, not client portal accounts. Phone Search filters the already-loaded collection by partial phone digits, excludes LID-only identities while a query is active, and paginates matching results locally in groups of 10.

### PlanRouteGate (`features/admin/components/plan-route-gate.tsx`)

Wraps Pro-only route components. Checks `tenantPlan` + `isMasterSupportContext` from auth store. If Starter tenant admin without Master support context, renders `NotFoundPage` instead of children.

### SupportBanner (`features/admin/components/support-banner.tsx`)

Alert banner shown above content when Master is in support context on a Starter tenant. Informs the Master user they are viewing the full Pro surface in a Starter tenant.

### NotFoundPage (`features/admin/components/not-found-page.tsx`)

Simple 404 card with a link back to the admin dashboard. Used by `PlanRouteGate` when a Starter tenant admin accesses a Pro-only route.

### DashboardPage (`features/admin/components/dashboard-page.tsx`)

Tenant dashboard with plan-aware metrics. Displays:
- Plan badge (Starter/Pro)
- Common metrics: Mailbox status, enabled code services, access control count
- Pro-only metrics: active clients, catalog services, active subscriptions, expiring soon
- Corrects `tenantPlan` in authStore from API response if it differs

### ClientsPage (`features/admin/components/clients-page.tsx`)

Client management with search, CRUD, and status toggle.

- Cached in `catalogStore.clients`
- Search filters client-side (no API call)
- After mutations: `invalidateClients()` + reload
- Links to subscriptions per client (`?client_id=`)

### CatalogPage (`features/admin/components/catalog-page.tsx`)

Service + plan CRUD with sidebar/panel layout.

- Cached in `catalogStore.services` + `catalogStore.plans`
- Services sidebar: create, rename, delete with preview
- Plans panel: create, rename, delete with preview
- After mutations: `invalidateServices()` or `invalidatePlans(id)` + reload
- Delete preview shows affected subscriptions count

### SubscriptionsPage (`features/admin/components/subscriptions-page.tsx`)

Full subscription management with filters and modals.

- Subscriptions NOT cached (frequent changes, filter-dependent)
- Dropdown data (clients, services) cached via `catalogStore`
- Filters: status, client, service
- Actions: create, edit, renew, reactivate, cancel, reveal credentials

### SubscriptionTable (`features/admin/components/subscription-table.tsx`)

Table component for subscription list display.

- Columns: client, service, email, profile, duration, dates, status, actions
- Reveal credentials eye icon per row
- Status badges with color coding

## Demo Feature Components

### Demo shell and lifecycle (`features/demo/components/`)

| Component | Responsibility |
|-----------|----------------|
| `DemoBanner` | Persistent plan, browser-local storage, countdown, connectivity, recovery, and Reset Demo Data status/action |
| `DemoCountdown` | Server-offset remaining-time display without noisy live-region announcements |
| `DemoOverlay` | Accessible interaction pause after two unverifiable lifecycle heartbeats, with explicit retry |
| `DemoEndedPage` | Public bilingual neutral end state with WhatsApp, Telegram, and email contact paths |
| `DemoWhatsappSimulator` | Plan-aware contained simulator: Starter Request flow; Pro Request and Operation modes |
| `ClientConsoleExperience` | Read-only Client menu simulation from current Pro workspace data |
| `TenantAdminConsoleExperience` | Pro Tenant Admin console navigation and local mutations |
| `SubscriptionConsoleExperience` | Pro subscription lifecycle simulation backed by the shared workspace repository |
| `TenantUtilityConsoleExperience` | Pro profile, access-control, Help, and code-service console flows |

`useDemoHeartbeat` performs minute/focus/visibility lifecycle checks and pauses fail-closed without deleting local work. `useCountdown` derives display time from server time, and `usePrefersReducedMotion` removes non-essential simulator delays while preserving state transitions. Chat state remains component-local; business mutations use the same Demo Workspace adapter as the Web pages.

## Master Feature Components

### MasterDashboard (`features/master/components/dashboard-page.tsx`)

Master admin dashboard with tenant management.

- Summary cards: total, active, inactive counts
- Business table with CRUD
- Code services dialog for global activation
- Tenant support context switch
- Plan selector in business form dialog
- Separate Production and Demos tabs; production summary cards exclude Demo Tenants

### Demo management (`features/master/components/demos-tab.tsx`)

`DemosTab` owns lifecycle-only search, filtering, creation, credential replacement, and deletion. `DemoTable` renders desktop rows and mobile cards with Pending/Active/Expired status; `DemoFormDialog` accepts immutable name and plan with Starter preselected; `DemoCredentialsDialog` reveals generated credentials once and provides separate copy actions. No component exposes workspace preview, support switch, telemetry, plan changes, or extension controls.

### BusinessTable (`features/master/components/business-table.tsx`)

Tenant list table with actions (edit, activate/deactivate, delete, manage catalog). Shows plan badge per tenant.

### BusinessFormDialog (`features/master/components/business-form-dialog.tsx`)

Create/edit tenant form dialog. Includes plan selector (Starter/Pro).

### CodeServicesDialog (`features/master/components/code-services-dialog.tsx`)

Global code-service activation toggles for master.

## Client Feature Components

### ClientDashboard (`features/client/components/dashboard-page.tsx`)

Read-only client dashboard showing subscription info and profile.

### ProfilePage (`features/client/components/profile-page.tsx`)

Client profile view with password change.

## Shared UI Components

### shadcn/ui (`components/ui/`)

Radix-based primitives generated via shadcn CLI:

| Component | Purpose |
|-----------|---------|
| `alert.tsx` | Alert banners |
| `alert-dialog.tsx` | Confirmation dialogs |
| `badge.tsx` | Status badges |
| `button.tsx` | Button with variants (default, outline, ghost, destructive) |
| `card.tsx` | Card container with header/content |
| `dialog.tsx` | Modal dialog |
| `dropdown-menu.tsx` | Dropdown menus |
| `input.tsx` | Text input |
| `label.tsx` | Form labels |
| `select.tsx` | Select dropdown |
| `separator.tsx` | Visual separator |
| `sheet.tsx` | Slide-out panel (mobile sidebar) |
| `skeleton.tsx` | Loading skeleton |
| `sonner.tsx` | Toast notification provider |
| `switch.tsx` | Toggle switch |
| `table.tsx` | Data table |

### Layout Components (`components/layout/`)

| Component | Purpose |
|-----------|---------|
| `app-sidebar.tsx` | Reusable sidebar with collapse, mobile sheet variant |
| `sidebar-nav.tsx` | Individual nav item with icon + label |

## Patterns

- **Styling**: Tailwind CSS classes, `cn()` utility for conditional classes
- **Icons**: Lucide React (`lucide-react`)
- **Toasts**: `toast.success()` / `toast.error()` from Sonner
- **Forms**: Controlled inputs with `useState`, form submission via `onSubmit`
- **API calls**: Direct Axios via `@/lib/api` or store actions
- **Error handling**: try/catch with `err.response?.data?.detail` extraction
- **Loading states**: Boolean state flags, skeleton/spinner UI
