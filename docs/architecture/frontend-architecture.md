# Frontend Architecture

React 19 + TypeScript SPA consuming the Trackpal REST API. Hosted on Cloudflare Pages, built with Vite.

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
        (tanstack) (stores)  (services/api.ts)
              │         │         │
              └─────────┼─────────┘
                        │
              Single-Page Application
              ┌───────────────────────┐
              │  App.tsx              │
              │  └─ <Outlet>          │
              ├───────────────────────┤
              │  LoginPage            │
              │  MasterDashboard      │
              │  TenantDashboard      │
              │  SubscriptionsPage    │
              │  ClientDashboard      │
              └───────────────────────┘
```

## Routing (TanStack Router)

Router lives in `src/router.ts` with the following routes:

| Path | Component | Auth | Role |
|------|-----------|------|------|
| `/login` | `LoginView` | Public | — |
| `/master/dashboard` | `MasterDashboardView` | Required | `master` |
| `/admin/dashboard` | `TenantDashboardView` | Required | `tenant` |
| `/admin/subscriptions` | `SubscriptionsView` | Required | `tenant` |
| `/client/dashboard` | `ClientDashboardView` | Required | `client` |
| `/:pathMatch(.*)*` | Redirect → `/login` | — | — |

### Navigation Guard

TanStack Router uses `beforeLoad` hooks for route guards:

1. **Authentication check**: If route requires auth and no token exists, redirect to `/login`
2. **Role check**: If route requires a specific role and user's role mismatches, redirect to the correct dashboard for their role (or `/login` if no role)
3. **Login redirect**: If already authenticated and navigating to `/login`, redirect to the appropriate dashboard based on role

`LoginPage` is eagerly loaded. Dashboard pages use lazy loading.

## State Management (Zustand)

Key stores in `src/stores/`:

### `authStore`

- **State**: `token`, `refreshToken`, `user`, `activeTenantId` — all persisted to `localStorage`
- **Selectors**: `isAuthenticated`, `role`, `username`
- **Actions**: `login(username, password)` — POST to `/auth/login`, stores tokens + user; `switchTenant(tenantId)` — Master support context; `exitTenantContext()` — exits support context through `/auth/switch-tenant` with `tenant_id: null`; `logout()` — POST to `/auth/logout`, clears localStorage

Client users land on `/client/dashboard`, which shows readonly client profile data and password change only.

Token and user data are read from `localStorage` on store initialization, surviving page reloads.

### `i18nStore`

Zustand i18n store that holds the merged translation catalog fetched from the backend:

- **State**: `locale`, `strings` (catalog dict), `isLoaded`
- **Actions**: `loadCatalog()` — fetches `GET /api/v1/i18n/catalog`, stores locale + merged strings
- **Helpers**: `t(key, params)` — looks up key in catalog, applies named params via string replace. Warns in dev if key missing.

Catalog loaded:
- On successful login (called from `LoginView`)
- On page refresh if already authenticated (`main.ts` checks `authStore.isAuthenticated`)
- After locale change through `PUT /api/v1/tenant-settings` (immediate refetch for UI update)

Frontend holds zero source-of-truth translation strings. All strings come from backend catalog.

Note: The frontend was migrated from Vue 3 + Pinia to React 19 + TypeScript + Zustand + TanStack Router. The i18n patterns remain conceptually the same (backend-sourced catalog, post-auth load, locale refetch on change) but use Zustand instead of Pinia.

## API Integration (Axios)

Singleton Axios instance in `src/services/api.ts`:

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
  ├─ Success → Store tokens + user in Zustand + localStorage
  │              │
  │              ├─ role === "master"  → /master/dashboard
  │              └─ role === "tenant"  → /admin/dashboard
  │              └─ role === "client"  → /client/dashboard
  │
  └─ Failure → Show error message (Spanish: "No se pudo iniciar sesión")
```

Logout:
- POST /api/v1/auth/logout with refresh token
- Clear Zustand state + localStorage
- Redirect to /login

## Build & Dev

Defined in `vite.config.ts`:

- **Plugin**: `@vitejs/plugin-react`
- **Dev server proxy**: `/api` → `http://localhost:8000` (targets backend, changes origin)
- **Build output**: `dist/` directory
- **Env prefix**: `VITE_` variables passed to client

### Cloudflare Pages Deployment

- `_redirects` file: SPA fallback `/* /index.html 200` — all paths serve index.html
- Favicon: `favicon.svg` (purple Trackpal logo)
- `Icons.svg`: Social media icon sprite (Bluesky, Discord, GitHub, X)

## Views Overview

### LoginPage

Login form with i18n-backed UI strings from `i18nStore.t()`. Uses translated labels for title, username, password, sign-in button, loading state, and error message. Calls `i18nStore.loadCatalog()` after successful auth.

### MasterDashboard

Full tenant management dashboard accessible only to `master` role:
- Summary cards: total, active, inactive tenant counts
- Tenant table with CRUD actions
- Manage catalog action switches Master into tenant support context
- Visible `Salir de tenant` action clears support context
- Create/Edit modal form
- Activate/deactivate/delete operations
- Logout button

### TenantDashboard

Self-service dashboard accessible only to `tenant` role:
- Welcome message + profile display
- Profile edit form (name, email, phone) — identity fields saved through `PUT /api/v1/me`
- **Locale and timezone** settings — saved through `PUT /api/v1/tenant-settings` (separate from profile identity)
- Password change form (old + new password)
- Catalog management: services CRUD and per-service plans CRUD
- Client management: table with CRUD actions; create-client form uses i18n label `frontend.clients.password` (`Contraseña` / `Password`)
- Link to subscriptions page
- Duplicate/validation API errors shown in user's locale
- Locale/timezone `<select>` or dropdowns in settings section; on locale save, refetches i18n catalog for immediate UI update
- Logout button

### SubscriptionsPage

Full subscription management page at `/admin/subscriptions` accessible only to `tenant` role:
- Table with columns: client, service, email, profile, duration, dates, status badges, actions
- Filters: status, client, service, quick expiry ranges, custom date range
- Create/Edit/Renew/Reactivate modals with all subscription fields
- Cancel with confirmation dialog
- Reveal credential eye icon per row -- decrypts password and PIN on demand
- Reminder settings panel: timezone dropdown (from `GET /api/v1/tenant-settings/timezones`), warning days, reminder time, recipient mode, reminders_enabled toggle; timezone edits no longer owned by reminder modal — handled at tenant level through `/tenant-settings`

Dashboard data is loaded from `GET /api/v1/dashboard` and `GET /api/v1/me` on mount.

## Reusable Components

Five panel components in `src/components/` extracted from views for maintainability:

| Component | Location | Purpose |
|-----------|----------|---------|
| `CatalogPanel.tsx` | Master & Tenant dashboards | Service + plan CRUD operations |
| `ClientManagementPanel.tsx` | Tenant dashboard | Client CRUD with forms, activation toggle |
| `CodeServicesGlobalPanel.tsx` | Master dashboard | Global code-service activation toggles |
| `CodeServicesTenantPanel.tsx` | Tenant dashboard | Per-tenant code-service selection |
| `MailboxConfigPanel.tsx` | Tenant dashboard | Mailbox config (IMAP, OAuth), connect, test, disconnect |

## Public I18n (pre-auth)

System for translating the login page and any unauthenticated views without backend access.

**Files**: `src/i18n/public.json` + `src/i18n/usePublicI18n.ts`

- Local JSON catalog with `en` / `es` entries for `login.*` keys.
- `usePublicI18n()` hook returns reactive `locale`, `setLocale()`, and `t(key, params?)`.
- Selected locale persisted to `localStorage` under key `publicLocale`.
- First visit defaults to `en`. Missing keys return the key itself (no crash).
- Imported in `LoginPage.tsx` for all login-form text.
- After successful login, switches to backend-sourced `i18nStore`.
