# Frontend Architecture

Vue 3 SPA consuming the Trackpal REST API. Hosted on Cloudflare Pages, built with Vite.

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
           Router    Pinia     Axios
         (vue-router) (stores) (services/api.js)
              │         │         │
              └─────────┼─────────┘
                        │
              Single-Page Application
              ┌──────────────────────────────┐
              │  App.vue                     │
              │  ├─ <router-view>            │
              │  └─ <Toaster> (vue-sonner)   │
              ├──────────────────────────────┤
              │  LoginView                   │
              │  MasterOverview (Dashboard)  │
              │  MasterCodeServices          │
              │  TenantOverview (Dashboard)  │
              │  TenantClients               │
              │  TenantCatalog               │
              │  TenantSubscriptions         │
              │  TenantMailbox               │
              │  TenantCodeServices          │
              │  TenantSettings              │
              │  ClientOverview (Dashboard)  │
              └──────────────────────────────┘
```

## Routing (vue-router)

Router lives in `src/router/index.js`. Routes are organized by role group:

### Master routes

| Path | Component | Auth | Role | Notes |
|------|-----------|------|------|-------|
| `/login` | `LoginView` | Public | — | Eager import |
| `/master/overview` | `MasterDashboardView` | Required | `master` | Tenant CRUD + support context |
| `/master/code-services` | `MasterCodeServicesView` | Required | `master` | Global code-service toggles |
| `/master/dashboard` | Redirect → `/master/overview` | — | — | Legacy redirect |

### Tenant / Admin routes

| Path | Component | Auth | Role | Allow master support |
|------|-----------|------|------|---------------------|
| `/admin/overview` | `TenantDashboardView` | Required | `tenant` | ✅ |
| `/admin/clients` | `TenantClientsView` | Required | `tenant` | ✅ |
| `/admin/catalog` | `TenantCatalogView` | Required | `tenant` | ✅ |
| `/admin/subscriptions` | `SubscriptionsView` | Required | `tenant` | ✅ |
| `/admin/mailbox` | `TenantMailboxView` | Required | `tenant` | ✅ |
| `/admin/code-services` | `TenantCodeServicesView` | Required | `tenant` | ✅ |
| `/admin/settings` | `TenantSettingsView` | Required | `tenant` | ❌ (hidden in support mode) |
| `/admin/dashboard` | Redirect → `/admin/overview` | — | — | Legacy redirect |

### Client routes

| Path | Component | Auth | Role |
|------|-----------|------|------|
| `/client/overview` | `ClientDashboardView` | Required | `client` |
| `/client/dashboard` | Redirect → `/client/overview` | — | Legacy redirect |

### Catch-all

| Path | Behavior |
|------|----------|
| `/:pathMatch(.*)*` | Redirect → `/login` |

### Navigation Guard

`router.beforeEach` enforces three rules:

1. **Authentication check**: If route requires auth and no token exists, redirect to `/login`
2. **Role check**: If route requires a specific role and user's role mismatches:
   - Master in support mode (`authStore.activeTenantId` is set) with route having `allowMasterSupport: true` → navigation allowed
   - Master in support mode with `allowMasterSupport: false` (or missing) → redirect to correct dashboard
   - Any other role mismatch → redirect to correct dashboard for their role
3. **Login redirect**: If already authenticated and navigating to `/login`, redirect to the appropriate dashboard based on role

All views except `LoginView` are lazy-loaded via dynamic imports.

## Support Mode Navigation

When a master user enters a tenant's context (via `switchTenant`), the navigation system adapts:

- **`getNavigationContext()`** in `src/config/navigation.js` detects support mode when `role === 'master'`, `activeTenantId` is set, and the current path starts with `/admin`.
- In support mode, the sidebar shows tenant management links but **omits** `/admin/settings` (settings stay on the master account).
- A prominent **"Exit support"** button appears in the sidebar, calling `switchTenant(null)` and redirecting to `/master/overview`.
- `allowMasterSupport` meta on routes controls visibility: tenant routes with `allowMasterSupport: true` are navigateable in support mode; `/admin/settings` has `allowMasterSupport: false` and is blocked.

## Split Tenant Workflow Pages

The original monolithic `TenantDashboardView` has been split into dedicated route-level pages:

| View | Path | Reuses Panel |
|------|------|-------------|
| `TenantDashboardView` | `/admin/overview` | — (navigation hub with cards) |
| `TenantClientsView` | `/admin/clients` | `ClientManagementPanel` |
| `TenantCatalogView` | `/admin/catalog` | `CatalogPanel` |
| `SubscriptionsView` | `/admin/subscriptions` | Subscription sub-components |
| `TenantMailboxView` | `/admin/mailbox` | `MailboxConfigPanel` |
| `TenantCodeServicesView` | `/admin/code-services` | `CodeServicesTenantPanel` |
| `TenantSettingsView` | `/admin/settings` | — (inline profile + password) |

Each view wraps its content in `DashboardLayout`, which provides the sidebar shell + mobile nav + theme/locale controls.

## Shared Shell: DashboardLayout

`DashboardLayout` (`src/components/DashboardLayout.vue`) is the shared layout wrapper for all authenticated views:

- **Desktop sidebar** (hidden on mobile): Trackpal branding, navigation links, exit-support button (support mode only), locale selector, theme toggle, user card + logout
- **Mobile header + sheet** (hidden on desktop): hamburger menu opening a `Sheet` with the same sidebar content
- **Main content slot**: `<slot />` for page content

The layout adapts navigation via `getNavigationContext(authStore, route)`.

## State Management (Pinia)

Two stores in `src/stores/`:

### `auth.js`

- **State**: `token`, `refreshToken`, `user`, `activeTenantId` — all persisted to `localStorage`
- **Getters (computed)**: `isAuthenticated`, `role`, `username`
- **Tenant settings cache**: `reminderSettings`, `timezoneOptions`, `settingsLoaded`, `timezonesLoaded`, `settingsInFlight`, `tenantContextKey`, `settingsLoadError` — runtime-only (not persisted), deduplicated in-flight loading
- **Auth actions**: `login(username, password)` — POST to `/auth/login`, stores tokens + user; `switchTenant(tenantId)` — Master support context; `exitTenantContext()` — exits support context through `/auth/switch-tenant` with `tenant_id: null`; `logout()` — POST to `/auth/logout`, clears localStorage
- **Settings actions**: `loadTenantSettings()` — fetches subscription settings + timezones, deduplicates concurrent calls; `updateReminderSettings(settings)` — PUT to `/subscription-settings`, updates cache

### `i18n.js`

Pinia i18n store that holds the merged translation catalog fetched from the backend:

- **State**: `locale`, `strings` (catalog dict), `isLoaded`
- **Actions**: `loadCatalog()` — fetches `GET /api/v1/i18n/catalog`, stores locale + merged strings
- **Helpers**: `t(key, params)` — looks up key in catalog, applies named params via string replace. Warns in dev if key missing.

Catalog loaded:
- On successful login (called from `LoginView`)
- On page refresh if already authenticated (`main.js` checks `authStore.isAuthenticated`)
- After locale change in profile section (immediate refetch for UI update)

Frontend holds zero source-of-truth translation strings. All strings come from backend catalog.

## UI Primitives (shadcn-vue / Reka UI)

The frontend now uses **shadcn-vue** components built on top of **Reka UI** (headless) and **Tailwind CSS v4**. Components live in `src/components/ui/`:

| Directory | Component |
|-----------|-----------|
| `ui/badge/` | Badge primitive |
| `ui/button/` | Button with variants (default, outline, ghost, destructive) and sizes |
| `ui/card/` | Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter |
| `ui/checkbox/` | Checkbox with label |
| `ui/dialog/` | Modal dialog with overlay |
| `ui/dropdown-menu/` | Dropdown menu |
| `ui/input/` | Text input with error state |
| `ui/select/` | Native select wrapper |
| `ui/separator/` | Horizontal/vertical separator |
| `ui/sheet/` | Slide-out panel (mobile nav) |
| `ui/sonner/` | Toast notification (vue-sonner) |
| `ui/switch/` | Toggle switch |
| `ui/table/` | Table, Thead, Tbody, Tr, Th, Td, Empty |
| `ui/tabs/` | Tab component |
| `ui/textarea/` | Multi-line text input |

These replace all ad-hoc card, button, input, and table markup across views.

## API Integration (Axios)

Singleton Axios instance in `src/services/api.js`:

- Base URL from `VITE_API_URL` env var or fallback `http://localhost:8000/api/v1`
- **Request interceptor**: Attaches `Authorization: Bearer <token>` header from localStorage
- **Response interceptor**: On HTTP 401, clears all auth state from localStorage and redirects to `/login`

The login action uses a direct Axios call (not the api instance) to avoid the auth interceptor loop during login.

## Auth Flow

```
Login Page
  │
  ├─ POST /api/v1/auth/login (username, password)
  │
  ├─ Success → Store tokens + user in Pinia + localStorage
  │              │
  │              ├─ role === "master"  → /master/overview
  │              └─ role === "tenant"  → /admin/overview
  │              └─ role === "client"  → /client/overview
  │
  └─ Failure → Show error message (Spanish: "No se pudo iniciar sesión")
```

Logout:
- POST /api/v1/auth/logout with refresh token
- Clear Pinia state + localStorage
- Redirect to /login

## Styling Architecture

- **Tailwind CSS v4** via `@tailwindcss/vite` plugin
- Custom CSS theme in `src/style.css` using CSS custom properties (`oklch` color space)
- Light and dark color schemes via `.dark` class on `<html>`
- **shadcn-vue** CSS variables pattern: `--background`, `--foreground`, `--card`, `--muted`, `--border`, `--primary`, `--destructive`, etc.
- Theme toggling via `useTheme` composable (persisted to `localStorage`, respects `prefers-color-scheme`)
- `tw-animate-css` for animation utilities

## Build & Dev

Defined in `vite.config.js`:

- **Plugins**: `@vitejs/plugin-vue`, `@tailwindcss/vite`
- **Resolve alias**: `@` → `./src` (used throughout the codebase)
- **Dev server proxy**: `/api` → `http://localhost:8000` (targets backend, changes origin)
- **Build output**: `dist/` directory
- **Env prefix**: `VITE_` variables passed to client
- **Test config**: Vitest with jsdom environment, globals enabled

### Cloudflare Pages Deployment

- `_redirects` file: SPA fallback `/* /index.html 200` — all paths serve index.html
- Favicon: `favicon.svg` (purple Trackpal logo)
- `Icons.svg`: Social media icon sprite (Bluesky, Discord, GitHub, X)

## Views Overview

### LoginView

Login form with i18n-backed UI strings from `i18nStore.t()`. Uses translated labels for title, username, password, sign-in button, loading state, and error message. Calls `i18nStore.loadCatalog()` after successful auth.

### MasterDashboardView

Full tenant management dashboard accessible only to `master` role at `/master/overview`:
- Summary cards: total, active, inactive tenant counts
- Tenant table with CRUD actions
- Manage catalog action switches Master into tenant support context
- Visible `Salir de tenant` action clears support context
- Create/Edit modal form
- Activate/deactivate/delete operations
- Logout button

### MasterCodeServicesView

Global code-service activation toggles at `/master/code-services`.

### TenantDashboardView

Navigation hub at `/admin/overview` accessible to `tenant` role (and master in support mode):
- Card grid linking to: Clients, Catalog, Subscriptions, Mailbox, Code Services
- Settings card is **hidden in support mode** (master viewing a tenant cannot access settings)
- Welcome message with support-mode indicators

### TenantClientsView

Client CRUD page at `/admin/clients`. Wraps `ClientManagementPanel` in `DashboardLayout`.

### TenantCatalogView

Service + plan CRUD page at `/admin/catalog`. Wraps `CatalogPanel` in `DashboardLayout`.

### SubscriptionsView

Full subscription management page at `/admin/subscriptions`:
- Table with columns: client, service, email, profile, duration, dates, status badges, actions
- Filters: status, client, service, quick expiry ranges, custom date range
- Create/Edit/Renew/Reactivate modals with all subscription fields
- Cancel with confirmation dialog
- Reveal credential eye icon per row — decrypts password and PIN on demand
- Uses subscription sub-components in `src/components/subscriptions/`

### TenantMailboxView

Mailbox configuration page at `/admin/mailbox`. Wraps `MailboxConfigPanel` in `DashboardLayout`.

### TenantCodeServicesView

Per-tenant code-service selection page at `/admin/code-services`. Wraps `CodeServicesTenantPanel` in `DashboardLayout`.

### TenantSettingsView

Tenant profile settings page at `/admin/settings` (not accessible in support mode):
- Profile edit form (name, email, phone, locale)
- Password change form (old + new password)
- Reminder settings (subscription expiry notifications)

### ClientDashboardView

Read-only client dashboard at `/client/overview`:
- Client profile display
- Subscription list
- Password change form

## Reusable Components

### Shared UI components (`src/components/`)

| Component | Purpose |
|-----------|---------|
| `DashboardLayout.vue` | Shared shell: sidebar, mobile nav, theme/locale controls |
| `PageHeader.vue` | Consistent page title + description + actions slot |
| `InlineAlert.vue` | Inline info/success/error messages (info, success, error variants) |
| `StatusBadge.vue` | Status indicators (active, inactive, expired, cancelled, neutral) |
| `EmptyState.vue` | Empty data placeholder with title, description, and actions slot |
| `LoadingBlock.vue` | Centered loading indicator |
| `ThemeToggle.vue` | Dark/light mode toggle button |

### Business Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `CatalogPanel.vue` | Master & Tenant dashboards | Service + plan CRUD operations |
| `ClientManagementPanel.vue` | Tenant dashboard | Client CRUD with forms, activation toggle |
| `CodeServicesGlobalPanel.vue` | Master dashboard | Global code-service activation toggles |
| `CodeServicesTenantPanel.vue` | Tenant dashboard | Per-tenant code-service selection |
| `MailboxConfigPanel.vue` | Tenant dashboard | Mailbox config (IMAP, OAuth), connect, test, disconnect |
| `SubscriptionTable.vue` | Subscriptions page | Table with filters, modals, credential reveal |
| `SubscriptionModal.vue` | Subscriptions page | Create/edit subscription form |
| `SubscriptionRenewModal.vue` | Subscriptions page | Renew subscription modal |
| `SubscriptionReactivateModal.vue` | Subscriptions page | Reactivate subscription modal |
| `SubscriptionCancelModal.vue` | Subscriptions page | Cancel with confirmation |
| `SubscriptionFilters.vue` | Subscriptions page | Filter bar for subscriptions table |
| `ReminderSettingsModal.vue` | Subscriptions page | Configure expiry reminder preferences |

### Utilities

| File | Purpose |
|------|---------|
| `catalogDeletePreview.js` | Delete-confirmation validation and preview helpers |
| `test-utils/renderWithApp.js` | Test wrapper that mounts components with Pinia + Router |
| `composables/useTheme.js` | Dark/light theme composable with localStorage persistence |

## Public I18n (pre-auth)

System for translating the login page and any unauthenticated views without backend access.

**Files**: `src/i18n/public.json` + `src/i18n/usePublicI18n.js`

- Local JSON catalog with `en` / `es` entries for `login.*` keys.
- `usePublicI18n()` composable returns reactive `locale`, `setLocale()`, and `t(key, params?)`.
- Selected locale persisted to `localStorage` under key `publicLocale`.
- First visit defaults to `en`. Missing keys return the key itself (no crash).
- Imported in `LoginView.vue` for all login-form text.
- After successful login, switches to backend-sourced `i18nStore`.
