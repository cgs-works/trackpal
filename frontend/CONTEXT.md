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
| **Settings Page** | Superficie de configuración del tenant admin. Usa navegación por categorías con un único panel activo para editar una sección a la vez; en móvil la selección de categoría se abre desde un drawer. El panel activo usa scroll interno para secciones largas e incluye una acción común de Cancelar que cierra la sección y descarta cambios locales no guardados. |
| **Client Layout** | Layout con sidebar para cliente final. Navegación: Dashboard, Profile. |
| **Auth Store** | Zustand store: token, refreshToken, user, activeTenantId, tenantPlan. Persistido en localStorage. `tenantPlan` es UI hint corregido por dashboard responses. |
| **Catalog Store** | Cache de servicios, planes y clientes con dedup de requests en vuelo. |
| **Settings Store** | Cache de configuración de tenant, recordatorios, timezones, mailbox y Public API Key. |
| **Public API Section** | Sección Pro-only dentro de Settings donde el tenant gestiona su Public API Key y Allowed Origins para publicar el catálogo en frontends externos. En UI para tenants usa “Clave API” en español y “API Key” en inglés. El tooltip `?` dice: “La Clave API permite que tu sitio web muestre automáticamente los servicios y planes de tu catálogo. Compártela solo con tu desarrollador o con la persona que administra tu web.” La creación de la clave pide al menos un sitio web autorizado primero. Una vez creada, la clave se muestra oculta por defecto con acciones para mostrarla y copiarla. La ayuda “Para tu desarrollador” muestra ejemplos frontend en tabs separados para HTML + JavaScript, React, Vue, Svelte, Angular y Alpine.js; aclara que se debe elegir según la tecnología del sitio web y que la Clave API funciona desde el navegador solo en sitios autorizados. The section calls `/public-api-key` management endpoints, stores state in `Settings Store`, and is hidden for Starter tenant admins outside Master support context. |
| **Allowed Origin** | Origin web exacto permitido para usar la Public API Key desde navegador. En UI para tenants se presenta como sitio web autorizado y se edita con una lista editable: campo de URL, botón para agregar sitio web y botón para eliminar cada sitio. La Public API Section también tiene una zona de peligro con el botón “Eliminar Clave API” para borrar la clave completa y desactivar el catálogo público. |
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
| **AccessControlSection** | Sección en Settings para listar/bloquear/desbloquear identidades de WhatsApp. Disponible tanto para Starter como Pro. La lista visible se pagina en grupos de 10 bloqueos. |
| **PublicApiSection** | Sección en Settings para crear, mostrar, regenerar y revocar la Public API Key, y para editar Allowed Origins. Disponible para Pro y Master Support Context. |
| **WhatsappLinkSection** | Sección en Settings para que el tenant vincule, consulte y desconecte su instancia WhatsApp. Disponible para Starter, Pro y Master Support Context si la instancia Evolution está configurada. |

### Product Labels (UI)
- **Plataformas habilitadas**: code services seleccionados por tenant
- **Correo central de búsqueda**: mailbox del tenant para extracción de códigos
- **Control de acceso**: bloqueo/desbloqueo de identidades WhatsApp
- **API pública de catálogo**: publicación read-only del catálogo para sitios externos
