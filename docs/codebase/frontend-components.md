# Frontend Components

React 19 components using TypeScript, shadcn/ui (Radix), and Tailwind CSS. Organized by feature module.

## Admin Feature Components

### SettingsPage (`features/admin/components/settings-page.tsx`)

Settings hub with expandable card sections. Uses `useSettingsStore` and `useCatalogStore` for cached data. Plan-aware: Starter shows Profile, Language, Code Services, Code Mailbox, Control de acceso, and Password. Pro adds Reminder Settings, Timezone, and planned Public API Key management. Master support context shows the full Pro settings set even for Starter tenants.

| Section | Component | Data Source |
|---------|-----------|-------------|
| Reminder Settings | `ReminderSettingsModal` (dialog) | `settingsStore.reminderSettings` |
| Language | `LocaleSection` | `settingsStore.tenantSettings` |
| Timezone | `TimezoneSection` | `settingsStore.tenantSettings` + `timezoneOptions` |
| Code Services | `CodeServicesSection` | API direct |
| Code Mailbox | `MailboxSection` | `settingsStore.mailbox` |
| Public API Catalog (planned) | `PublicApiSection` | Public API Key management API |
| Control de acceso | `AccessControlSection` | API direct |
| Profile | `ProfileSection` | `getProfile()` API |
| Password | `PasswordSection` | API direct |

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

### ReminderSettingsModal (`features/admin/components/reminder-settings-modal.tsx`)

Dialog for reminder configuration (warning days, reminder time, recipient mode, enabled toggle).

- Timezone displayed as read-only (edited via TimezoneSection)
- Loads via `loadReminderSettings()` + `loadTenantSettings()` on open
- Saves via `updateReminderSettings()`
- Resets local state on modal open via `useEffect([open])`

### MailboxSection (`features/admin/components/mailbox-section.tsx`)

IMAP/OAuth mailbox configuration.

- Cached in `settingsStore.mailbox`
- Provider selection: Google, Microsoft, IMAP custom
- OAuth flow: opens provider auth URL in popup
- IMAP form: host, port, SSL toggle, password
- Test connection, disconnect actions
- After mutations: `clearSettingsCache()` + reload

### PublicApiSection (`features/admin/components/public-api-section.tsx`) — planned

Pro-only Settings section for Public API Catalog configuration. It should show the visible Public API Key, edit exact Allowed Origins, regenerate the key while preserving origins, and revoke the public API configuration.

### AccessControlSection (`features/admin/components/access-control-section.tsx`)

Lists active WhatsApp access blocks, blocks a phone, and unblocks existing entries through `/access-control/blocks`. This affects bot/code interactions only, not client portal accounts.

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

## Master Feature Components

### MasterDashboard (`features/master/components/dashboard-page.tsx`)

Master admin dashboard with tenant management.

- Summary cards: total, active, inactive counts
- Business table with CRUD
- Code services dialog for global activation
- Tenant support context switch
- Plan selector in business form dialog

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
