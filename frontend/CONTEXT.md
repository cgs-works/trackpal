# Frontend Context

## Stack

- React 19 con hooks (sin class components)
- TypeScript estricto (`tsconfig.app.json`)
- Zustand para state management
- TanStack Router para routing basado en archivos
- Tailwind CSS v4 via plugin Vite
- shadcn/ui (basado en Radix) para componentes
- Axios con interceptores JWT
- Vite como build tool

## Vocabulario de dominio

| Término | Definición |
|---------|------------|
| **Master Layout** | Layout con sidebar para el operador Master. Muestra summary cards y business table. |
| **Admin Layout** | Layout colapsable con sidebar para tenant admin. Navegación: Dashboard, Clients, Catalog, Subscriptions, Settings. Starter oculta links Pro-only. Master en contexto de soporte ve navegación completa + banner. |
| **Client Layout** | Layout con sidebar para cliente final. Navegación: Dashboard, Profile. |
| **Auth Store** | Zustand store: token, refreshToken, user, activeTenantId, tenantPlan. Persistido en localStorage. `tenantPlan` es UI hint corregido por dashboard responses. |
| **Catalog Store** | Cache de servicios, planes y clientes con dedup de requests en vuelo. |
| **Settings Store** | Cache de configuración de tenant, recordatorios, timezones y mailbox. |
| **Public I18n** | Hook `usePublicI18n()` para pre-auth (login). Catálogo local en `public.json`. |
| **Backend I18n** | Catálogo servido via `GET /api/v1/i18n/catalog`. Función `t(key, params?)`. |
| **Path Alias** | `@/` mapea a `src/` (configurado en tsconfig + vite). |

## Estructura de features

```
features/
├── auth/           # Login (público, pre-auth i18n)
├── admin/          # Tenant admin: dashboard, clients, catalog, subscriptions, settings
├── master/         # Master: dashboard, business table, code services
└── client/         # Cliente: dashboard (read-only), profile
```

Cada feature tiene:
- `layout/` — wrapper de layout
- `components/` — páginas y secciones
- `services/` — funciones API tipadas

## Routing

File-based routing via `@tanstack/router-plugin`. Árbol auto-generado en `src/routeTree.gen.ts` (NO editar manualmente).

| Ruta | Componente | Rol | Plan Gate |
|------|-----------|-----|----------|
| `/login` | `LoginForm` | Público | — |
| `/` | Redirect por rol | Autenticado | — |
| `/master/dashboard` | `MasterDashboard` | `master` | — |
| `/admin/dashboard` | `DashboardPage` | `tenant` | — |
| `/admin/clients` | `ClientsPage` | `tenant` | Pro-only |
| `/admin/catalog` | `CatalogPage` | `tenant` | Pro-only |
| `/admin/subscriptions` | `SubscriptionsPage` | `tenant` | Pro-only |
| `/admin/settings` | `SettingsPage` | `tenant` | — |
| `/client/dashboard` | `ClientDashboard` | `client` | — |
| `/client/profile` | `ProfilePage` | `client` | — |

Rutas Pro-only usan `PlanRouteGate` wrapper. Starter tenant admin ve 404 en estas rutas. Master en contexto de soporte bypass el gate.

## State Management (Zustand)

### Patrón de dedup de requests en vuelo

```ts
loadData: async () => {
  const state = get();
  if (state.loaded) return state.data;
  if (state.inFlight) return state.inFlight;
  const promise = apiCall();
  set({ inFlight: promise });
  // ...
}
```

### Invalidación de cache

- Login/logout/switchTenant → limpia todos los stores
- CRUD operations → invalidan el cache específico

## I18n

- **Pre-auth**: `usePublicI18n()` con catálogo local (`public.json`)
- **Post-auth**: `t(key, params?)` con catálogo del backend
- **Catálogo se carga**: en refresh de página, en login, en cambio de locale
- **No hardcodear strings traducidos** — todo viene del catálogo

## API Client

Axios singleton en `src/lib/api.ts`:
- Base URL: `VITE_API_URL` o fallback `http://localhost:8000/api/v1`
- Request interceptor: `Authorization: Bearer <token>`
- Response interceptor: 401 → limpiar auth + redirect a `/login`

## Styling

- Tailwind CSS v4 utility classes
- `cn()` helper: `clsx` + `tailwind-merge`
- shadcn/ui components en `src/components/ui/`
- Responsive: mobile-first con `md:` breakpoint
- Geist Variable como font display/body/label
- Tokens OKLCH en `index.css` (extender ahí, no colores raw)

## Starter/Pro Product Split

| Término | Definición |
|---------|------------|
| **TenantPlan** | `"starter" | "pro" | null`. Persistido en auth store, corregido por dashboard. UI hint solamente; backend es source of truth para autorización. |
| **PlanRouteGate** | Componente wrapper para rutas Pro-only. Starter tenant admin ve `NotFoundPage`. Master support bypass. |
| **SupportBanner** | Alert visible cuando Master está en contexto de soporte (switched a un Starter tenant). Indica que la UI completa es visible solo para soporte. |
| **Master Support Context** | `role === "master" && activeTenantId !== null`. Master ve UI admin completa + banner, sin restricciones de plan. |
| **AccessControlSection** | Sección en Settings para listar/bloquear/desbloquear identidades de WhatsApp. Disponible tanto para Starter como Pro. |

### Product Labels (UI)
- **Plataformas habilitadas**: code services seleccionados por tenant
- **Correo central de búsqueda**: mailbox del tenant para extracción de códigos
- **Control de acceso**: bloqueo/desbloqueo de identidades WhatsApp
