# Frontend Codebase Structure

```
frontend/
├── index.html                    # HTML entry point, mounts #app
├── package.json                  # Dependencies: react 19, zustand, tanstack router
├── tsconfig.json                 # TypeScript config with @/ path alias
├── tsconfig.app.json             # App-specific TS config (strict mode)
├── vite.config.ts                # Vite config: react, tailwind, tanstack router plugin
├── .env.example                  # VITE_API_URL template
│
├── public/
│   ├── favicon.svg               # Trackpal logo (purple gradient)
│   ├── icons.svg                 # Social media icon sprite
│   └── _redirects                # Cloudflare Pages SPA fallback: /* /index.html 200
│
├── src/
│   ├── main.tsx                  # App bootstrap: React DOM createRoot, render <App />
│   ├── App.tsx                   # RouterProvider + QueryClientProvider setup
│   ├── index.css                 # Global Tailwind styles
│   │
│   ├── routes/                   # TanStack Router file-based routes
│   │   ├── __root.tsx            # Root layout: i18n loading, Toaster, devtools
│   │   ├── index.tsx             # Index redirect by role
│   │   ├── login.tsx             # Login page route
│   │   ├── master.tsx            # Master layout route
│   │   ├── admin.tsx             # Admin layout route
│   │   ├── client.tsx            # Client layout route
│   │   ├── master/
│   │   │   └── dashboard.tsx     # Master dashboard route
│   │   ├── admin/
│   │   │   ├── dashboard.tsx     # Tenant dashboard route
│   │   │   ├── clients.tsx       # Client management route (Pro-only, wrapped in PlanRouteGate)
│   │   │   ├── catalog.tsx       # Catalog management route (Pro-only, wrapped in PlanRouteGate)
│   │   │   ├── subscriptions.tsx # Subscriptions route (Pro-only, wrapped in PlanRouteGate)
│   │   │   └── settings.tsx      # Settings route
│   │   └── client/
│   │       ├── dashboard.tsx     # Client dashboard route
│   │       └── profile.tsx       # Client profile route
│   ├── routeTree.gen.ts          # Auto-generated route tree (DO NOT EDIT)
│   │
│   ├── store/                    # Zustand stores
│   │   ├── auth.ts               # Auth: token, user, tenantPlan, isMasterSupportContext, login/logout/switchTenant/setTenantPlan
│   │   ├── catalog.ts            # Cache: services, plans, clients with dedup
│   │   └── settings.ts           # Cache: tenant/reminder settings, timezones, mailbox
│   │
│   ├── lib/                      # Shared utilities
│   │   ├── api.ts                # Axios singleton: base URL, JWT interceptor, 401 handler
│   │   └── utils.ts              # cn() helper (clsx + tailwind-merge)
│   │
│   ├── i18n/                     # Internationalization
│   │   ├── index.ts              # Backend catalog: loadCatalog(), t(), getLocale()
│   │   ├── public.json           # Pre-auth translations (en/es for login)
│   │   └── public.ts             # usePublicI18n() hook for pre-auth views
│   │
│   ├── components/               # Shared UI components
│   │   ├── layout/
│   │   │   ├── app-sidebar.tsx   # Reusable sidebar (desktop + mobile)
│   │   │   └── sidebar-nav.tsx   # Nav item component
│   │   └── ui/                   # shadcn/ui components
│   │       ├── alert.tsx
│   │       ├── alert-dialog.tsx
│   │       ├── badge.tsx
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── dialog.tsx
│   │       ├── dropdown-menu.tsx
│   │       ├── input.tsx
│   │       ├── label.tsx
│   │       ├── select.tsx
│   │       ├── separator.tsx
│   │       ├── sheet.tsx
│   │       ├── skeleton.tsx
│   │       ├── sonner.tsx
│   │       ├── switch.tsx
│   │       └── table.tsx
│   │
│   └── features/                 # Feature modules (by role/domain)
│       ├── auth/
│       │   ├── components/
│       │   │   └── login-form.tsx
│       │   └── services/
│       │       └── auth-api.ts   # TenantPlan type, TokenResponse with tenant_plan
│       │
│       ├── admin/                # Tenant admin feature
│       │   ├── layout/
│       │   │   └── admin-layout.tsx  # Plan-aware nav items, support banner
│       │   ├── components/
│       │   │   ├── dashboard-page.tsx        # Plan-aware metrics, tenantPlan correction
│       │   │   ├── plan-route-gate.tsx       # Pro-only route guard component
│       │   │   ├── support-banner.tsx        # Master support context alert
│       │   │   ├── not-found-page.tsx        # 404 for blocked Pro routes
│       │   │   ├── clients-page.tsx
│       │   │   ├── client-table.tsx
│       │   │   ├── client-form-dialog.tsx
│       │   │   ├── client-delete-dialog.tsx
│       │   │   ├── catalog-page.tsx
│       │   │   ├── subscriptions-page.tsx
│       │   │   ├── subscription-table.tsx
│       │   │   ├── subscription-form-dialog.tsx
│       │   │   ├── subscription-lifecycle-dialog.tsx
│       │   │   ├── subscription-renew-dialog.tsx
│       │   │   ├── settings-page.tsx         # Plan-aware section visibility
│       │   │   ├── profile-section.tsx
│       │   │   ├── password-section.tsx
│       │   │   ├── locale-section.tsx
│       │   │   ├── timezone-section.tsx
│       │   │   ├── timezone-picker.tsx
│       │   │   ├── reminder-settings-modal.tsx
│       │   │   ├── code-services-section.tsx  # Plan-aware labels
│       │   │   ├── access-control-section.tsx # WhatsApp access blocks UI
│       │   │   └── mailbox-section.tsx        # Plan-aware labels
│       │   └── services/
│       │       ├── client-api.ts
│       │       ├── catalog-api.ts
│       │       ├── subscription-api.ts
│       │       ├── settings-api.ts
│       │       ├── reminder-api.ts
│       │       ├── dashboard-api.ts           # getTenantDashboard() with plan
│       │       └── access-control-api.ts      # list/create/delete access blocks
│       │
│       ├── master/               # Master admin feature
│       │   ├── layout/
│       │   │   └── master-layout.tsx
│       │   ├── components/
│       │   │   ├── dashboard-page.tsx
│       │   │   ├── business-table.tsx         # Plan badge per tenant
│       │   │   ├── business-form-dialog.tsx   # Plan selector (Starter/Pro)
│       │   │   ├── code-services-dialog.tsx
│       │   │   ├── delete-confirm-dialog.tsx
│       │   │   ├── empty-state.tsx
│       │   │   └── summary-cards.tsx
│       │   └── services/
│       │       └── tenant-api.ts
│       │
│       └── client/               # Client-facing feature
│           ├── layout/
│           │   └── client-layout.tsx
│           ├── components/
│           │   ├── dashboard-page.tsx
│           │   └── profile-page.tsx
│           └── services/
│               └── client-dashboard-api.ts
│
└── dist/                         # Build output (gitignored)
```

## Entry Points

| File | Purpose |
|------|---------|
| `index.html` | HTML shell, loads `/src/main.tsx` |
| `main.tsx` | Creates React root, renders `<App />` |
| `App.tsx` | Sets up `QueryClientProvider` + `RouterProvider` with generated route tree |
| `routeTree.gen.ts` | Auto-generated by `@tanstack/router-plugin` — DO NOT edit manually |

## Module Responsibilities

| Module | Files | Responsibility |
|--------|-------|----------------|
| Routes | `routes/*.tsx` | Route definitions, layout wrappers, page components |
| Auth Store | `store/auth.ts` | Login/logout/switch, token/user/plan persistence, cache clearing |
| Catalog Store | `store/catalog.ts` | Services/plans/clients cache with dedup + invalidation |
| Settings Store | `store/settings.ts` | Tenant/reminder settings, timezones, mailbox cache with dedup |
| API Client | `lib/api.ts` | Axios singleton, JWT injection, 401 auto-logout |
| I18n | `i18n/index.ts` | Backend catalog loading, `t()` key resolver |
| Public I18n | `i18n/public.ts` | Pre-auth i18n with local JSON catalog |
| UI Components | `components/ui/` | shadcn/ui primitives (Radix-based) |
| Layout | `components/layout/` | Reusable sidebar, nav items |
| Feature Modules | `features/*/` | Role-specific pages, components, and API services |

## Dependencies (from package.json)

| Package | Purpose |
|---------|---------|
| `react` ^19.2.6 | UI framework |
| `react-dom` ^19.2.6 | DOM renderer |
| `zustand` ^5.0.14 | State management |
| `@tanstack/react-router` ^1.170.15 | Client-side routing |
| `@tanstack/react-query` ^5.101.0 | Async state management (QueryClient) |
| `axios` ^1.17.0 | HTTP client with interceptors |
| `tailwindcss` ^4.3.0 | Utility-first CSS framework |
| `@tailwindcss/vite` ^4.3.0 | Vite plugin for Tailwind |
| `shadcn` ^4.11.0 | Component generator for Radix-based UI |
| `lucide-react` ^1.17.0 | Icon library |
| `sonner` ^2.0.7 | Toast notifications |
| `next-themes` ^0.4.6 | Theme management (dark/light) |
| `class-variance-authority` ^0.7.1 | Component variant utility |
| `clsx` ^2.1.1 | Conditional classnames |
| `tailwind-merge` ^3.6.0 | Tailwind class deduplication |
| `@tanstack/router-plugin` ^1.168.18 | File-based route generation |
| `@tanstack/router-devtools` ^1.167.0 | Route devtools (dev only) |

## Dev Dependencies

| Package | Purpose |
|---------|---------|
| `typescript` ~6.0.2 | Type checking |
| `vite` ^8.0.12 | Build tool and dev server |
| `@vitejs/plugin-react` ^6.0.1 | Vite plugin for React |
| `eslint` ^10.3.0 | Linting |
| `eslint-plugin-react-hooks` ^7.1.1 | React hooks lint rules |
| `eslint-plugin-react-refresh` ^0.5.2 | Fast refresh lint rules |
