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

- **State**: `token`, `refreshToken`, `user`, `activeTenantId` — persisted to `localStorage`
- **Selectors**: `isAuthenticated`, `role`, `username`
- **Plan-aware state**:
  - `tenantPlan`: `starter | pro | null`, persisted from auth responses and corrected by tenant dashboard responses. This is only a UI hint; backend gates remain authoritative.
  - `isMasterSupportContext`: true when Master is switched into a tenant (`role=master` + `activeTenantId`). Master support sees the full admin surface and a support banner.
- **Actions**:
  - `login(username, password)` — POST to `/auth/login`, stores tokens + user, clears all caches, loads i18n catalog
  - `switchTenant(tenantId)` — Master support context switch, clears all caches
  - `logout()` — POST to `/auth/logout`, clears localStorage + all caches
  - `setTenantPlan(plan)` — corrects `tenantPlan` from dashboard response after initial render

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
- **Response interceptor**: On HTTP 401, clears all auth state from `localStorage` and redirects to `/login`

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

### ClientLayout (`features/client/layout/client-layout.tsx`)

Client navigation uses the same role-navigation and sidebar primitives. When private Help is enabled it exposes only Dashboard, Profile, and Help, with Help last before account/logout. Desktop active states are exact route matches; mobile exposes the same authorized destinations through the focus-managed `Sheet`. Contextual Help is available on the Dashboard and Profile screens and never starts an Orientation Tour.


### MasterLayout (`features/master/layout/master-layout.tsx`)

Sidebar layout for master pages:
- Summary cards: total, active, inactive tenant counts
- Business table with CRUD actions
- Manage catalog action switches into tenant support context

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

### CatalogPage (`features/admin/components/catalog-page.tsx`)

Service + plan CRUD with cached data from `catalogStore` (Pro-only):
- Services sidebar with create/rename/delete
- Plans panel with create/rename/delete
- Delete preview dialog with confirmation
