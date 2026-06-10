# Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Trackpal frontend on a Tailwind v4 + shadcn-based UI system while preserving all existing backend-integrated business flows and fixing the regressions introduced by the recent rewrite.

**Architecture:** Keep backend contracts unchanged. Introduce the new frontend in layers: tooling and tokens first, then shell and routing, then migrate one workflow at a time. Preserve existing API and Pinia logic whenever possible; only change script logic when required to fix broken wiring or expose functionality through the new navigation.

**Tech Stack:** Vue 3, Pinia, Vue Router, Axios, Tailwind CSS v4, shadcn-vue-compatible primitives, Vitest, @vue/test-utils, vue-sonner

---

## Read this before touching code

**Spec:**
- `docs/superpowers/specs/2026-06-10-frontend-redesign-design.md`

**Frontend docs:**
- `docs/architecture/frontend-architecture.md`
- `docs/codebase/frontend-structure.md`
- `docs/code-standard/frontend-conventions.md`

**Backend contract refs (read-only, do not modify in this plan):**
- `docs/architecture/api-layer.md`
- `backend/tests/test_auth.py`
- `backend/tests/test_tenants.py`
- `backend/tests/test_profile.py`
- `backend/tests/test_catalog.py`
- `backend/tests/test_clients.py`
- `backend/tests/test_subscriptions.py`
- `backend/tests/test_code_services.py`
- `backend/tests/test_mailbox_oauth_imap.py`
- `backend/tests/test_mailbox_persistence.py`

## Baseline scan summary

### Current frontend stack
- Vue 3 + Pinia + Vue Router + Axios
- Tailwind CSS v4 already installed via `@tailwindcss/vite`
- Existing theme toggle in `frontend/src/composables/useTheme.js`
- Existing shared shell in `frontend/src/components/DashboardLayout.vue`
- Existing frontend tests are minimal: theme, auth-store reminder cache, catalog delete-preview helper

### Current backend contracts used by the frontend
| Surface | Frontend callers | Backend endpoints | Backend contract tests |
|---|---|---|---|
| Login | `src/views/LoginView.vue`, `src/stores/auth.js` | `POST /auth/login`, `GET /i18n/catalog` | `test_auth.py`, `test_i18n.py` |
| Master | `src/views/MasterDashboardView.vue`, `src/components/CodeServicesGlobalPanel.vue` | `/tenants`, `/auth/switch-tenant`, `/code-services/global` | `test_tenants.py`, `test_code_services.py` |
| Tenant settings | `src/views/TenantDashboardView.vue` | `/me`, `/me/password` | `test_profile.py` |
| Clients | `src/components/ClientManagementPanel.vue` | `/clients*` | `test_clients.py` |
| Catalog | `src/components/CatalogPanel.vue` | `/catalog/services*`, `/delete-preview` | `test_catalog.py` |
| Subscriptions | `src/views/SubscriptionsView.vue`, `src/components/subscriptions/*` | `/subscriptions*`, `/subscription-settings*`, `/catalog/services/{id}/plans`, `/clients` | `test_subscriptions.py` |
| Mailbox | `src/components/MailboxConfigPanel.vue` | `/tenant/mailbox/*` | `test_mailbox_oauth_imap.py`, `test_mailbox_persistence.py` |
| Code services (tenant) | `src/components/CodeServicesTenantPanel.vue` | `/code-services/tenants/current*` | `test_code_services.py` |
| Client dashboard | `src/views/ClientDashboardView.vue` | `/dashboard`, `/me`, `/me/password` | `test_profile.py`, `test_subscriptions.py` |

### Known regressions to fix during migration
1. `frontend/src/views/TenantDashboardView.vue` renders `MailboxConfigPanel` without passing `mailbox` or handling `@updated`; existing mailbox state never loads.
2. `frontend/src/views/SubscriptionsView.vue` mounts `ReminderSettingsModal` without passing the prop it actually uses; the modal never renders or loads settings.
3. `frontend/src/components/subscriptions/SubscriptionFilters.vue` keeps its own local filter state and does not hydrate from `route.query.client_id`; clicking “subscriptions” from a client row loses visible filter state on the next interaction.
4. `frontend/src/components/DashboardLayout.vue` builds navigation from `authStore.role` only, so master support mode (`activeTenantId`) shows the wrong menu while the user is on tenant routes.
5. Tenant settings must not be exposed in master support mode because `/me` remains master-scoped; only direct tenants should reach `/admin/settings`.

## File structure to end up with

### New configuration / tooling files
- Create: `frontend/jsconfig.json` — alias support for `@/*`
- Create: `frontend/components.json` — shadcn-vue project config for JavaScript + Tailwind v4
- Create: `frontend/src/lib/utils.js` — `cn()` helper for class merging
- Create: `frontend/src/test-utils/renderWithApp.js` — shared mount helper for Pinia + Router tests

### New shared UI files
- Create via shadcn CLI: `frontend/src/components/ui/*`
  - Required primitives in this plan: `button`, `input`, `textarea`, `select`, `dialog`, `sheet`, `tabs`, `badge`, `dropdown-menu`, `table`, `separator`, `switch`, `checkbox`, `card`, `sonner`
- Create: `frontend/src/components/InlineAlert.vue`
- Create: `frontend/src/components/EmptyState.vue`
- Create: `frontend/src/components/LoadingBlock.vue`
- Create: `frontend/src/components/PageHeader.vue`
- Create: `frontend/src/components/StatusBadge.vue`

### New navigation / route files
- Create: `frontend/src/config/navigation.js`
- Create: `frontend/src/views/TenantClientsView.vue`
- Create: `frontend/src/views/TenantCatalogView.vue`
- Create: `frontend/src/views/TenantMailboxView.vue`
- Create: `frontend/src/views/TenantCodeServicesView.vue`
- Create: `frontend/src/views/TenantSettingsView.vue`
- Create: `frontend/src/views/MasterCodeServicesView.vue`

### Existing files that must be migrated, not replaced blindly
- Modify: `frontend/src/style.css`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/components/DashboardLayout.vue`
- Modify: `frontend/src/components/ThemeToggle.vue`
- Modify: `frontend/src/composables/useTheme.js`
- Modify: `frontend/src/views/LoginView.vue`
- Modify: `frontend/src/views/MasterDashboardView.vue`
- Modify: `frontend/src/views/TenantDashboardView.vue`
- Modify: `frontend/src/views/SubscriptionsView.vue`
- Modify: `frontend/src/views/ClientDashboardView.vue`
- Modify: `frontend/src/components/CatalogPanel.vue`
- Modify: `frontend/src/components/ClientManagementPanel.vue`
- Modify: `frontend/src/components/CodeServicesGlobalPanel.vue`
- Modify: `frontend/src/components/CodeServicesTenantPanel.vue`
- Modify: `frontend/src/components/MailboxConfigPanel.vue`
- Modify: `frontend/src/components/subscriptions/ReminderSettingsModal.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionFilters.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionModal.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionRenewModal.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionReactivateModal.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionCancelModal.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionTable.vue`

### Docs that must be updated at the end
- Modify: `docs/architecture/frontend-architecture.md`
- Modify: `docs/codebase/frontend-structure.md`
- Modify: `docs/code-standard/frontend-conventions.md`

### Ground rules for every implementation task
- Keep backend APIs unchanged.
- Preserve current Pinia store names and Axios service import path.
- For business components, prefer “replace template, keep logic” over rewriting scripts from scratch.
- Use inline alerts for long-form errors, toasts only for short confirmations.
- Do not add remote fonts in this pass.
- Use role-aware routing plus support-mode routing; do not infer navigation from `authStore.role` alone.

---

- [x] **Step 1: Write the failing `cn()` helper test**

```js
// frontend/src/lib/__tests__/utils.spec.js
import { describe, it, expect } from 'vitest'
import { cn } from '../utils'

describe('cn', () => {
  it('merges tailwind classes and keeps the last conflicting utility', () => {
    expect(cn('px-2 text-sm', 'px-4', false && 'hidden')).toBe('text-sm px-4')
  })
})
```

- [x] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/__tests__/utils.spec.js`
Expected: FAIL with `Cannot find module '../utils'` or equivalent import error.

- [x] **Step 3: Install the missing dependencies and create the project scaffolding**

Run:

```bash
cd frontend && npm i class-variance-authority clsx tailwind-merge lucide-vue-next tw-animate-css reka-ui vue-sonner
cd frontend && npm i -D @vue/test-utils
```

Create `frontend/jsconfig.json`:

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.js", "src/**/*.vue"]
}
```

Create `frontend/components.json`:

```json
{
  "$schema": "https://shadcn-vue.com/schema.json",
  "style": "new-york",
  "typescript": false,
  "tailwind": {
    "config": "",
    "css": "src/style.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "composables": "@/composables",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib"
  },
  "iconLibrary": "lucide"
}
```

Modify `frontend/vite.config.js`:

```js
/// <reference types="vitest" />
import path from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
```

Create `frontend/src/lib/utils.js`:

```js
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
```

Create `frontend/src/test-utils/renderWithApp.js`:

```js
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

export async function renderWithApp(component, {
  props = {},
  slots = {},
  routes = [{ path: '/', component }],
  path = '/',
  global = {},
} = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  })

  router.push(path)
  await router.isReady()

  return mount(component, {
    props,
    slots,
    global: {
      plugins: [pinia, router],
      ...global,
    },
  })
}
```

Run the shadcn CLI after the config files exist:

```bash
cd frontend && npx shadcn-vue@latest add button input textarea select dialog sheet tabs badge dropdown-menu table separator switch checkbox card sonner
```

Modify `frontend/src/App.vue` so the toaster is always mounted:

```vue
<script setup>
import 'vue-sonner/style.css'
import { Toaster } from '@/components/ui/sonner'
</script>

<template>
  <router-view />
  <Toaster class="pointer-events-auto" rich-colors close-button />
</template>
```

- [x] **Step 4: Run the helper test and a production build**

Run:
- `cd frontend && npx vitest run src/lib/__tests__/utils.spec.js`
- `cd frontend && npm run build`

Expected:
- Vitest PASS
- Vite build PASS

- [x] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/jsconfig.json frontend/components.json frontend/vite.config.js frontend/src/App.vue frontend/src/lib/utils.js frontend/src/lib/__tests__/utils.spec.js frontend/src/test-utils/renderWithApp.js frontend/src/components/ui
git commit -m "chore: add shadcn frontend foundation"
```

---

### Task 2: Global theme tokens and shared feedback primitives

**Required skills:**
- `superpowers:test-driven-development`
- `vue-expert-js`
- `uncodixfy`
- `impeccable`

**Files:**
- Modify: `frontend/src/style.css`
- Modify: `frontend/src/composables/useTheme.js`
- Modify: `frontend/src/components/ThemeToggle.vue`
- Create: `frontend/src/components/InlineAlert.vue`
- Create: `frontend/src/components/EmptyState.vue`
- Create: `frontend/src/components/LoadingBlock.vue`
- Create: `frontend/src/components/PageHeader.vue`
- Create: `frontend/src/components/StatusBadge.vue`
- Test: `frontend/src/components/__tests__/PageHeader.spec.js`
- Test: `frontend/src/components/__tests__/StatusBadge.spec.js`
- Test: `frontend/src/composables/__tests__/theme.spec.js`

- [x] **Step 1: Write the failing shared-component tests**

```js
// frontend/src/components/__tests__/PageHeader.spec.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PageHeader from '../PageHeader.vue'

describe('PageHeader', () => {
  it('renders title, description, and actions slot', () => {
    const wrapper = mount(PageHeader, {
      props: { title: 'Subscriptions', description: 'Manage client access' },
      slots: { actions: '<button>New</button>' },
    })

    expect(wrapper.text()).toContain('Subscriptions')
    expect(wrapper.text()).toContain('Manage client access')
    expect(wrapper.text()).toContain('New')
  })
})
```

```js
// frontend/src/components/__tests__/StatusBadge.spec.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusBadge from '../StatusBadge.vue'

describe('StatusBadge', () => {
  it('renders the label and variant classes for active state', () => {
    const wrapper = mount(StatusBadge, {
      props: { variant: 'active', label: 'Active' },
    })

    expect(wrapper.text()).toContain('Active')
    expect(wrapper.classes().join(' ')).toContain('text-emerald')
  })
})
```

- [x] **Step 2: Run the tests to verify they fail**

Run:
- `cd frontend && npx vitest run src/components/__tests__/PageHeader.spec.js`
- `cd frontend && npx vitest run src/components/__tests__/StatusBadge.spec.js`

Expected: FAIL because the components do not exist yet.

- [x] **Step 3: Implement the global token system and shared components**

Modify `frontend/src/style.css` to establish the theme contract:

```css
@import "tailwindcss";
@import "tw-animate-css";

:root {
  --background: oklch(0.982 0.004 95);
  --foreground: oklch(0.245 0.01 95);
  --card: oklch(0.995 0.002 95);
  --card-foreground: oklch(0.245 0.01 95);
  --muted: oklch(0.956 0.006 95);
  --muted-foreground: oklch(0.52 0.014 95);
  --border: oklch(0.905 0.01 95);
  --input: oklch(0.905 0.01 95);
  --ring: oklch(0.56 0.07 265);
  --primary: oklch(0.38 0.05 265);
  --primary-foreground: oklch(0.985 0.002 95);
  --success: oklch(0.56 0.12 150);
  --warning: oklch(0.71 0.13 80);
  --destructive: oklch(0.58 0.16 25);
  --sidebar: oklch(0.97 0.004 95);
  --sidebar-foreground: oklch(0.28 0.01 95);
}

.dark {
  --background: oklch(0.18 0.01 95);
  --foreground: oklch(0.94 0.003 95);
  --card: oklch(0.22 0.01 95);
  --card-foreground: oklch(0.94 0.003 95);
  --muted: oklch(0.25 0.01 95);
  --muted-foreground: oklch(0.72 0.01 95);
  --border: oklch(0.3 0.01 95);
  --input: oklch(0.3 0.01 95);
  --ring: oklch(0.68 0.05 265);
  --primary: oklch(0.78 0.04 265);
  --primary-foreground: oklch(0.2 0.01 95);
  --success: oklch(0.72 0.11 150);
  --warning: oklch(0.78 0.12 80);
  --destructive: oklch(0.72 0.16 25);
  --sidebar: oklch(0.2 0.01 95);
  --sidebar-foreground: oklch(0.9 0.003 95);
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-ring: var(--ring);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-success: var(--success);
  --color-warning: var(--warning);
  --color-destructive: var(--destructive);
  --color-sidebar: var(--sidebar);
  --color-sidebar-foreground: var(--sidebar-foreground);
}

@layer base {
  * {
    @apply border-border;
  }

  html {
    color-scheme: light;
  }

  html.dark {
    color-scheme: dark;
  }

  body {
    @apply min-h-screen bg-background text-foreground antialiased;
  }
}
```

Create `frontend/src/components/PageHeader.vue`:

```vue
<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>

<template>
  <div class="flex flex-col gap-3 border-b border-border pb-4 md:flex-row md:items-end md:justify-between">
    <div class="space-y-1">
      <h1 class="text-xl font-semibold tracking-tight text-foreground">{{ title }}</h1>
      <p v-if="description" class="text-sm text-muted-foreground">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="flex items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>
```

Create `frontend/src/components/StatusBadge.vue`:

```vue
<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  variant: { type: String, default: 'neutral' },
  label: { type: String, required: true },
})

const classes = computed(() => {
  const map = {
    active: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    inactive: 'border-border bg-muted text-muted-foreground',
    expired: 'border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300',
    cancelled: 'border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300',
    neutral: 'border-border bg-muted text-muted-foreground',
  }

  return cn('inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium', map[props.variant] || map.neutral)
})
</script>

<template>
  <span :class="classes">{{ label }}</span>
</template>
```

Create `frontend/src/components/InlineAlert.vue`:

```vue
<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  variant: { type: String, default: 'info' },
  message: { type: String, required: true },
})

const classes = computed(() => {
  const map = {
    info: 'border-border bg-muted text-foreground',
    success: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
    error: 'border-red-500/20 bg-red-500/10 text-red-800 dark:text-red-200',
  }
  return cn('rounded-md border px-3 py-2 text-sm', map[props.variant] || map.info)
})
</script>

<template>
  <p :class="classes">{{ message }}</p>
</template>
```

Create `frontend/src/components/EmptyState.vue` and `frontend/src/components/LoadingBlock.vue` with the same design language.

Modify `frontend/src/components/ThemeToggle.vue` to use the shadcn button primitive instead of ad-hoc classes.

- [x] **Step 4: Run the new shared-component tests and the existing theme tests**

Run:
- `cd frontend && npx vitest run src/components/__tests__/PageHeader.spec.js src/components/__tests__/StatusBadge.spec.js`
- `cd frontend && npx vitest run src/composables/__tests__/theme.spec.js`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src/style.css frontend/src/components/ThemeToggle.vue frontend/src/composables/useTheme.js frontend/src/components/InlineAlert.vue frontend/src/components/EmptyState.vue frontend/src/components/LoadingBlock.vue frontend/src/components/PageHeader.vue frontend/src/components/StatusBadge.vue frontend/src/components/__tests__/PageHeader.spec.js frontend/src/components/__tests__/StatusBadge.spec.js
git commit -m "feat: add frontend theme tokens and shared feedback components"
```

---

### Task 3: Router expansion and shared app shell

**Required skills:**
- `superpowers:test-driven-development`
- `vue-expert-js`
- `uncodixfy`
- `impeccable`

**Files:**
- Create: `frontend/src/config/navigation.js`
- Create: `frontend/src/components/__tests__/DashboardLayout.spec.js`
- Create: `frontend/src/router/__tests__/router.spec.js`
- Create: `frontend/src/views/TenantClientsView.vue`
- Create: `frontend/src/views/TenantCatalogView.vue`
- Create: `frontend/src/views/TenantMailboxView.vue`
- Create: `frontend/src/views/TenantCodeServicesView.vue`
- Create: `frontend/src/views/TenantSettingsView.vue`
- Create: `frontend/src/views/MasterCodeServicesView.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/components/DashboardLayout.vue`

- [x] **Step 1: Write the failing shell and router tests**

```js
// frontend/src/router/__tests__/router.spec.js
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import router from '../index'
import { useAuthStore } from '@/stores/auth'

describe('router', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('redirects legacy tenant dashboard to /admin/overview', async () => {
    const store = useAuthStore()
    store.token = 'token'
    store.user = { role: 'tenant', id: 'tenant-user' }

    await router.push('/admin/dashboard')
    expect(router.currentRoute.value.fullPath).toBe('/admin/overview')
  })

  it('allows master support mode into tenant workflow pages but not /admin/settings', async () => {
    const store = useAuthStore()
    store.token = 'token'
    store.user = { role: 'master', id: 'master-user' }
    store.activeTenantId = 'tenant-1'

    await router.push('/admin/clients')
    expect(router.currentRoute.value.fullPath).toBe('/admin/clients')

    await router.push('/admin/settings')
    expect(router.currentRoute.value.fullPath).not.toBe('/admin/settings')
  })
})
```

```js
// frontend/src/components/__tests__/DashboardLayout.spec.js
import { describe, it, expect } from 'vitest'
import DashboardLayout from '../DashboardLayout.vue'
import { renderWithApp } from '@/test-utils/renderWithApp'
import { useAuthStore } from '@/stores/auth'

describe('DashboardLayout', () => {
  it('shows tenant support navigation when a master has activeTenantId and is on /admin/*', async () => {
    const wrapper = await renderWithApp(DashboardLayout, {
      routes: [{ path: '/admin/clients', component: DashboardLayout }],
      path: '/admin/clients',
      slots: { default: '<div>body</div>' },
    })

    const store = useAuthStore()
    store.user = { role: 'master', username: 'master' }
    store.activeTenantId = 'tenant-1'
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Clients')
    expect(wrapper.text()).toContain('Exit support')
  })
})
```

- [x] **Step 2: Run the tests to verify they fail**

Run:
- `cd frontend && npx vitest run src/router/__tests__/router.spec.js`
- `cd frontend && npx vitest run src/components/__tests__/DashboardLayout.spec.js`

Expected: FAIL because the new routes and support-mode shell behavior do not exist yet.

- [x] **Step 3: Implement the navigation model, route map, and shell**

Create `frontend/src/config/navigation.js`:

```js
export function getNavigationContext(authStore, route) {
  const isSupportMode = authStore.role === 'master' && !!authStore.activeTenantId && route.path.startsWith('/admin')

  if (isSupportMode) {
    return {
      mode: 'tenant-support',
      items: [
        { label: 'Overview', to: '/admin/overview' },
        { label: 'Clients', to: '/admin/clients' },
        { label: 'Catalog', to: '/admin/catalog' },
        { label: 'Subscriptions', to: '/admin/subscriptions' },
        { label: 'Mailbox', to: '/admin/mailbox' },
        { label: 'Code Services', to: '/admin/code-services' },
      ],
    }
  }

  if (authStore.role === 'master') {
    return {
      mode: 'master',
      items: [
        { label: 'Overview', to: '/master/overview' },
        { label: 'Code Services', to: '/master/code-services' },
      ],
    }
  }

  if (authStore.role === 'tenant') {
    return {
      mode: 'tenant',
      items: [
        { label: 'Overview', to: '/admin/overview' },
        { label: 'Clients', to: '/admin/clients' },
        { label: 'Catalog', to: '/admin/catalog' },
        { label: 'Subscriptions', to: '/admin/subscriptions' },
        { label: 'Mailbox', to: '/admin/mailbox' },
        { label: 'Code Services', to: '/admin/code-services' },
        { label: 'Settings', to: '/admin/settings' },
      ],
    }
  }

  return {
    mode: 'client',
    items: [{ label: 'Overview', to: '/client/overview' }],
  }
}
```

Modify `frontend/src/router/index.js` so the canonical routes become:

```js
const routes = [
  { path: '/login', name: 'login', component: LoginView, meta: { requiresAuth: false } },

  { path: '/master/overview', name: 'master-overview', meta: { requiresAuth: true, role: 'master' }, component: () => import('../views/MasterDashboardView.vue') },
  { path: '/master/code-services', name: 'master-code-services', meta: { requiresAuth: true, role: 'master' }, component: () => import('../views/MasterCodeServicesView.vue') },
  { path: '/master/dashboard', redirect: '/master/overview' },

  { path: '/admin/overview', name: 'tenant-overview', meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true }, component: () => import('../views/TenantDashboardView.vue') },
  { path: '/admin/clients', name: 'tenant-clients', meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true }, component: () => import('../views/TenantClientsView.vue') },
  { path: '/admin/catalog', name: 'tenant-catalog', meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true }, component: () => import('../views/TenantCatalogView.vue') },
  { path: '/admin/subscriptions', name: 'tenant-subscriptions', meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true }, component: () => import('../views/SubscriptionsView.vue') },
  { path: '/admin/mailbox', name: 'tenant-mailbox', meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true }, component: () => import('../views/TenantMailboxView.vue') },
  { path: '/admin/code-services', name: 'tenant-code-services', meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true }, component: () => import('../views/TenantCodeServicesView.vue') },
  { path: '/admin/settings', name: 'tenant-settings', meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: false }, component: () => import('../views/TenantSettingsView.vue') },
  { path: '/admin/dashboard', redirect: '/admin/overview' },

  { path: '/client/overview', name: 'client-overview', meta: { requiresAuth: true, role: 'client' }, component: () => import('../views/ClientDashboardView.vue') },
  { path: '/client/dashboard', redirect: '/client/overview' },

  { path: '/:pathMatch(.*)*', redirect: '/login' },
]
```

Update the guard so `allowMasterSupport: false` blocks `/admin/settings` for masters even when `activeTenantId` exists.

Refactor `frontend/src/components/DashboardLayout.vue` to:
- use `getNavigationContext(authStore, route)`
- show `Exit support` button when `mode === 'tenant-support'`
- keep theme toggle, locale selector, and logout grouped in the shell footer / topbar
- use shadcn `Sheet`, `Button`, `DropdownMenu`, and `Separator` instead of custom modal/backdrop markup

Create minimal route files so the new route map compiles. Use this exact pattern first; later tasks will fill them in with real content:

```vue
<!-- Example: frontend/src/views/TenantClientsView.vue -->
<script setup>
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Clients" description="Manage client access." />
    </div>
  </DashboardLayout>
</template>
```

- [x] **Step 4: Re-run the shell and router tests**

Run:
- `cd frontend && npx vitest run src/router/__tests__/router.spec.js`
- `cd frontend && npx vitest run src/components/__tests__/DashboardLayout.spec.js`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src/config/navigation.js frontend/src/router/index.js frontend/src/components/DashboardLayout.vue frontend/src/components/__tests__/DashboardLayout.spec.js frontend/src/router/__tests__/router.spec.js frontend/src/views/TenantClientsView.vue frontend/src/views/TenantCatalogView.vue frontend/src/views/TenantMailboxView.vue frontend/src/views/TenantCodeServicesView.vue frontend/src/views/TenantSettingsView.vue frontend/src/views/MasterCodeServicesView.vue
git commit -m "feat: add role-aware app shell and route map"
```

---

### Task 4: Redesign LoginView on the new system

**Required skills:**
- `superpowers:test-driven-development`
- `vue-expert-js`
- `uncodixfy`
- `impeccable`

**Files:**
- Modify: `frontend/src/views/LoginView.vue`
- Test: `frontend/src/views/__tests__/LoginView.spec.js`

- [x] **Step 1: Write the failing login view test**

```js
import { describe, it, expect, vi } from 'vitest'
import { renderWithApp } from '@/test-utils/renderWithApp'
import LoginView from '../LoginView.vue'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    login: vi.fn().mockResolvedValue({ user: { role: 'tenant' } }),
  }),
}))

vi.mock('@/stores/i18n', () => ({
  useI18nStore: () => ({ loadCatalog: vi.fn(), t: key => key }),
}))

describe('LoginView', () => {
  it('renders the form and submits to the tenant overview route', async () => {
    const wrapper = await renderWithApp(LoginView, {
      routes: [
        { path: '/login', component: LoginView },
        { path: '/admin/overview', component: { template: '<div>Tenant</div>' } },
      ],
      path: '/login',
    })

    await wrapper.get('#username').setValue('tenant')
    await wrapper.get('#password').setValue('tenant-password')
    await wrapper.get('form').trigger('submit.prevent')

    expect(wrapper.html()).toContain('Trackpal')
  })
})
```

- [x] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/views/__tests__/LoginView.spec.js`
Expected: FAIL because the route map and login redirection target changed, and the old template is still in place.

- [x] **Step 3: Implement the new login layout while preserving auth logic**

Keep the existing `handleSubmit()` flow, but replace the template with a two-zone composition built from the new primitives.

Use this structure:

```vue
<script setup>
// keep the current imports and handleSubmit logic
</script>

<template>
  <main class="grid min-h-screen lg:grid-cols-[1.1fr_0.9fr]">
    <section class="hidden border-r border-border bg-muted/40 p-10 lg:flex lg:flex-col lg:justify-between">
      <div class="space-y-4">
        <p class="text-sm font-medium text-muted-foreground">Trackpal</p>
        <div class="space-y-2">
          <h1 class="text-3xl font-semibold tracking-tight">Operational access, without dashboard noise.</h1>
          <p class="max-w-md text-sm text-muted-foreground">Sign in to manage tenants, client access, subscriptions, and mailbox workflows.</p>
        </div>
      </div>
      <div class="flex items-center gap-3 text-sm text-muted-foreground">
        <ThemeToggle />
        <select id="locale-select" v-model="locale" @change="setLocale(locale)" class="h-9 rounded-md border border-input bg-background px-3">
          <option value="en">English</option>
          <option value="es">Español</option>
        </select>
      </div>
    </section>

    <section class="flex items-center justify-center p-6">
      <div class="w-full max-w-md space-y-6">
        <div class="space-y-1 lg:hidden">
          <p class="text-sm font-medium text-muted-foreground">Trackpal</p>
          <h1 class="text-2xl font-semibold tracking-tight">{{ t('login.title') }}</h1>
        </div>

        <div class="rounded-xl border border-border bg-card p-6 shadow-sm">
          <form class="space-y-4" @submit.prevent="handleSubmit">
            <div class="space-y-2">
              <label for="username" class="text-sm font-medium">{{ t('login.username') }}</label>
              <input id="username" v-model="username" type="text" autocomplete="username" required class="h-10 w-full rounded-md border border-input bg-background px-3" />
            </div>
            <div class="space-y-2">
              <label for="password" class="text-sm font-medium">{{ t('login.password') }}</label>
              <input id="password" v-model="password" type="password" autocomplete="current-password" required class="h-10 w-full rounded-md border border-input bg-background px-3" />
            </div>
            <InlineAlert v-if="errorMessage" variant="error" :message="errorMessage" />
            <button type="submit" :disabled="isLoading" class="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground">
              {{ isLoading ? t('login.signing_in') : t('login.sign_in') }}
            </button>
          </form>
        </div>
      </div>
    </section>
  </main>
</template>
```

Also update the redirection targets in `handleSubmit()` to:
- master → `/master/overview`
- tenant → `/admin/overview`
- client → `/client/overview`

- [x] **Step 4: Run the login test and a production build**

Run:
- `cd frontend && npx vitest run src/views/__tests__/LoginView.spec.js`
- `cd frontend && npm run build`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src/views/LoginView.vue frontend/src/views/__tests__/LoginView.spec.js
git commit -m "feat: redesign login on shared ui system"
```

---

### Task 5: Tenant overview and settings split

**Required skills:**
- `superpowers:test-driven-development`
- `vue-expert-js`
- `uncodixfy`
- `impeccable`

**Files:**
- Modify: `frontend/src/views/TenantDashboardView.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/config/navigation.js`
- Modify: `frontend/src/views/TenantSettingsView.vue`
- Test: `frontend/src/views/__tests__/TenantSettingsView.spec.js`

**Backend contract refs:**
- `backend/tests/test_profile.py`

- [ ] **Step 1: Write the failing settings page test**

```js
import { describe, it, expect, vi } from 'vitest'
import { renderWithApp } from '@/test-utils/renderWithApp'
import TenantSettingsView from '../TenantSettingsView.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}))

vi.mock('@/stores/i18n', () => ({
  useI18nStore: () => ({ t: key => key, loadCatalog: vi.fn() }),
}))

describe('TenantSettingsView', () => {
  it('loads /me and saves profile data', async () => {
    api.get.mockResolvedValueOnce({ data: { full_name: 'Active Tenant', email: 'tenant@example.com', phone: '12015550002', locale: 'en' } })
    api.put.mockResolvedValueOnce({ data: { full_name: 'Updated Tenant', email: 'tenant@example.com', phone: '12015550002', locale: 'es' } })

    const wrapper = await renderWithApp(TenantSettingsView)
    expect(api.get).toHaveBeenCalledWith('/me')
    await wrapper.get('#profile_locale').setValue('es')
    await wrapper.get('form[data-testid="tenant-profile-form"]').trigger('submit.prevent')
    expect(api.put).toHaveBeenCalledWith('/me', expect.objectContaining({ locale: 'es' }))
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/views/__tests__/TenantSettingsView.spec.js`
Expected: FAIL because `TenantSettingsView.vue` is still a stub.

- [ ] **Step 3: Turn `TenantDashboardView.vue` into the tenant overview page and implement `TenantSettingsView.vue`**

Update `frontend/src/views/TenantDashboardView.vue` so it becomes the overview page, not the old tabbed container.

Use this exact overview structure:

```vue
<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'

const router = useRouter()
const authStore = useAuthStore()
const isSupportMode = computed(() => authStore.role === 'master' && !!authStore.activeTenantId)

const cards = computed(() => {
  const items = [
    { title: 'Clients', to: '/admin/clients', body: 'Create, edit, activate, and deactivate client access.' },
    { title: 'Catalog', to: '/admin/catalog', body: 'Manage services, plans, and delete-preview flows.' },
    { title: 'Subscriptions', to: '/admin/subscriptions', body: 'Create, renew, cancel, and reveal credentials.' },
    { title: 'Mailbox', to: '/admin/mailbox', body: 'Configure OAuth or IMAP mailbox access.' },
    { title: 'Code Services', to: '/admin/code-services', body: 'Choose which lookup services are active.' },
  ]

  if (!isSupportMode.value) {
    items.push({ title: 'Settings', to: '/admin/settings', body: 'Update tenant profile, locale, and password.' })
  }

  return items
})
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Overview" description="Choose the area you want to work in." />
      <InlineAlert
        v-if="isSupportMode"
        variant="info"
        message="You are browsing this tenant in support mode. Profile settings stay on the master account and are intentionally hidden here."
      />
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <button v-for="card in cards" :key="card.to" type="button" class="rounded-xl border border-border bg-card p-5 text-left shadow-sm transition-colors hover:bg-muted/40" @click="router.push(card.to)">
          <div class="space-y-1">
            <h2 class="text-base font-medium">{{ card.title }}</h2>
            <p class="text-sm text-muted-foreground">{{ card.body }}</p>
          </div>
        </button>
      </div>
    </div>
  </DashboardLayout>
</template>
```

Implement `frontend/src/views/TenantSettingsView.vue` by moving the current profile/password logic out of the old tabbed dashboard. Keep the existing `/me`, `/me/password`, and `i18nStore.loadCatalog()` behavior. Do **not** allow this page in support mode; the route guard from Task 3 enforces that.

- [ ] **Step 4: Run the settings test**

Run: `cd frontend && npx vitest run src/views/__tests__/TenantSettingsView.spec.js`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src/views/TenantDashboardView.vue frontend/src/views/TenantSettingsView.vue frontend/src/views/__tests__/TenantSettingsView.spec.js frontend/src/router/index.js frontend/src/config/navigation.js
git commit -m "feat: split tenant overview and settings"
```

---

### Task 6: Tenant mailbox page and mailbox refresh wiring

**Required skills:**
- `superpowers:test-driven-development`
- `superpowers:systematic-debugging`
- `vue-expert-js`
- `uncodixfy`
- `impeccable`

**Files:**
- Modify: `frontend/src/views/TenantMailboxView.vue`
- Modify: `frontend/src/components/MailboxConfigPanel.vue`
- Test: `frontend/src/views/__tests__/TenantMailboxView.spec.js`

**Backend contract refs:**
- `backend/tests/test_mailbox_oauth_imap.py`
- `backend/tests/test_mailbox_persistence.py`

- [x] **Step 1: Write the failing mailbox page test for the real regression**

```js
import { describe, it, expect, vi } from 'vitest'
import { renderWithApp } from '@/test-utils/renderWithApp'
import TenantMailboxView from '../TenantMailboxView.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('TenantMailboxView', () => {
  it('loads mailbox config and refreshes it after the panel emits updated', async () => {
    api.get
      .mockResolvedValueOnce({ data: { mailbox_email: 'ops@example.com', provider: 'google', auth_method: 'oauth', status: 'connected' } })
      .mockResolvedValueOnce({ data: { mailbox_email: 'ops@example.com', provider: 'google', auth_method: 'oauth', status: 'revoked' } })

    const wrapper = await renderWithApp(TenantMailboxView)
    expect(api.get).toHaveBeenCalledWith('/tenant/mailbox/')

    wrapper.getComponent({ name: 'MailboxConfigPanel' }).vm.$emit('updated')
    await Promise.resolve()

    expect(api.get).toHaveBeenCalledTimes(2)
  })
})
```

- [x] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/views/__tests__/TenantMailboxView.spec.js`
Expected: FAIL because the view does not load mailbox state yet.

- [x] **Step 3: Implement `TenantMailboxView.vue` and re-skin `MailboxConfigPanel.vue`**

Implement `frontend/src/views/TenantMailboxView.vue` like this:

```vue
<script setup>
import { onMounted, ref } from 'vue'
import api from '@/services/api'
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'
import InlineAlert from '@/components/InlineAlert.vue'
import MailboxConfigPanel from '@/components/MailboxConfigPanel.vue'

const mailbox = ref(null)
const errorMessage = ref('')

async function loadMailbox() {
  errorMessage.value = ''
  try {
    const response = await api.get('/tenant/mailbox/')
    mailbox.value = response.data
  } catch (error) {
    const detail = error.response?.data?.detail
    errorMessage.value = Array.isArray(detail) ? detail.map(item => item.msg || item.message || String(item)).join(', ') : detail || 'Could not load mailbox configuration.'
  }
}

onMounted(loadMailbox)
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Mailbox" description="Connect the mailbox used for code retrieval workflows." />
      <InlineAlert v-if="errorMessage" variant="error" :message="errorMessage" />
      <MailboxConfigPanel :mailbox="mailbox" @updated="loadMailbox" />
    </div>
  </DashboardLayout>
</template>
```

Then refactor `frontend/src/components/MailboxConfigPanel.vue` to keep the existing save/test/oauth/disconnect logic, but replace the raw template with:
- shadcn card-like sections
- `InlineAlert` for errors/success
- a stronger status display using `StatusBadge`
- buttons and form inputs from the shared UI system

Do **not** move the mutation API calls out of the component in this task. The point of this task is to fix loading/refresh and re-skin the UI without changing mailbox behavior.

- [x] **Step 4: Run the mailbox page test**

Run: `cd frontend && npx vitest run src/views/__tests__/TenantMailboxView.spec.js`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src/views/TenantMailboxView.vue frontend/src/components/MailboxConfigPanel.vue frontend/src/views/__tests__/TenantMailboxView.spec.js
git commit -m "fix: restore tenant mailbox wiring and redesign mailbox page"
```

---

### Task 7: Tenant clients, catalog, and code-services sections

**Required skills:**
- `superpowers:test-driven-development`
- `vue-expert-js`
- `uncodixfy`
- `impeccable`

**Files:**
- Modify: `frontend/src/views/TenantClientsView.vue`
- Modify: `frontend/src/views/TenantCatalogView.vue`
- Modify: `frontend/src/views/TenantCodeServicesView.vue`
- Modify: `frontend/src/components/ClientManagementPanel.vue`
- Modify: `frontend/src/components/CatalogPanel.vue`
- Modify: `frontend/src/components/CodeServicesTenantPanel.vue`
- Test: `frontend/src/views/__tests__/TenantSectionViews.spec.js`

**Backend contract refs:**
- `backend/tests/test_clients.py`
- `backend/tests/test_catalog.py`
- `backend/tests/test_code_services.py`

- [ ] **Step 1: Write the failing tenant section smoke tests**

```js
// frontend/src/views/__tests__/TenantSectionViews.spec.js
import { describe, it, expect } from 'vitest'
import { renderWithApp } from '@/test-utils/renderWithApp'
import TenantClientsView from '../TenantClientsView.vue'
import TenantCatalogView from '../TenantCatalogView.vue'
import TenantCodeServicesView from '../TenantCodeServicesView.vue'

describe('tenant section routes', () => {
  it('renders the clients page shell', async () => {
    const wrapper = await renderWithApp(TenantClientsView)
    expect(wrapper.text()).toContain('Clients')
  })

  it('renders the catalog page shell', async () => {
    const wrapper = await renderWithApp(TenantCatalogView)
    expect(wrapper.text()).toContain('Catalog')
  })

  it('renders the code services page shell', async () => {
    const wrapper = await renderWithApp(TenantCodeServicesView)
    expect(wrapper.text()).toContain('Code Services')
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/views/__tests__/TenantSectionViews.spec.js`
Expected: FAIL because the route files still contain only the minimal content from Task 3.

- [ ] **Step 3: Implement the route wrappers and migrate the business panels**

Implement the three route files using this pattern:

```vue
<script setup>
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'
import ClientManagementPanel from '@/components/ClientManagementPanel.vue'
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Clients" description="Create, update, activate, and remove client access." />
      <ClientManagementPanel />
    </div>
  </DashboardLayout>
</template>
```

Repeat the same structure for `TenantCatalogView.vue` and `TenantCodeServicesView.vue`.

Then rework the three business panels so they use the new shared system:
- `ClientManagementPanel.vue`: keep current `loadClients`, `saveClient`, `toggleClientStatus`, `deleteClient`, and router push logic; replace only the template with shared table, inputs, buttons, inline alerts, and `StatusBadge`.
- `CatalogPanel.vue`: keep current delete-preview logic and helper imports; replace `window.prompt` with inline edit controls or shadcn dialog, and replace the custom modal with the shared dialog primitive.
- `CodeServicesTenantPanel.vue`: keep current fetch/save logic; replace only the template so it matches the shell.

For `CatalogPanel.vue`, the confirm-delete flow must still require typed confirmation and still call the existing `?confirm=true` backend endpoints.

- [ ] **Step 4: Run the smoke tests and the existing delete-preview helper test**

Run:
- `cd frontend && npx vitest run src/views/__tests__/TenantSectionViews.spec.js`
- `cd frontend && npx vitest run src/components/__tests__/catalogDeletePreview.spec.js`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/TenantClientsView.vue frontend/src/views/TenantCatalogView.vue frontend/src/views/TenantCodeServicesView.vue frontend/src/components/ClientManagementPanel.vue frontend/src/components/CatalogPanel.vue frontend/src/components/CodeServicesTenantPanel.vue frontend/src/views/__tests__/TenantSectionViews.spec.js
git commit -m "feat: migrate tenant management sections to shared shell"
```

---

### Task 8: Subscriptions workspace, reminder modal, and route-query filter sync

**Required skills:**
- `superpowers:test-driven-development`
- `superpowers:systematic-debugging`
- `vue-expert-js`
- `uncodixfy`
- `impeccable`

**Files:**
- Modify: `frontend/src/views/SubscriptionsView.vue`
- Modify: `frontend/src/components/subscriptions/ReminderSettingsModal.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionFilters.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionModal.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionRenewModal.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionReactivateModal.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionCancelModal.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionTable.vue`
- Test: `frontend/src/views/__tests__/SubscriptionsView.spec.js`

**Backend contract refs:**
- `backend/tests/test_subscriptions.py`

- [ ] **Step 1: Write the failing regression tests**

```js
// frontend/src/views/__tests__/SubscriptionsView.spec.js
import { describe, it, expect, vi } from 'vitest'
import { renderWithApp } from '@/test-utils/renderWithApp'
import SubscriptionsView from '../SubscriptionsView.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    loadTenantSettings: vi.fn().mockResolvedValue(),
  }),
}))

vi.mock('@/stores/i18n', () => ({
  useI18nStore: () => ({ t: key => key }),
}))

describe('SubscriptionsView regressions', () => {
  it('passes the current route client_id into the filter UI', async () => {
    api.get
      .mockResolvedValueOnce({ data: [{ id: 'c1', full_name: 'Client One' }] })
      .mockResolvedValueOnce({ data: [{ id: 's1', name: 'Netflix' }] })
      .mockResolvedValueOnce({ data: [{ id: 'p1', name: 'Basic' }] })
      .mockResolvedValueOnce({ data: [] })

    const wrapper = await renderWithApp(SubscriptionsView, {
      routes: [{ path: '/admin/subscriptions', component: SubscriptionsView }],
      path: '/admin/subscriptions?client_id=c1',
    })

    expect(wrapper.get('[data-testid="filter-client"]').element.value).toBe('c1')
  })

  it('opens the reminder settings modal when the button is clicked', async () => {
    api.get
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] })

    const wrapper = await renderWithApp(SubscriptionsView)
    await wrapper.get('[data-testid="open-reminder-settings"]').trigger('click')
    expect(wrapper.text()).toContain('frontend.subscriptions.reminder_settings_title')
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/views/__tests__/SubscriptionsView.spec.js`
Expected: FAIL because the filter component does not hydrate from route state and the reminder modal still uses the wrong prop contract.

- [ ] **Step 3: Fix the prop contract and filter-state sync before re-skinning the rest**

Make these exact logic changes first:

1. In `frontend/src/components/subscriptions/ReminderSettingsModal.vue`, rename the prop from `show` to `isOpen` and update both the template guard and the watcher to use `props.isOpen`.

```js
const props = defineProps({
  isOpen: { type: Boolean, default: false },
})

watch(() => props.isOpen, async (newVal) => {
  if (!newVal) return
  // existing load logic unchanged
})
```

2. In `frontend/src/views/SubscriptionsView.vue`, pass the right prop and add a stable test id.

```vue
<button
  data-testid="open-reminder-settings"
  @click="isReminderSettingsOpen = true"
  type="button"
  class="inline-flex h-9 items-center rounded-md border border-border bg-card px-3 text-sm font-medium"
>
  {{ i18nStore.t('frontend.subscriptions.reminder_settings') || 'Reminder settings' }}
</button>
<ReminderSettingsModal :isOpen="isReminderSettingsOpen" @close="isReminderSettingsOpen = false" @saved="handleSave" />
```

3. In `frontend/src/components/subscriptions/SubscriptionFilters.vue`, add an `initialFilters` prop, add `data-testid="filter-client"` to the client `<select>`, and hydrate the local `filters` ref from it.

```js
const props = defineProps({
  clients: { type: Array, required: true },
  services: { type: Array, required: true },
  t: { type: Function, required: true },
  initialFilters: {
    type: Object,
    default: () => ({ status: '', client_id: '', service_id: '', expires_from: '', expires_to: '' }),
  },
})

watch(
  () => props.initialFilters,
  (value) => {
    filters.value = {
      status: value?.status || '',
      client_id: value?.client_id || '',
      service_id: value?.service_id || '',
      expires_from: value?.expires_from || '',
      expires_to: value?.expires_to || '',
    }
  },
  { deep: true, immediate: true },
)
```

4. In `frontend/src/views/SubscriptionsView.vue`, pass `:initial-filters="activeFilters"` into `SubscriptionFilters`.

- [ ] **Step 4: Re-skin the subscription workspace without changing business behavior**

After the regression fixes pass, migrate the templates in:
- `SubscriptionsView.vue`
- `SubscriptionModal.vue`
- `SubscriptionRenewModal.vue`
- `SubscriptionReactivateModal.vue`
- `SubscriptionCancelModal.vue`
- `SubscriptionTable.vue`

Rules for this task:
- keep the same endpoint calls
- keep the same emitted events (`close`, `save`, `edit`, `renew`, `reactivate`, `cancel`)
- keep the current reveal-credentials logic in `SubscriptionTable.vue`
- keep the reminder-settings cache behavior from `authStore`
- remove hardcoded Spanish button text where translation props already exist; always use `t(...)`

- [ ] **Step 5: Run the regression tests and the full frontend test suite**

Run:
- `cd frontend && npx vitest run src/views/__tests__/SubscriptionsView.spec.js`
- `cd frontend && npm test`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/SubscriptionsView.vue frontend/src/components/subscriptions/ReminderSettingsModal.vue frontend/src/components/subscriptions/SubscriptionFilters.vue frontend/src/components/subscriptions/SubscriptionModal.vue frontend/src/components/subscriptions/SubscriptionRenewModal.vue frontend/src/components/subscriptions/SubscriptionReactivateModal.vue frontend/src/components/subscriptions/SubscriptionCancelModal.vue frontend/src/components/subscriptions/SubscriptionTable.vue frontend/src/views/__tests__/SubscriptionsView.spec.js
git commit -m "fix: restore subscriptions workflow on shared ui system"
```

---

### Task 9: Master and client dashboards on the new shell

**Required skills:**
- `superpowers:test-driven-development`
- `vue-expert-js`
- `uncodixfy`
- `impeccable`

**Files:**
- Modify: `frontend/src/views/MasterDashboardView.vue`
- Modify: `frontend/src/views/MasterCodeServicesView.vue`
- Modify: `frontend/src/components/CodeServicesGlobalPanel.vue`
- Modify: `frontend/src/views/ClientDashboardView.vue`
- Test: `frontend/src/views/__tests__/RoleDashboards.spec.js`

**Backend contract refs:**
- `backend/tests/test_tenants.py`
- `backend/tests/test_code_services.py`
- `backend/tests/test_profile.py`
- `backend/tests/test_subscriptions.py`

- [ ] **Step 1: Write the failing dashboard smoke tests**

```js
// frontend/src/views/__tests__/RoleDashboards.spec.js
import { describe, it, expect } from 'vitest'
import { renderWithApp } from '@/test-utils/renderWithApp'
import MasterDashboardView from '../MasterDashboardView.vue'
import ClientDashboardView from '../ClientDashboardView.vue'

describe('role dashboards', () => {
  it('renders the master overview page shell', async () => {
    const wrapper = await renderWithApp(MasterDashboardView)
    expect(wrapper.text()).toContain('Overview')
  })

  it('renders the client overview page shell', async () => {
    const wrapper = await renderWithApp(ClientDashboardView)
    expect(wrapper.text()).toContain('Security')
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/views/__tests__/RoleDashboards.spec.js`
Expected: FAIL because the current pages still use the older ad-hoc layout.

- [ ] **Step 3: Migrate the master and client pages**

Implementation rules:
- `MasterDashboardView.vue`: keep `loadTenants`, create/edit/deactivate/delete tenant flows, and `manageCatalog()` logic; rework the template to use `PageHeader`, shared tables, shared alerts, and route the code-services area out of overview.
- `MasterCodeServicesView.vue`: render only `CodeServicesGlobalPanel` under the shared shell and header.
- `CodeServicesGlobalPanel.vue`: keep its fetch/save logic; replace only the template and status rendering.
- `ClientDashboardView.vue`: keep `/dashboard`, `/me`, and `/me/password`; rework the template to use `PageHeader`, `StatusBadge`, `InlineAlert`, and the shared table primitives.

Important: update any hardcoded `/client/dashboard` pushes or redirects still remaining in these pages to `/client/overview`.

- [ ] **Step 4: Run the dashboard smoke tests and a production build**

Run:
- `cd frontend && npx vitest run src/views/__tests__/RoleDashboards.spec.js`
- `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/MasterDashboardView.vue frontend/src/views/MasterCodeServicesView.vue frontend/src/components/CodeServicesGlobalPanel.vue frontend/src/views/ClientDashboardView.vue frontend/src/views/__tests__/RoleDashboards.spec.js
git commit -m "feat: migrate master and client dashboards to shared shell"
```

---

### Task 10: Documentation refresh and final verification

**Required skills:**
- `docs`
- `superpowers:verification-before-completion`
- `requesting-code-review`

**Files:**
- Modify: `docs/architecture/frontend-architecture.md`
- Modify: `docs/codebase/frontend-structure.md`
- Modify: `docs/code-standard/frontend-conventions.md`

- [ ] **Step 1: Update the docs to match the new route map and component layout**

Update `docs/architecture/frontend-architecture.md` so it describes:
- the canonical routes (`/master/overview`, `/admin/*`, `/client/overview`)
- support-mode navigation behavior
- the split tenant workflow pages
- shadcn-based UI primitives and shared shell

Update `docs/codebase/frontend-structure.md` so it lists:
- `src/config/navigation.js`
- the new `src/components/ui/` directory
- the new tenant route files
- the new shared components (`PageHeader`, `InlineAlert`, `StatusBadge`, etc.)

Update `docs/code-standard/frontend-conventions.md` so it records:
- alias usage (`@/...`)
- shadcn/tailwind shared-component rules
- the “keep business logic, replace template” migration rule for future UI work
- the expectation to write a view/component test for new shared UI work

- [ ] **Step 2: Run the final verification commands**

Run:
- `cd frontend && npm test`
- `cd frontend && npm run build`
- `cd backend && uv run pytest tests/test_auth.py tests/test_tenants.py tests/test_profile.py tests/test_catalog.py tests/test_clients.py tests/test_subscriptions.py tests/test_code_services.py tests/test_mailbox_oauth_imap.py tests/test_mailbox_persistence.py -q`

Expected:
- Frontend Vitest: PASS
- Frontend build: PASS
- Backend contract suite: PASS

- [ ] **Step 3: Request a code review before merge**

Run the code review workflow after the tests/build pass. The review checklist must explicitly verify:
- the three known regressions are fixed
- support-mode navigation uses tenant routes but hides `/admin/settings`
- login, master, tenant, subscriptions, mailbox, and client surfaces all still reach the same backend endpoints
- the UI uses shared primitives instead of ad-hoc card/button/input markup

- [ ] **Step 4: Commit the docs update**

```bash
git add docs/architecture/frontend-architecture.md docs/codebase/frontend-structure.md docs/code-standard/frontend-conventions.md
git commit -m "docs: update frontend architecture after redesign"
```

---

## Spec coverage self-check

- **Goal / system-first approach:** covered by Tasks 1-3.
- **Dual theme:** covered by Task 2.
- **Login + app shell first slice:** covered by Tasks 3-4.
- **Navigation rethink:** covered by Task 3 and enforced in later tasks.
- **Cross-role consistency:** covered by Tasks 3, 5, 8, 9.
- **State/error/loading handling:** covered by Tasks 2, 5, 6, 7, 8, 9.
- **Accessibility + shared primitives:** covered by Tasks 2-4.
- **Testing expectations:** covered in every task via Vitest + final verification.
- **Docs update:** covered by Task 10.

## Placeholder scan

This plan intentionally contains no `TODO`, `TBD`, or “similar to Task N” instructions. Each task has:
- exact file paths
- exact commands
- explicit regression or behavior goals
- at least one concrete code block for the critical change

## Type / prop consistency check

- Router canonical paths use `/master/overview`, `/admin/overview`, `/client/overview` consistently.
- Support-mode route flag is `allowMasterSupport` everywhere.
- Reminder modal prop is standardized to `isOpen` to match the other subscription modals.
- Shared shell navigation derives from `getNavigationContext(authStore, route)`, not raw `authStore.role` alone.
