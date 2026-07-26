# Frontend Architecture

React 19 + TypeScript SPA consuming the TrackPal REST API. Hosted on Cloudflare Pages, built with Vite.

## High-Level Design

```
[Browser] ── Vite Dev Server (dev) ── proxy /api ──→ [Backend :8000]
                        │
             Cloudflare Pages (prod)
                        │
              SPA with client-side routing
                        │
              ┌─────────┼─────────┐
              │         │         │
          Router   Zustand    Axios
       (tanstack) (stores)  (lib/api.ts)
              │         │         │
              └─────────┼─────────┘
                        │
              Single-Page Application
              ┌───────────────────────┐
              │  App.tsx              │
              │  └─ <RouterProvider>  │
              ├───────────────────────┤
              │  RootRoute            │
              │  ├─ LoginPage         │
              │  ├─ MasterLayout      │
              │  ├─ AdminLayout       │
              │  └─ ClientLayout      │
              └───────────────────────┘
```

## Routing (TanStack Router)

File-based routing via `@tanstack/router-plugin`. Route tree auto-generated at `src/routeTree.gen.ts`.

Routes defined in `src/routes/`:

| File | Path | Component | Auth | Role |
|------|------|-----------|------|------|
| `login.tsx` | `/login` | `LoginForm` | Public | — |
| `index.tsx` | `/` | Redirect by role | Required | any |
| `master.tsx` → `master/dashboard.tsx` | `/master/dashboard` | `MasterDashboard` | Required | `master` |
| `admin.tsx` → `admin/dashboard.tsx` | `/admin/dashboard` | `DashboardPage` | Required | `tenant` |
| `admin.tsx` → `admin/clients.tsx` | `/admin/clients` | `ClientsPage` (Pro-only) | Required | `tenant` |
| `admin.tsx` → `admin/catalog.tsx` | `/admin/catalog` | `CatalogPage` (Pro-only) | Required | `tenant` |
| `admin.tsx` → `admin/subscriptions.tsx` | `/admin/subscriptions` | `SubscriptionsPage` (Pro-only) | Required | `tenant` |
| `admin.tsx` → `admin/settings.tsx` | `/admin/settings` | `SettingsPage` with My Account tabs | Required | `tenant` |
| `admin.tsx` → `admin/help.tsx` | `/admin/help` | `HelpCenterPage` (private release-gated) | Required | `tenant` |
| `client.tsx` → `client/dashboard.tsx` | `/client/dashboard` | `ClientDashboard` | Required | `client` |
| `client.tsx` → `client/profile.tsx` | `/client/profile` | `ProfilePage` | Required | `client` |
| `client.tsx` → `client/help.tsx` | `/client/help` | `HelpCenterPage` (private release-gated) | Required | `client` |

Starter tenant admins see 404 for direct navigation to Pro-only admin routes (`/admin/clients`, `/admin/catalog`, `/admin/subscriptions`). Master support context bypasses this frontend gate to inspect preserved Pro data.

### Route Layouts

- `__root.tsx` — Root layout: loads i18n catalog before rendering, renders `<Outlet>` + `<Toaster>` + devtools
- `master.tsx` — Master layout with sidebar nav
- `admin.tsx` — Tenant Admin layout with shared collapsible desktop sidebar, plan-aware role navigation, contextual Help on Dashboard, Pro modules, and Settings, and support banner for Master support context; mobile navigation opens in a Sheet
- `client.tsx` — Client layout using the same shared role navigation and mobile Sheet; when private Help is enabled it exposes Dashboard, Profile, and Help only, plus contextual Help on Client screens


### Navigation Guard

Root route (`__root.tsx`) handles auth initialization:
1. Checks `localStorage` for token
2. If authenticated, loads i18n catalog (blocks rendering until loaded to prevent raw key flash)
3. If not authenticated, renders immediately (login page has its own public i18n)

Index route (`/`) redirects by role:
- `master` → `/master/dashboard`
- `tenant` → `/admin/dashboard`
- `client` → `/client/dashboard`
- unauthenticated → `/login`

## State Management (Zustand)

Three Zustand stores in `src/store/`:

### `authStore` (`store/auth.ts`)

- **State**: `token`, `refreshToken`, `user`, `activeTenantId`, and `tenantPlan` remain persisted to `localStorage` for production compatibility.
- **Demo context**: authenticated Demo Accounts persist immutable `demo` metadata separately from workspace data: tenant id, immutable display name, plan, lifecycle status, activation/expiration timestamps, credential version, and server time.
- **Data source**: `dataSource` is selected once from the authenticated context. Production uses the existing API boundary; Demo Accounts use a tenant-isolated browser-local workspace repository. Resource contracts cover dashboard, settings, CRUD, simulator, and orientation consumers.
- **Actions**:
  - `login(username, password)` — POST to `/auth/login`, stores tokens + auth metadata, clears all caches, and loads the i18n catalog.
  - `refresh()` — rotates tokens while preserving Demo lifecycle metadata and distinguishes `demo_ended` and `demo_credentials_replaced` outcomes.
  - `heartbeat()` — POST to `/auth/heartbeat` and updates lifecycle-only metadata without loading business data.
  - `switchTenant(tenantId)` — Master support context switch, clears all caches, and returns to the production adapter.
  - `logout()` — POST to `/auth/logout`, clears auth metadata and caches, but preserves the matching Demo Workspace for a later login.
  - `setTenantPlan(plan)` — corrects production `tenantPlan` from dashboard responses without changing Demo's immutable plan.

- **Demo connectivity**: `useDemoHeartbeat` owns one interval while an active Demo Account is mounted, deduplicates overlapping focus and hidden-to-visible checks, and removes the interval/listeners on logout, navigation, unmount, or context change. One transient failure shows a localized warning; two pause the shell behind an accessible manual-retry overlay. Successful retry resets the count and keeps the browser-local workspace intact.
- **Lifecycle fail-closed**: a missing, changed, expired, or deleted Demo identity clears the matching workspace and navigates to the public Demo Ended page; `demo_credentials_replaced` preserves the workspace and returns to login with a reauthentication message. Manual logout remains a neutral login transition.

### Demo Workspace contract (`features/demo/services/demo-workspace.ts`)

- Workspace storage is keyed by `trackpal:demo-workspace:<tenant_id>` so different Demo Accounts cannot share browser state.
- The versioned envelope stores lifecycle anchors, the deterministic plan baseline, browser-local settings/business state, and tour acknowledgements; it excludes tokens, passwords, credentials, session identifiers, and chat transcripts.
- `ensure()` creates the envelope lazily after authenticated Demo context exists; Starter initializes the Master-provided business name, English locale, connected simulated mailbox/WhatsApp states, three ordered generic code services, and two ordered blocked identities. `reset()` restores that baseline while preserving tour state, and `clear()` removes only the selected Demo Account's workspace.

### `settingsStore` (`store/settings.ts`)

Caches tenant settings, reminder settings, timezone options, and mailbox configuration:

- **State**: `reminderSettings`, `tenantSettings`, `timezoneOptions`, `mailbox` + loaded/in-flight flags
- **Dedup**: In-flight promise deduplication prevents concurrent duplicate API calls
- **Epoch guard**: `_settingsEpoch` counter prevents stale responses from setting state after cache clear
- **Actions**: `loadReminderSettings()`, `loadTenantSettings()`, `loadTimezoneOptions()`, `loadMailbox()`, `updateReminderSettings()`, `updateTenantSettings()`, `clearSettingsCache()`

### `catalogStore` (`store/catalog.ts`)

Caches reference data (services, plans, clients):

- **State**: `services`, `plans` (keyed by serviceId), `clients` + loaded/in-flight flags
- **Dedup**: In-flight promise deduplication
- **Actions**: `loadServices()`, `loadPlans(serviceId)`, `loadClients()`, `invalidateServices()`, `invalidatePlans(serviceId?)`, `invalidateClients()`, `clearAll()`

### `exportStore` (`features/admin/stores/export-store.ts`)

Manages Tenant Data Export state for the My Account Data tab:

- **State**: `job` (current export with status, timestamps, actor attribution, cooldown, expiry, download URL), `requesting`, `downloadLoading`, `cancelling`, `error`
- **Polling**: `refreshStatus()` fetches current job; called on mount and periodically while Data tab is open
- **Actions**:
  - `requestExport()` — POST to `/me/export` with password step-up
  - `refreshStatus()` — GET `/me/export` current status
  - `cancelExport()` — POST `/me/export/cancel` to cancel pending/processing job
  - `download()` — GET `/me/export/download` presigned URL and trigger browser download
  - `reset()` — Clear all state (on unmount)

### Cache Invalidation Pattern

All stores are invalidated on:
- `login()` — clears settings + catalog + export stores
- `logout()` — clears settings + catalog + export stores; redirects to login after Tenant Admin deletion
- `switchTenant()` — clears settings + catalog + export stores

Individual CRUD operations invalidate their specific cache:
- Client create/update/delete → `invalidateClients()`
- Service create/rename/delete → `invalidateServices()`
- Plan create/rename/delete → `invalidatePlans(serviceId)`
- Mailbox save/test/disconnect → `clearSettingsCache()` (full reset)
- Timezone/locale save → `updateTenantSettings()` (updates cache directly)

## I18n System

### Backend-sourced catalog

- `src/i18n/index.ts` — plain module (not a store)
- `loadCatalog()` fetches `GET /api/v1/i18n/catalog`, stores merged strings
- `t(key, params?)` — looks up key, applies named params via regex replace. Missing keys return the key itself.
- `getLocale()` — returns current locale string
- `isCatalogReady()` / `waitForCatalog()` — async initialization helpers

### Public i18n (pre-auth)

- `src/i18n/public.json` — local JSON catalog with `en`/`es` entries for `login.*` keys
- `src/i18n/public.ts` — `usePublicI18n()` hook returns reactive `locale`, `setLocale()`, `t(key)`
- Selected locale persisted to `localStorage` under key `publicLocale`
- After successful login, switches to backend-sourced i18n

### Catalog loading sequence

1. On page refresh: root route checks token → if exists, `loadCatalog()` → blocks rendering until loaded
2. On login: `login()` action calls `loadCatalog()` after storing tokens
3. On locale change: `updateTenantSettings()` triggers `loadCatalog()` in the calling component

## API Integration (Axios)

Singleton Axios instance in `src/lib/api.ts`:

- Base URL from `VITE_API_URL` env var or fallback `http://localhost:8000/api/v1`
- **Request interceptor**: Attaches `Authorization: Bearer <token>` from `localStorage`
- **Response interceptor**: On ordinary HTTP 401, clears auth tokens and demo metadata and redirects to `/login`. Lifecycle-coded Demo failures (`demo_ended`, `demo_credentials_replaced`) bypass the hard redirect so `authStore` can preserve or clear the matching workspace and route to the correct outcome; the Demo Workspace remains untouched for credential replacement.

Authentication services also expose typed `/auth/refresh` and `/auth/heartbeat` contracts. Stable lifecycle details (`demo_ended`, `demo_credentials_replaced`) are kept distinct from ordinary authentication failures in `authStore.authOutcome`.
Path alias: `@/` maps to `src/` (configured in `tsconfig.json` + `vite.config.ts`).

## Auth Flow

```
Login Page (LoginForm)
  │
  ├─ POST /api/v1/auth/login (username, password)
  │
  ├─ Success → Store tokens + user in Zustand + localStorage
  │              │
  │              ├─ role === "master"  → /master/dashboard
  │              ├─ role === "tenant"  → /admin/dashboard
  │              └─ role === "client"  → /client/dashboard
  │
  └─ Failure → Show error message
```

Logout:
- POST /api/v1/auth/logout with refresh token
- Clear Zustand state + localStorage
- Clear all caches (settings + catalog)
- Redirect to /login

## UI Framework

- **Styling**: Tailwind CSS v4 via `@tailwindcss/vite` plugin
- **Components**: shadcn/ui (Radix-based) — `src/components/ui/`
- **Icons**: Lucide React
- **Toasts**: Sonner
- **Theme**: `next-themes` with dark mode default

## Build & Dev

Defined in `vite.config.ts`:

- **Plugins**: `@vitejs/plugin-react`, `@tailwindcss/vite`, `@tanstack/router-plugin/vite`
- **Path alias**: `@` → `./src`
- **Build output**: `dist/` directory
- **TypeScript**: strict mode via `tsconfig.app.json`

### Scripts

| Command | Action |
|---------|--------|
| `npm run dev` | Start Vite dev server with HMR |
| `npm run build` | `tsc -b && vite build` — type check + production build |
| `npm run lint` | ESLint |
| `npm run preview` | Preview production build locally |

### Cloudflare Pages Deployment

- `_redirects` file: SPA fallback `/* /index.html 200` — all paths serve index.html
- Favicon: `favicon.svg` (purple TrackPal logo)
- `Icons.svg`: Social media icon sprite

## Views Overview

### LoginPage (`features/auth/components/login-form.tsx`)

Login form with pre-auth i18n via `usePublicI18n()`. Uses translated labels for title, username, password, sign-in button, loading state, and error message. After successful auth, catalog switches to backend-sourced.

### AdminLayout (`features/admin/layout/admin-layout.tsx`)

Collapsible sidebar layout for tenant admin pages:
- Shared role-navigation model: Dashboard, Clients, Catalog, Subscriptions, and Settings remain in the existing order; Starter hides the Pro-only destinations and Master Support Context shows them.
- Desktop sidebar: brand, authorized nav items, username, collapse control, and logout.
- Mobile: the shared header exposes an accessible menu control that opens the authorized destinations in a focus-managed `Sheet`; selecting a destination closes the Sheet.
- Content: `<Outlet>` renders child routes.
- When Master support context active with Starter tenant: renders `<SupportBanner>` above `<Outlet>`.
- Starter Demo dashboard cards and enabled-service badges load through the selected data-source adapter and derive entirely from the browser-local workspace; production dashboards retain the API-backed adapter.
- Starter Demo orientation content remains server-readable, while completion/skipping is acknowledged in the local workspace so reload and logout/login preserve it without a business mutation request.

### ClientLayout (`features/client/layout/client-layout.tsx`)

Client navigation uses the same role-navigation and sidebar primitives. When private Help is enabled it exposes only Dashboard, Profile, and Help, with Help last before account/logout. Desktop active states are exact route matches; mobile exposes the same authorized destinations through the focus-managed `Sheet`. Contextual Help is available on the Dashboard and Profile screens and never starts an Orientation Tour.


### MasterLayout (`features/master/layout/master-layout.tsx`)

Sidebar layout for master pages. The Master dashboard keeps lifecycle work separated into accessible `Production` and `Demos` tabs:
- **Production** renders the existing summary cards, search, tenant rows, exports, status actions, deletion, and support-context actions. Demo Tenants are excluded from its rows and counts even if a stale response contains them.
- **Demos** uses the lifecycle-only `/demos/` API. It renders no workspace preview, activity feed, last-seen fields, summary cards, or usage telemetry.
- Demo creation accepts only a name and Starter/Pro plan (Starter by default). Credential creation/replacement responses show the plaintext password once with independent username/password copy actions; dismissing the dialog clears it.
- Pending, Active, and Expired lifecycle rows expose status-specific actions. Credential replacement is disabled for Expired rows, while deletion is confirmable for every status. Desktop tables have responsive mobile card lists.
- Manage catalog action switches into tenant support context for production Tenants only.

### SettingsPage (`features/admin/components/settings-page.tsx`)

`SettingsPage` renders tenant settings as a flat category list plus a single active detail panel. No category opens by default; the panel shows a guide message until the user selects a category. Desktop uses a lateral category menu, mobile uses a `Sheet` category picker, long sections scroll inside the detail panel, and the common Cancelar action closes the active section so unsaved local edits are discarded by unmounting the section component.

**Settings now includes My Account as the first category**, replacing the old separate Profile and Password categories. My Account uses role-aware horizontal tabs:

| Tab | Tenant Admin | Master Support Context |
|-----|-------------|------------------------|
| Profile | Full profile (identity fields) | Target business profile (reads/updates selected Tenant, not Master identity) |
| Security | Password change | Not rendered |
| Data | Export status/actions + self-service deletion | Export status/actions only (no Security tab, no deletion action) |

**Data tab** (`DataTabContent`):
- Displays current export job status (empty, pending, processing, ready, failed, cancelled)
- Polls status while Data tab is open
- Request new export button (triggers password step-up dialog)
- Cancel pending/processing export
- Download ready export via presigned URL
- Download previous version while replacement is in progress
- Actor attribution: localized "You" / "Support" labels
- Cooldown display with remaining time
- Expiry countdown for ready exports
- Danger zone (Tenant Admin only): self-service deletion with password + destructive word dialog
- Master Support Context: replaces danger zone with guidance back to Master Dashboard

### SubscriptionsPage (`features/admin/components/subscriptions-page.tsx`)

Full subscription management (Pro-only):
- Table with columns: client, service, email, profile, duration, dates, status badges, actions
- Filters: status, client, service
- Create/Edit/Renew/Reactivate/Cancel modals
- Reveal credential per row

### ClientsPage (`features/admin/components/clients-page.tsx`)

Client management with cached data from `catalogStore` (Pro-only):
- Client table with search
- Create/Edit/Delete dialogs
- Activate/deactivate toggle
- Link to subscriptions per client
- Pro Demo Accounts route Clients CRUD through the browser-local workspace adapter: the deterministic baseline has five fictional clients, local validation/uniqueness/phone normalization, lifecycle toggles, relation-safe deletion, search/status filtering, and pagination. Mutations never call tenant Client or Client identity APIs and remain available after reload or logout/login.

### CatalogPage (`features/admin/components/catalog-page.tsx`)

Service + plan CRUD with cached data from `catalogStore` (Pro-only):
- Services sidebar with create/rename/delete
- Plans panel with create/rename/delete
- Delete preview dialog with confirmation

- Pro Demo Accounts use the browser-local catalog adapter: the baseline has exactly three deterministic generic services with six representative plans; service/plan names are trimmed, case-insensitively unique within their scope, and capped at 200 characters.
- Catalog delete previews expose affected plans and active/historical subscription impact. Confirmed service deletion cascades plans and related local references, while plan deletion removes its local references; Starter workspaces have no catalog baseline.
- CatalogPage and dependent subscription selectors use the selected data-source adapter, so Demo catalog reads and mutations never call catalog API endpoints and persist across reload or logout/login.