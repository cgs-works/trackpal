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
              ┌───────────────────┐
              │  App.vue          │
              │  └─ <router-view> │
              ├───────────────────┤
              │  LoginView        │
              │  MasterDashboard  │
              │  TenantDashboard  │
              │  Subscriptions    │
              │  ClientDashboard  │
              └───────────────────┘
```

## Routing (vue-router)

Router lives in `src/router/index.js` with five routes:

| Path | Component | Auth | Role |
|------|-----------|------|------|
| `/login` | `LoginView` | Public | — |
| `/master/dashboard` | `MasterDashboardView` | Required | `master` |
| `/admin/dashboard` | `TenantDashboardView` | Required | `tenant` |
| `/admin/subscriptions` | `SubscriptionsView` | Required | `tenant` |
| `/client/dashboard` | `ClientDashboardView` | Required | `client` |
| `/:pathMatch(.*)*` | Redirect → `/login` | — | — |

### Navigation Guard

`router.beforeEach` enforces two rules:

1. **Authentication check**: If route requires auth and no token exists, redirect to `/login`
2. **Role check**: If route requires a specific role and user's role mismatches, redirect to the correct dashboard for their role (or `/login` if no role)
3. **Login redirect**: If already authenticated and navigating to `/login`, redirect to the appropriate dashboard based on role

No lazy loading is used for `LoginView` (eager import). `MasterDashboardView` and `TenantDashboardView` are lazy-loaded via dynamic imports.

## State Management (Pinia)

Two stores in `src/stores/`:

### `auth.js`

- **State**: `token`, `refreshToken`, `user`, `activeTenantId` — all persisted to `localStorage`
- **Getters (computed)**: `isAuthenticated`, `role`, `username`
- **Actions**: `login(username, password)` — POST to `/auth/login`, stores tokens + user; `switchTenant(tenantId)` — Master support context; `exitTenantContext()` — exits support context through `/auth/switch-tenant` with `tenant_id: null`; `logout()` — POST to `/auth/logout`, clears localStorage

Client users land on `/client/dashboard`, which shows readonly client profile data and password change only.

Token and user data are read from `localStorage` on store initialization, surviving page reloads.

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
  │              ├─ role === "master"  → /master/dashboard
  │              └─ role === "tenant"  → /admin/dashboard
  │              └─ role === "client"  → /client/dashboard
  │
  └─ Failure → Show error message (Spanish: "No se pudo iniciar sesión")
```

Logout:
- POST /api/v1/auth/logout with refresh token
- Clear Pinia state + localStorage
- Redirect to /login

## Build & Dev

Defined in `vite.config.js`:

- **Plugin**: `@vitejs/plugin-vue`
- **Dev server proxy**: `/api` → `http://localhost:8000` (targets backend, changes origin)
- **Build output**: `dist/` directory
- **Env prefix**: `VITE_` variables passed to client

### Cloudflare Pages Deployment

- `_redirects` file: SPA fallback `/* /index.html 200` — all paths serve index.html
- Favicon: `favicon.svg` (purple Trackpal logo)
- `Icons.svg`: Social media icon sprite (Bluesky, Discord, GitHub, X)

## Views Overview

### LoginView

Login form with i18n-backed UI strings from `i18nStore.t()`. Uses translated labels for title, username, password, sign-in button, loading state, and error message. Calls `i18nStore.loadCatalog()` after successful auth.

### MasterDashboardView

Full tenant management dashboard accessible only to `master` role:
- Summary cards: total, active, inactive tenant counts
- Tenant table with CRUD actions
- Manage catalog action switches Master into tenant support context
- Visible `Salir de tenant` action clears support context
- Create/Edit modal form
- Activate/deactivate/delete operations
- Logout button

### TenantDashboardView

Self-service dashboard accessible only to `tenant` role:
- Welcome message + profile display
- Profile edit form (name, email, phone, **locale**)
- Password change form (old + new password)
- Catalog management: services CRUD and per-service plans CRUD
- Client management: table with CRUD actions
- Link to subscriptions page
- Duplicate/validation API errors shown in user's locale
- Locale `<select>` in profile section (en/es); on save, refetches i18n catalog for immediate UI update
- Logout button

### SubscriptionsView

Full subscription management page at `/admin/subscriptions` accessible only to `tenant` role:
- Table with columns: client, service, email, profile, duration, dates, status badges, actions
- Filters: status, client, service, quick expiry ranges, custom date range
- Create/Edit/Renew/Reactivate modals with all subscription fields
- Cancel with confirmation dialog
- Reveal credential eye icon per row -- decrypts password and PIN on demand

Dashboard data is loaded from `GET /api/v1/dashboard` and `GET /api/v1/me` on mount.
