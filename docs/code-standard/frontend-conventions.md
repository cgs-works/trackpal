# Frontend Coding Conventions

## Language & Runtime

- **TypeScript** (strict mode via `tsconfig.app.json`)
- **React 19** with hooks (no class components)
- **Node.js** managed via `package.json`, lockfile `package-lock.json`

## Project Structure

- `src/routes/` — TanStack Router file-based routes (auto-generated tree)
- `src/store/` — Zustand stores (one file per domain)
- `src/lib/` — Shared utilities (api client, cn helper)
- `src/i18n/` — Internationalization module
- `src/components/ui/` — shadcn/ui primitives
- `src/components/layout/` — Shared layout components
- `src/features/` — Feature modules organized by role/domain

## Naming

| Artifact | Convention | Example |
|----------|-----------|---------|
| Files (components) | kebab-case | `clients-page.tsx`, `timezone-picker.tsx` |
| Files (services/utils) | kebab-case | `client-api.ts`, `auth-api.ts` |
| Files (stores) | kebab-case | `auth.ts`, `catalog.ts`, `settings.ts` |
| React components | PascalCase | `ClientsPage`, `TimezonePicker` |
| Zustand stores | `use<Name>Store` | `useAuthStore`, `useCatalogStore` |
| Route files | kebab-case | `admin/dashboard.tsx`, `client/profile.tsx` |
| API service functions | camelCase | `listClients()`, `getMailbox()` |
| Types/interfaces | PascalCase | `Client`, `SubscriptionFilters` |
| Path alias | `@/` | `@/store/auth`, `@/lib/api` |
| Environment variables | `VITE_UPPER_SNAKE_CASE` | `VITE_API_URL` |

## React Component Patterns

### Functional components only

All components are functional with hooks. No class components.

### File organization

Each feature component is a single file exporting one component:

```tsx
// features/admin/components/locale-section.tsx
export function LocaleSection() {
  // ...
}
```

### Hooks ordering

1. Store hooks (`useAuthStore`, `useSettingsStore`, etc.)
2. Local state (`useState`)
3. Derived state (`useMemo`, `computed`)
4. Side effects (`useEffect`)
5. Callbacks (`useCallback`)
6. Event handlers

### Controlled forms

Forms use controlled inputs with `useState`:

```tsx
const [email, setEmail] = useState("");

<Input
  id="email"
  type="email"
  value={email}
  onChange={(e) => setEmail(e.target.value)}
/>
```

## I18n Conventions

### No hardcoded translated strings

All UI text comes from the backend catalog via `t(key)` from `@/i18n`.

### Usage

```tsx
import { t } from "@/i18n";

// Simple key
<h1>{t("frontend.settings.title")}</h1>

// With params
<p>{t("frontend.clients.activated", { name: client.full_name })}</p>
```

### Pre-auth i18n

Login page uses `usePublicI18n()` from `@/i18n/public` (local JSON catalog):

```tsx
import { usePublicI18n } from "@/i18n/public";
const { t } = usePublicI18n();
```

### Catalog loading

- On page refresh: root route loads catalog before rendering
- On login: `login()` action loads catalog
- On locale change: component calls `loadCatalog()` after save

## State Management (Zustand)

### Store creation

```ts
import { create } from "zustand";

interface MyState {
  data: Data[];
  loaded: boolean;
  inFlight: Promise<Data[]> | null;
  loadData: () => Promise<Data[]>;
}

export const useMyStore = create<MyState>((set, get) => ({
  data: [],
  loaded: false,
  inFlight: null,
  loadData: async () => {
    const state = get();
    if (state.loaded) return state.data;
    if (state.inFlight) return state.inFlight;
    const promise = fetchData();
    set({ inFlight: promise });
    const data = await promise;
    set({ data, loaded: true, inFlight: null });
    return data;
  },
}));
```

### In-flight deduplication

Prevents concurrent duplicate API calls:

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

### Cache invalidation

After mutations, invalidate + reload:

```ts
await createClient(payload);
invalidateClients();
await loadClientsData();
```

### Store clearing

On logout/tenant switch, clear all stores:

```ts
useSettingsStore.getState().clearSettingsCache();
useCatalogStore.getState().clearAll();
```

## API Patterns

### Axios singleton

`@/lib/api.ts` — handles token injection and 401 redirect globally.

### Error extraction

```ts
try {
  await apiCall();
} catch (err) {
  const apiErr = err as { response?: { data?: { detail?: string | Array<{ msg?: string }> } } };
  const detail = apiErr.response?.data?.detail;
  const msg = typeof detail === "string"
    ? detail
    : Array.isArray(detail)
      ? detail.map((d) => d.msg || "Unknown").join("; ")
      : "Fallback message";
}
```

### Service functions

Each feature has a service file with typed API functions:

```ts
// features/admin/services/client-api.ts
import api from "@/lib/api";

export async function listClients(): Promise<Client[]> {
  const { data } = await api.get("/clients");
  return data;
}
```

## Styling

### Tailwind CSS v4

All styling via Tailwind utility classes. No custom CSS files (except `index.css` for globals).

### cn() utility

Conditional class merging via `clsx` + `tailwind-merge`:

```tsx
import { cn } from "@/lib/utils";

<div className={cn("base classes", isActive && "active classes", className)} />
```

### shadcn/ui components

Use shadcn/ui primitives from `@/components/ui/`. Customization via className props, not style overrides.

### Responsive design

- Mobile-first with `md:` breakpoint for sidebar
- Admin layout: sidebar hidden on mobile, header bar shown instead
- Sheet component for mobile navigation

## File Structure Rules

### Feature modules

Each feature under `src/features/` follows:

```
features/<role>/
├── layout/       # Layout wrapper component
├── components/   # Page and section components
└── services/     # API service functions + types
```

### Component files

- One component per file
- File name matches component name in kebab-case
- Export as named export: `export function ComponentName() {}`

### Service files

- One domain per file (client-api.ts, catalog-api.ts)
- Export typed async functions
- Import `api` from `@/lib/api`
- Types co-located in the service file or imported from shared types

## Plan-Aware UI Conventions

### `tenantPlan` is a UI hint, not authorization

Plan-aware UI gates are convenience only. Do not use frontend `tenantPlan` as authorization. Pro-only backend calls must still expect 404 for Starter tenants.

### `isMasterSupportContext` for support bypass

Master users in tenant support context (`role=master` + `activeTenantId`) see the full Pro surface regardless of the tenant's plan. Components check this flag alongside `tenantPlan` to decide visibility.

### Route-level gating

Pro-only routes (`/admin/clients`, `/admin/catalog`, `/admin/subscriptions`) are wrapped in `<PlanRouteGate>` which renders a 404 for Starter tenant admins outside Master support context.

### Sidebar nav filtering

`AdminLayout` filters nav items by `proOnly` flag. Starter admins only see Dashboard and Settings in the sidebar.

### Settings section visibility

SettingsPage conditionally includes sections: Reminder Settings, Timezone, and Public API are Pro-only; all other sections (Profile, Language, Code Services, Code Mailbox, Control de acceso, WhatsApp, Password) are available for all plans.

## No Tests

No frontend test files exist. Tests are not part of the current frontend setup. Backend has pytest coverage.

## Linting

ESLint with `eslint-plugin-react-hooks` and `eslint-plugin-react-refresh`. Run via `npm run lint`.
