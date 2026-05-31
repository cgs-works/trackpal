# Frontend Codebase Structure

```
frontend/
├── index.html                    # HTML entry point, mounts #app with /src/main.js
├── package.json                  # Dependencies: vue 3, pinia, vue-router, axios
├── vite.config.js                # Vite config: Vue plugin, dev proxy /api → :8000
├── .env.example                  # VITE_API_URL template
├── .gitignore                    # Node, dist, editor artifacts
│
├── public/
│   ├── favicon.svg               # Trackpal logo (purple gradient)
│   ├── icons.svg                 # Social media icon sprite
│   └── _redirects                # Cloudflare Pages SPA fallback: /* /index.html 200
│
├── src/
│   ├── main.js                   # App bootstrap: createApp, Pinia, router, mount
│   ├── App.vue                   # Root component — just <router-view />
│   ├── style.css                 # Global styles: font, body, .login-page, .login-form, error
│   │
│   ├── router/
│   │   └── index.js              # Vue Router config + navigation guard (auth + role)
│   │
│   ├── services/
│   │   └── api.js                # Axios instance: base URL, JWT interceptor, 401 handler
│   │
│   ├── stores/
│   │   ├── auth.js               # Pinia store: token, user, activeTenantId, login, switch, logout
│   │   └── i18n.js               # Pinia store: locale, catalog, t(), loadCatalog()
│   │
│   ├── i18n/
│   │   ├── public.json           # Pre-auth translation strings (en/es for login page)
│   │   └── usePublicI18n.js      # Composable: locale, setLocale, t() — persists localStorage
│   │
│   ├── components/               # Reusable UI panels extracted from views
│   │   ├── CatalogPanel.vue              # Service + plan CRUD panel
│   │   ├── ClientManagementPanel.vue     # Client CRUD panel with forms
│   │   ├── CodeServicesGlobalPanel.vue   # Master global code-service toggles
│   │   ├── CodeServicesTenantPanel.vue   # Tenant code-service selection panel
│   │   └── MailboxConfigPanel.vue        # Mailbox config (IMAP/OAuth) panel
│   │
│   ├── styles/
│   │   ├── client-dashboard.css           # Client dashboard specific styles
│   │   └── client-dashboard-responsive.css # Responsive breakpoints for client dashboard
│   │
│   └── views/
│       ├── LoginView.vue         # Login form (Spanish UI)
│       ├── MasterDashboardView.vue  # Master tenant CRUD + support context switch
│       ├── TenantDashboardView.vue  # Tenant profile/password + catalog + client CRUD
│       ├── SubscriptionsView.vue    # Subscription CRUD table + modals
│       └── ClientDashboardView.vue  # Client readonly dashboard + password change
│
└── dist/                         # Build output (gitignored)
```

## Entry Points

| File | Purpose |
|------|---------|
| `index.html` | HTML shell, loads `/src/main.js` as module |
| `src/main.js` | Creates Vue app, registers Pinia + Router, mounts to `#app` |
| `src/App.vue` | Root component rendering `<router-view />` |

## Module Responsibilities

| Module | Files | Responsibility |
|--------|-------|----------------|
| Router | `router/index.js` | Route definitions, lazy loading, navigation guard for auth + role; /admin/subscriptions route for subscriptions |
| API Service | `services/api.js` | Axios singleton, JWT injection on requests, 401 auto-logout |
| Auth Store | `stores/auth.js` | Login/logout/switch actions, token/user/active tenant persistence in localStorage |
| I18n Store | `stores/i18n.js` | Fetches catalog from backend, locale state, `t(key, params)` resolver |
| Public I18n | `i18n/usePublicI18n.js` | Pre-auth i18n composable with local JSON catalog, persists locale to localStorage |
| Components | `components/*.vue` | Reusable panels: Catalog, ClientManagement, CodeServices (global + tenant), MailboxConfig |
| Views | `views/*.vue` | Page-level components: login, master dashboard, tenant dashboard, subscriptions page, client dashboard |

## Dependencies (from package.json)

| Package | Type | Purpose |
|---------|------|---------|
| `vue` ^3.5.34 | dependency | Reactive UI framework |
| `pinia` ^3.0.4 | dependency | State management |
| `vue-router` ^4.6.4 | dependency | Client-side routing |
| `axios` ^1.16.0 | dependency | HTTP client with interceptors |
| `@vitejs/plugin-vue` ^6.0.6 | devDependency | Vite plugin for Vue SFC compilation |
| `vite` ^8.0.12 | devDependency | Build tool and dev server |

## Scripts

| Command | Action |
|---------|--------|
| `npm run dev` | Start Vite dev server with HMR |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Preview production build locally |
