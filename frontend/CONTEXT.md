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
| **Tenant Admin** | The person who operates a Tenant through the plan-aware administrative Web and WhatsApp interfaces. Use **Tenant** for the business entity, not the person. |
| **Master Layout** | Sidebar layout for the Master operator, with summary cards and separate production-business and Demo Tenant management tabs. |
| **Demo Management Tab** | Master-only lifecycle view for creating Starter or Pro Demo Tenants, credentialing, monitoring, and deleting them without entering their Demo Workspaces. It excludes prospect activity, workspace telemetry, summary cards, and Demo Tenants from production metrics. |
| **Admin Layout** | Layout colapsable con sidebar para tenant admin. Navegación: Dashboard, Clients, Catalog, Subscriptions, Settings, and the gated Help Center. Starter oculta links Pro-only. Master en contexto de soporte ve navegación completa + banner, pero no Tenant Admin Help. Contextual Help uses stable targets `admin.clients`, `admin.catalog`, and `admin.subscriptions` on the Pro screens without submitting their forms. |

| **Demo Account** | Prospect-facing label for a Demo Tenant (`Cuenta de demostración` / `Demo account`). Avoid the internal word Tenant in prospect-facing copy. |
| **Demo Banner** | Persistent Admin Layout notice that identifies a Demo Account and its immutable Starter or Pro plan, shows its remaining time, explains browser-local data, and links to Demo Reset. |
| **Demo Ended Page** | Public bilingual page shown when a demo expires or the Master removes it. It explains that the demo is unavailable and offers WhatsApp, Telegram, and email contact paths. |
| **Demo Lifecycle Heartbeat** | Minute-level lifecycle check carrying no business data. It closes ended demos, enforces credential replacement, and pauses interaction after two consecutive unverifiable checks. |
| **Demo Baseline** | The canonical, plan-aware PII-free dataset restored by Demo Reset. Pro includes 5 Clients, 3 generic Services, and 8 Subscriptions spanning the supported lifecycle states; Starter includes a business profile, fixed connected Demo Mailbox and Demo WhatsApp Instance, 3 enabled code services, and 2 blocked identities. Dates derive from demo activation and the initial locale is English. |
| **Demo Integration** | In-product representation of an external integration that accepts no provider credentials and sends no traffic outside TrackPal. |
| **Demo Workspace** | One browser's independent, evaluation-long copy of the Demo Baseline and subsequent business changes. It starts with the Master-provided business name, remains separate from backend and other browsers, and is removed when the demo ends. |
| **Demo CRUD** | Pro Demo Account's browser-local Clients, Catalog, and Subscriptions behavior with production-equivalent UI, validation, lifecycle rules, and confirmations. |
| **Demo Client** | Browser-local Client that participates in Demo CRUD, Subscriptions, and the simulated Client Console but has no backend identity or portal login. |
| **Demo Console Simulator** | Plan-aware WhatsApp simulation page. Starter exposes only the landing-style access-code request triggered by `code`, `código`, or `codigo`; Pro uses the current Demo Workspace to reproduce the full production Client and Pro Tenant Admin Consoles, including `0`/`8`/`9` navigation. |
| **Demo Reset** | Prospect-initiated restoration of one Demo Workspace to the Demo Baseline. It preserves credentials, evaluation time, and the selected plan's tour completion, and cannot be invoked remotely by the Master. |
| **Demo Mailbox** | Fixed connected mailbox representation that powers simulated code lookup without exposing connection or credential controls. |
| **Demo WhatsApp Instance** | Fixed connected WhatsApp representation linked to the Demo Console Simulator, with no QR, pairing, disconnect, or real Evolution instance. |
| **Settings Page** | Superficie de configuración del tenant admin. Usa navegación por categorías con un único panel activo para editar una sección a la vez; en móvil la selección de categoría se abre desde un drawer. El panel activo usa scroll interno para secciones largas e incluye una acción común de Cancelar que cierra la sección y descarta cambios locales no guardados. |
| **My Account** | User-facing name for the selected Tenant business profile and data surfaces (`Mi cuenta` / `My account`). Tenant Admin sees Profile, Security, and Data tabs; Master Support Context uses the same label for the selected business but omits Security and self-service deletion. It never refers to the authenticated Master's own identity; keep **Tenant** as the internal domain term and avoid exposing that jargon in UI copy. |
| **Client Layout** | Layout con sidebar para cliente final. Navegación: Dashboard, Profile. |
| **Auth Store** | Zustand store for tokens, user, active tenant, production plan hint, immutable Demo Account lifecycle metadata, selected production/Demo data-source adapter, and distinguishable authentication outcomes. Auth metadata is persisted separately from the browser-local Demo Workspace. |
| **Catalog Store** | Cache de servicios, planes y clientes con dedup de requests en vuelo. |
| **Settings Store** | Cache de configuración de tenant, recordatorios, timezones, mailbox y Public API Key. |
| **Gmail Setup Assistant** | Two-step Settings experience for connecting the Central Lookup Mailbox. Step 1 guides the Tenant Admin to create a Google app password at myaccount.google.com/apppasswords. Step 2 collects the Gmail address and app password. An optional **Google Connection** alternative may appear behind the `VITE_GMAIL_OAUTH_CONNECT_ENABLED` gate. Avoid exposing **IMAP**, server, port, or SSL terminology. |
| **App Password** | Customer-facing name for the Google-generated, revocable credential used by the Gmail Setup Assistant. It is never the user's primary Google Account password. |
| **Public API Section** | Sección Pro-only dentro de Settings donde el tenant gestiona su Public API Key y Allowed Origins para publicar el catálogo en frontends externos. En UI para tenants usa “Clave API” en español y “API Key” en inglés. El tooltip `?` dice: “La Clave API permite que tu sitio web muestre automáticamente los servicios y planes de tu catálogo. Compártela solo con tu desarrollador o con la persona que administra tu web.” La creación de la clave pide al menos un sitio web autorizado primero. Una vez creada, la clave se muestra oculta por defecto con acciones para mostrarla y copiarla. La ayuda “Para tu desarrollador” muestra ejemplos frontend en tabs separados para HTML + JavaScript, React, Vue, Svelte, Angular y Alpine.js; aclara que se debe elegir según la tecnología del sitio web y que la Clave API funciona desde el navegador solo en sitios autorizados. The section calls `/public-api-key` management endpoints, stores state in `Settings Store`, and is hidden for Starter tenant admins outside Master support context. Pro Demo Accounts see the capability and explanation with disabled key and origin controls; Starter Demo Accounts retain the normal plan gate. |
| **Allowed Origin** | Origin web exacto permitido para usar la Public API Key desde navegador. En UI para tenants se presenta como sitio web autorizado y se edita con una lista editable: campo de URL, botón para agregar sitio web y botón para eliminar cada sitio. La Public API Section también tiene una zona de peligro con el botón “Eliminar Clave API” para borrar la clave completa y desactivar el catálogo público. |
| **Public I18n** | Hook `usePublicI18n()` para pre-auth (login). Catálogo local en `public.json`. |
| **Privacy Policy** | Public document explaining how TrackPal handles personal data and privacy responsibilities. |
| **Terms of Service** | Public document defining the conditions and responsibilities for using TrackPal. |
| **Legal Footer** | Public surface that identifies TrackPal and exposes the Privacy Policy and Terms of Service destinations. |
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
| `/admin/demo/simulator` | `DemoWhatsappSimulator` | Demo `tenant` only | Starter Request; Pro Request + Operation |
| `/admin/help` | `HelpCenterPage` | `tenant` | `VITE_PRIVATE_HELP_ENABLED=true` |
| `/demo-ended` | `DemoEndedPage` | Public | — |
| `/client/dashboard` | `ClientDashboard` | `client` | — |
| `/client/profile` | `ProfilePage` | `client` | — |
| `/client/help` | `HelpCenterPage` | `client` | `VITE_PRIVATE_HELP_ENABLED=true` |

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
| **Phone Search** | Access Control lookup criterion that matches blocked phone identities by a partial sequence of digits. It does not match identities represented only by a WhatsApp LID. |
| **PublicApiSection** | Sección en Settings para crear, mostrar, regenerar y revocar la Public API Key, y para editar Allowed Origins. Disponible para Pro y Master Support Context. |
| **WhatsappLinkSection** | Sección en Settings para que el tenant vincule, consulte y desconecte su instancia WhatsApp. Disponible para Starter, Pro y Master Support Context si la instancia Evolution está configurada. |

### Product Labels (UI)
- **Plataformas habilitadas**: code services seleccionados por tenant
- **Correo central de búsqueda**: cuenta Gmail del negocio conectada para extracción de códigos
- **Control de acceso**: bloqueo/desbloqueo de identidades WhatsApp
- **API pública de catálogo**: publicación read-only del catálogo para sitios externos
