# Frontend Coding Conventions

## Language & Runtime

- JavaScript (ES modules) — no TypeScript currently
- Vue 3 Composition API with `<script setup>` syntax
- Node.js (managed via `package.json`, lockfile `package-lock.json`)

## Project Structure

- `src/router/` — route definitions and navigation guards
- `src/config/` — configuration modules (e.g., `navigation.js`)
- `src/stores/` — Pinia stores (one file per store)
- `src/services/` — API client and other service modules
- `src/composables/` — Vue composables (one file per composable)
- `src/lib/` — utility modules (e.g., `utils.js` with `cn()`)
- `src/components/ui/` — shadcn-vue UI primitives (one directory per component)
- `src/components/` — reusable shared and business components
- `src/views/` — page-level components, one per route
- `src/test-utils/` — shared test helpers (e.g., `renderWithApp.js`)
- `src/styles/` — legacy CSS files (only `client-dashboard.css` still used)

## Alias Usage

All imports within `src/` use the `@` alias (configured in `vite.config.js`):

```js
// ✅ Correct: alias import
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'
import DashboardLayout from '@/components/DashboardLayout.vue'

// ❌ Avoid: relative import
import { useAuthStore } from '../stores/auth'
```

**Exception**: Some legacy views still use relative imports (e.g., `../services/api`). New code should use `@/...` consistently.

## Naming

| Artifact | Convention | Example |
|----------|-----------|---------|
| Files | camelCase | `auth.js`, `LoginView.vue` |
| Vue components (single-file) | PascalCase | `LoginView.vue`, `MasterDashboardView.vue` |
| Pinia stores | camelCase, `use<Name>Store` | `useAuthStore`, `useI18nStore` |
| Route names | kebab-case | `master-overview`, `tenant-settings` |
| Axios instance | lowercase | `api` |
| Environment variables | `VITE_UPPER_SNAKE_CASE` | `VITE_API_URL` |
| Composables | camelCase, `use<Name>` | `useTheme`, `usePublicI18n` |

## Vue Component Patterns

### Script Setup

All components use `<script setup>` with explicit imports:

```vue
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import api from '@/services/api'

const router = useRouter()
const authStore = useAuthStore()
const i18nStore = useI18nStore()
</script>
```

### Template

- Scoped styles via `<style scoped>` (minimal — most styling via Tailwind utilities)
- Event handlers use `@submit.prevent` for forms
- Conditional rendering uses `v-if`, not `v-show`
- `{{ i18nStore.t('translation.key') }}` for all user-facing text

## UI Components (shadcn-vue / Reka UI)

The project uses **shadcn-vue** components built on top of **Reka UI** headless primitives and **Tailwind CSS v4**.

### Import Pattern

All shadcn UI primitives are imported from `@/components/ui/<name>`:

```vue
<script setup>
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableEmpty,
} from '@/components/ui/table'
</script>
```

### Class Merging

Use the `cn()` utility from `@/lib/utils.js` for conditional class merging:

```js
import { cn } from '@/lib/utils'

const classes = computed(() => {
  return cn(
    'base-class',
    variant === 'primary' && 'primary-class',
    variant === 'ghost' && 'ghost-class',
  )
})
```

This combines `clsx` (conditional class objects) with `tailwind-merge` (resolves conflicting Tailwind utilities).

### Component Rules

1. **Prefer shadcn primitives** over ad-hoc styled divs for cards, buttons, inputs, tables, dialogs, sheets, selects, switches, and textareas.
2. **Do not wrap primitives** in custom wrapper components unless the wrapper adds meaningful behavior (not just styling).
3. **Use shadcn Button variants** (`default`, `outline`, `ghost`, `destructive`) and sizes (`default`, `sm`, `lg`, `icon`, `icon-sm`) instead of raw `<button>` with custom classes.
4. **Use `<Dialog>`** for modals instead of custom overlay + positioned div.
5. **Use `<Table>`** primitives instead of raw `<table>` with custom styling.
6. **Use `<Sheet>`** for slide-out panels (mobile navigation).
7. **Configure new shadcn components** by adding them to `src/components/ui/` following the existing pattern (a component directory with `index.js` re-exporting the Reka UI wrapper).

## Shared App-Level Components

The following shared components live in `src/components/` (not in `ui/`):

| Component | Purpose |
|-----------|---------|
| `DashboardLayout` | Wraps all authenticated views with sidebar, mobile nav, theme/locale controls |
| `PageHeader` | Consistent page title + description + optional `#actions` slot |
| `InlineAlert` | Styled info/success/error message with `variant` prop |
| `StatusBadge` | Status indicator with color variants (active, inactive, expired, cancelled, neutral) |
| `EmptyState` | Empty data placeholder with title, description, and optional actions slot |
| `LoadingBlock` | Centered "Loading..." placeholder |

These should be reused across views instead of duplicating markup.

## Styling with Tailwind CSS v4

- **Tailwind CSS v4** via `@tailwindcss/vite` plugin
- Custom theme defined in `src/style.css` using CSS custom properties in `oklch` color space
- Light/dark color schemes controlled by `.dark` class on `<html>`
- CSS variables follow shadcn naming: `--background`, `--foreground`, `--card`, `--muted`, `--border`, `--primary`, `--destructive`, etc.
- Use `bg-background`, `text-foreground`, `text-muted-foreground`, `border-border`, `bg-card`, `bg-muted` etc. for theme-aware styling
- Tailwind utility classes preferred over custom CSS
- Minimal use of `<style scoped>` — only for complex layouts or overrides
- Dark mode: `dark:` variant (e.g., `dark:bg-zinc-900`)

## Keep Business Logic, Replace Template

When migrating or refactoring views:

1. **Keep** the `<script setup>` section's business logic (API calls, computed state, error handling, data transformations)
2. **Replace** the `<template>` section to use shadcn primitives and shared components
3. **Remove or gut** `<style scoped>` — move any needed CSS variables into `src/style.css`
4. **Update imports** to use `@/...` alias and new UI components

This rule applies to any future UI overhaul: preserve data-flow and state logic, swap presentation markup.

## Writing Tests

### Test Framework

Tests use **Vitest** with **jsdom** environment and **@vue/test-utils**.

### Test Setup

Use the shared `renderWithApp` helper from `@/test-utils/renderWithApp`:

```js
import { renderWithApp } from '@/test-utils/renderWithApp'
```

This mounts components with a fresh Pinia instance and a memory-history Vue Router, so tests can use `useAuthStore`, `useRouter`, and route navigation.

### Test Expectations

- **View/component tests**: Verify that the component renders expected text content, handles loading/error states, and renders structural elements
- **Store tests**: Verify state mutations, getter computations, and action behavior
- **Avoid testing backend behavior**: Mock API calls at the service layer
- **Use `vi.mock()`** for mocking stores and API in view tests

### Test Coverage Requirement

Every new shared UI component or view MUST include a test file:

- Views: `src/views/__tests__/<ViewName>.spec.js`
- Shared components: `src/components/__tests__/<ComponentName>.spec.js`
- Composables: `src/composables/__tests__/<ComposableName>.spec.js`

Tests should verify:
- Component renders without errors
- Key UI elements are present
- Conditional states (loading, empty, error) render correctly
- User interactions (button clicks, form submit) trigger expected behavior

### Existing Test Files

```
src/components/__tests__/
├── DashboardLayout.spec.js
├── PageHeader.spec.js
├── StatusBadge.spec.js
└── catalogDeletePreview.spec.js

src/composables/__tests__/
└── useTheme.spec.js

src/views/__tests__/
├── LoginView.spec.js
├── RoleDashboards.spec.js
├── SubscriptionsView.spec.js
├── TenantMailboxView.spec.js
├── TenantSectionViews.spec.js
└── TenantSettingsView.spec.js
```

## I18n Conventions

- **No hardcoded translated strings** in frontend source. All UI text comes from backend catalog fetched via `GET /api/v1/i18n/catalog`.
- **I18n Pinia store** at `src/stores/i18n.js`. Import via `useI18nStore()`.
- **`t(key, params)`** — lookup function on the i18n store. Params are named placeholders replaced via string replace. Missing keys return the key itself and warn in dev console.
- **Catalog loading**: on login success (`LoginView`), on page refresh if authenticated (`main.js`), and after locale change (profile save triggers refetch).
- **Locale selector**: Dashboard sidebar provides `<select>` with `en`/`es` options. On change, save to backend (tenant role) or localStorage (master/client), refetch catalog for immediate UI update.

### Script Setup with i18n

```vue
<script setup>
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'

const authStore = useAuthStore()
const i18nStore = useI18nStore()

// Use in template: {{ i18nStore.t('frontend.login.title') }}
// Or with params: {{ i18nStore.t('frontend.clients.created', { login: client.login }) }}
</script>
```

### Template Usage

```vue
<template>
  <h1>{{ i18nStore.t('frontend.login.title') }}</h1>
  <button>{{ isLoading ? i18nStore.t('frontend.login.signing_in') : i18nStore.t('frontend.login.sign_in') }}</button>
</template>
```

## State Management (Pinia)

- Store created with `defineStore('name', () => { ... })` — composition API style
- State variables use `ref()`, getters use `computed()`
- Actions are async functions that directly mutate refs
- Auth state persisted to `localStorage` manually (no pinia-persistedstate plugin)
- Tenant settings cache is runtime-only (not persisted, deduplicated via `settingsInFlight` promise)

## API Patterns

- Axios interceptors handle token injection and 401 responses globally
- Login action uses a direct `axios.post()` call (not the `api` instance) to avoid interceptor recursion
- Error handling: try/catch in views, extract `error.response?.data?.detail` for user-facing messages
- API error helper pattern:

```js
function getApiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  }
  return detail || error.response?.data?.message || fallback
}
```

## Router Patterns

- Routes with `meta.requiresAuth` and `meta.role` for access control
- Routes with `meta.allowMasterSupport` to enable master-in-support-mode navigation
- Lazy loading: `component: () => import('...')` for all views except LoginView
- Navigation guard in `router/index.js` handles:
  - Redirect to `/login` when unauthenticated
  - Role mismatch redirect to correct dashboard
  - Support mode: allow navigation when master has `activeTenantId` and route has `allowMasterSupport: true`
  - Redirect to dashboard from `/login` when already authenticated
- Legacy redirects: `/master/dashboard` → `/master/overview`, `/admin/dashboard` → `/admin/overview`, `/client/dashboard` → `/client/overview`
- Catch-all route `/:pathMatch(.*)*` redirects unknown paths to `/login`

## Navigation Config

Sidebar navigation is computed by `getNavigationContext(authStore, route)` in `src/config/navigation.js`:

- Returns `mode` (`'master'`, `'tenant'`, `'tenant-support'`, `'client'`) and `items` array
- In `tenant-support` mode (`master` role + `activeTenantId` + path starts with `/admin`), `/admin/settings` is omitted
- Called from `DashboardLayout` to render the sidebar nav links

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `VITE_API_URL` | No | `http://localhost:8000/api/v1` | Backend API base URL |

## Dev Server

Vite dev server proxies `/api` requests to `http://localhost:8000` (configured in `vite.config.js`). This avoids CORS issues during development.
