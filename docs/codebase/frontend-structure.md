# Frontend Codebase Structure

```
frontend/
├── index.html                    # HTML entry point, mounts #app with /src/main.js
├── package.json                  # Dependencies: vue 3, pinia, vue-router, axios, reka-ui, shadcn-vue, tailwindcss v4
├── vite.config.js                # Vite config: Vue plugin, Tailwind plugin, @ alias, dev proxy /api → :8000, Vitest config
├── .env.example                  # VITE_API_URL template
├── .gitignore                    # Node, dist, editor artifacts
│
├── public/
│   ├── favicon.svg               # Trackpal favicon asset
│   ├── icons.svg                 # Social media icon sprite
│   └── _redirects                # Cloudflare Pages SPA fallback: /* /index.html 200
│
├── src/
│   ├── main.js                   # App bootstrap: createApp, Pinia, Router, i18n preload, mount
│   ├── App.vue                   # Root component — <router-view /> + <Toaster> for toast notifications
│   ├── style.css                 # Tailwind CSS v4 entry + dark-only command-center CSS variables (oklch)
│   │
│   ├── lib/
│   │   ├── darkTheme.js          # Forces root .dark class and color-scheme during bootstrap
│   │   └── utils.js              # cn() utility combining clsx + tailwind-merge for shadcn class merging
│   │
│   ├── config/
│   │   └── navigation.js         # getNavigationContext() — computes sidebar links by role & support mode
│   │
│   ├── router/
│   │   └── index.js              # Vue Router config + navigation guard (auth + role + support mode)
│   │
│   ├── services/
│   │   └── api.js                # Axios instance: base URL, JWT interceptor, 401 handler
│   │
│   ├── stores/
│   │   ├── auth.js               # Pinia store: token, user, activeTenantId, login, switch, logout + tenant settings cache
│   │   └── i18n.js               # Pinia store: locale, catalog, t(), loadCatalog()
│   │
│   ├── i18n/
│   │   ├── public.json           # Pre-auth translation strings (en/es for login page)
│   │   └── usePublicI18n.js      # Composable: locale, setLocale, t() — persists localStorage
│   │

│   ├── test-utils/
│   │   └── renderWithApp.js      # Test helper: mounts components with Pinia + Router for integration tests
│   │
│   ├── components/
│   │   ├── DashboardLayout.vue           # Shared shell: compact sidebar, mobile nav, locale controls, user card
│   │   ├── PageHeader.vue               # Consistent page title + description + actions slot
│   │   ├── InlineAlert.vue              # Inline info/success/error message component
│   │   ├── StatusBadge.vue              # Status indicator badge (active, inactive, expired, cancelled, neutral)
│   │   ├── EmptyState.vue               # Empty data placeholder with title, description, and actions slot
│   │   ├── LoadingBlock.vue             # Centered loading indicator
│   │   ├── SummaryMetric.vue            # Command-center metric card
│   │   ├── EntityInspector.vue          # Selected entity detail inspector
│   │   ├── ImpactConfirmDialog.vue      # Destructive confirmation with impact summary
│   │   ├── catalogDeletePreview.js      # Delete-confirmation validation and preview helpers (JS module)
│   │   ├── CatalogPanel.vue             # Service + plan CRUD panel
│   │   ├── ClientManagementPanel.vue    # Client CRUD panel with forms
│   │   ├── CodeServicesGlobalPanel.vue  # Master global code-service toggles
│   │   ├── CodeServicesTenantPanel.vue  # Tenant code-service selection panel
│   │   ├── MailboxConfigPanel.vue       # Mailbox config (IMAP/OAuth) panel
│   │   ├── subscriptions/               # Subscription page sub-components
│   │   │   ├── SubscriptionTable.vue
│   │   │   ├── SubscriptionModal.vue
│   │   │   ├── SubscriptionRenewModal.vue
│   │   │   ├── SubscriptionReactivateModal.vue
│   │   │   ├── SubscriptionCancelModal.vue
│   │   │   ├── SubscriptionFilters.vue
│   │   │   └── ReminderSettingsModal.vue
│   │   │
│   │   ├── ui/                          # shadcn-vue UI primitives (generated/wrapped)
│   │   │   ├── badge/
│   │   │   ├── button/
│   │   │   ├── card/
│   │   │   ├── checkbox/
│   │   │   ├── dialog/
│   │   │   ├── dropdown-menu/
│   │   │   ├── input/
│   │   │   ├── select/
│   │   │   ├── separator/
│   │   │   ├── sheet/
│   │   │   ├── sonner/
│   │   │   ├── switch/
│   │   │   ├── table/
│   │   │   ├── tabs/
│   │   │   └── textarea/
│   │   │
│   │   └── __tests__/                   # Component-level tests
│   │       ├── DashboardLayout.spec.js
│   │       ├── PageHeader.spec.js
│   │       ├── StatusBadge.spec.js
│   │       └── catalogDeletePreview.spec.js
│   │
│   ├── styles/                          # Legacy styles (kept for ClientDashboardView)
│   │   ├── client-dashboard.css
│   │   └── client-dashboard-responsive.css
│   │
│   └── views/
│       ├── LoginView.vue                # Login form (i18n-backed UI)
│       ├── MasterDashboardView.vue      # Master tenant CRUD + support context switch
│       ├── MasterCodeServicesView.vue   # Global code-service activation toggles
│       ├── TenantDashboardView.vue      # Tenant navigation hub (card grid)
│       ├── TenantClientsView.vue        # Client CRUD page
│       ├── TenantCatalogView.vue        # Service + plan CRUD page
│       ├── SubscriptionsView.vue        # Subscription CRUD table + modals
│       ├── TenantMailboxView.vue        # Mailbox configuration page
│       ├── TenantCodeServicesView.vue   # Per-tenant code-service selection
│       ├── TenantSettingsView.vue       # Tenant profile + password + reminder settings
│       ├── ClientDashboardView.vue      # Client readonly dashboard + password change
│       │
│       └── __tests__/                   # View-level integration tests
│           ├── LoginView.spec.js
│           ├── RoleDashboards.spec.js
│           ├── SubscriptionsView.spec.js
│           ├── TenantMailboxView.spec.js
│           ├── TenantSectionViews.spec.js
│           └── TenantSettingsView.spec.js
│
└── dist/                         # Build output (gitignored)
```

## Entry Points

| File | Purpose |
|------|---------|
| `index.html` | HTML shell, loads `/src/main.js` as module |
| `src/main.js` | Creates Vue app, registers Pinia + Router, preloads i18n catalog if authenticated, mounts to `#app` |
| `src/App.vue` | Root component rendering `<router-view />` + `<Toaster>` for toasts |

## Module Responsibilities

| Module | Files | Responsibility |
|--------|-------|----------------|
| Router | `router/index.js` | Route definitions, lazy loading, navigation guard for auth + role + support mode; `/admin/*` routes for tenant workflow pages; redirects for legacy dashboard paths |
| Navigation Config | `config/navigation.js` | Computes sidebar link items based on role and support mode |
| API Service | `services/api.js` | Axios singleton, JWT injection on requests, 401 auto-logout |
| Auth Store | `stores/auth.js` | Login/logout/switch actions, token/user/active tenant persistence in localStorage, tenant settings cache with deduplication |
| I18n Store | `stores/i18n.js` | Fetches catalog from backend, locale state, `t(key, params)` resolver |
| Public I18n | `i18n/usePublicI18n.js` | Pre-auth i18n composable with local JSON catalog, persists locale to localStorage |
| Dark Theme | `lib/darkTheme.js` | Forces dark-only root class, color-scheme, and `localStorage.theme = dark` |
| UI Primitives | `components/ui/*` | shadcn-vue components built on Reka UI + Tailwind CSS v4 |
| Shared Components | `components/*.vue` | `DashboardLayout`, `PageHeader`, `InlineAlert`, `StatusBadge`, `EmptyState`, `LoadingBlock`, `SummaryMetric`, `EntityInspector`, `ImpactConfirmDialog` |
| Business Components | `components/{Catalog,ClientManagement,CodeServices*,MailboxConfig}Panel.vue` | Reusable business panels extracted from views |
| Subscription Components | `components/subscriptions/*.vue` | Subscription table, modals, and filters |
| Views | `views/*.vue` | Page-level components: login, master pages, tenant workflow pages, subscriptions page, client dashboard |

## Dependencies (from package.json)

| Package | Type | Purpose |
|---------|------|---------|
| `vue` ^3.5.34 | dependency | Reactive UI framework |
| `pinia` ^3.0.4 | dependency | State management |
| `vue-router` ^4.6.4 | dependency | Client-side routing |
| `axios` ^1.16.0 | dependency | HTTP client with interceptors |
| `reka-ui` ^2.9.10 | dependency | Headless UI primitives (dialog, dropdown, sheet, etc.) |
| `vue-sonner` ^2.0.9 | dependency | Toast notifications |
| `@tanstack/vue-table` ^8.21.3 | dependency | Table sorting/filtering |
| `class-variance-authority` ^0.7.1 | dependency | UI variant utilities |
| `clsx` ^2.1.1 | dependency | Class name merging |
| `tailwind-merge` ^3.6.0 | dependency | Tailwind class conflict resolution |
| `lucide-vue-next` ^1.0.0 | dependency | Icon library |
| `@lucide/vue` ^1.17.0 | dependency | Icon library (alt) |
| `@vueuse/core` ^14.3.0 | dependency | Vue composition utilities |
| `tw-animate-css` ^1.4.0 | dependency | CSS animation utilities for Tailwind |
| `@vitejs/plugin-vue` ^6.0.6 | devDependency | Vite plugin for Vue SFC compilation |
| `@tailwindcss/vite` ^4.3.0 | devDependency | Tailwind CSS v4 Vite plugin |
| `tailwindcss` ^4.3.0 | devDependency | Utility-first CSS framework |
| `vite` ^8.0.12 | devDependency | Build tool and dev server |
| `vitest` ^4.1.8 | devDependency | Test runner |
| `@vue/test-utils` ^2.4.11 | devDependency | Vue component testing utilities |
| `jsdom` ^29.1.1 | devDependency | DOM environment for tests |

## Scripts

| Command | Action |
|---------|--------|
| `npm run dev` | Start Vite dev server with HMR |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Preview production build locally |
| `npm test` | Run Vitest test suite |
