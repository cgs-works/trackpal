# Dark Command Center Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Trackpal frontend presentation as a dark-only command center while preserving existing Vue/Pinia/router/API behavior.

**Architecture:** Keep current business logic in views and panels, replace presentation and interaction patterns with dark-only shadcn-vue primitives. Introduce small shared workspace components for summary metrics, inspectors, and impact confirmations so pages do not duplicate layout behavior.

**Tech Stack:** Vue 3 Composition API, JavaScript ESM, Pinia, vue-router, Axios, Tailwind CSS v4, shadcn-vue/Reka UI, Vitest, @vue/test-utils.

---

## Spec and Design Inputs

- Design source: `DESIGN.md`
- Feature spec: `docs/superpowers/specs/2026-06-10-dark-command-center-frontend.md`
- Frontend architecture docs: `docs/architecture/frontend-architecture.md`
- Frontend structure docs: `docs/codebase/frontend-structure.md`
- Frontend conventions: `docs/code-standard/frontend-conventions.md`

## Global Implementation Rules

1. Preserve existing `<script setup>` business logic unless a task explicitly changes state shape for dialog/inspector behavior.
2. Use `@/...` imports for new frontend code.
3. Use shadcn primitives from `@/components/ui/*` for controls.
4. Do not add TypeScript.
5. Do not add light-mode UI.
6. Do not use inline editing for tenants, clients, services, plans, or subscriptions.
7. Add tests before implementation in every task.
8. Run the task-specific test after each implementation step.
9. Commit after each task.
10. Do not stage `.superpowers/brainstorm/` files.
11. Run Task 0 before any UI task. The plan assumes shadcn-vue primitives exist locally after Task 0.

## File Structure

### New files

- `frontend/src/lib/darkTheme.js` — forces dark-only root class/color-scheme during bootstrap.
- `frontend/src/lib/__tests__/darkTheme.spec.js` — tests dark-only theme behavior.
- `frontend/src/components/SummaryMetric.vue` — compact metric block used by summary-first pages.
- `frontend/src/components/EntityInspector.vue` — reusable read-only selected-entity inspector with cyan active border.
- `frontend/src/components/ImpactConfirmDialog.vue` — reusable destructive confirmation dialog with impact rows.
- `frontend/src/components/__tests__/CommandCenterPrimitives.spec.js` — tests shared workspace primitives.

### Modified files

- `frontend/package.json` — add local `shadcn-vue` dev dependency if missing.
- `frontend/package-lock.json` — lock the shadcn-vue CLI dependency.
- `frontend/components.json` — verify JavaScript shadcn-vue configuration and aliases.
- `frontend/jsconfig.json` — verify `@/*` alias for Vue and shadcn imports.
- `frontend/src/components/ui/*` — generate or verify required shadcn-vue primitives.
- `frontend/src/main.js` — call `applyDarkTheme()` before mount.
- `frontend/src/style.css` — replace light/dark variable split with dark-only command-center tokens.
- `frontend/src/components/DashboardLayout.vue` — remove `ThemeToggle`, remove light classes, cyan active nav, dark-only mobile sheet.
- `frontend/src/views/LoginView.vue` — compact single-card login with vertical divider, no theme toggle, shadcn inputs/buttons.
- `frontend/src/views/MasterDashboardView.vue` — summary-first tenants workspace, dialog create/edit, inspector, visible row actions, impact delete confirm.
- `frontend/src/components/ClientManagementPanel.vue` — summary-first clients workspace, dialog create/edit, inspector, visible row actions, impact delete confirm.
- `frontend/src/components/CatalogPanel.vue` — summary-first catalog workspace, dialog create/edit, preserve typed delete preview.
- `frontend/src/views/SubscriptionsView.vue` — summary-first subscriptions workspace and inspector wiring.
- `frontend/src/components/subscriptions/SubscriptionTable.vue` — selectable rows, visible actions, preserve credential reveal.
- `frontend/src/components/subscriptions/SubscriptionFilters.vue` — preserve route-query hydration via `initialFilters`.
- `frontend/src/components/subscriptions/ReminderSettingsModal.vue` — keep `isOpen` visibility contract.
- `frontend/src/components/MailboxConfigPanel.vue` — dark-only command-center surface and visible states.
- `frontend/src/views/TenantMailboxView.vue` — preserve 404 empty config and OAuth query feedback.
- `frontend/src/components/CodeServicesGlobalPanel.vue` — dark-only summary-first presentation.
- `frontend/src/components/CodeServicesTenantPanel.vue` — dark-only summary-first presentation.
- `frontend/src/views/ClientDashboardView.vue` — dark-only client portal, no legacy light CSS dependency.
- `frontend/src/components/ThemeToggle.vue` — delete after removing imports.
- `frontend/src/composables/useTheme.js` — delete after replacing with `darkTheme.js`.
- `frontend/src/views/__tests__/LoginView.spec.js` — update for new login layout and no theme toggle.
- `frontend/src/components/__tests__/DashboardLayout.spec.js` — update for dark-only shell and mobile nav.
- `frontend/src/views/__tests__/RoleDashboards.spec.js` — update master/client dashboard expectations.
- `frontend/src/views/__tests__/TenantSectionViews.spec.js` — update tenant section smoke tests.
- `frontend/src/views/__tests__/SubscriptionsView.spec.js` — update subscription filter/inspector/modal tests.
- `frontend/src/views/__tests__/TenantMailboxView.spec.js` — preserve 404/OAuth behavior expectations.
- `docs/architecture/frontend-architecture.md` — update dark-only architecture and component list.
- `docs/codebase/frontend-structure.md` — update structure and remove theme toggle references.
- `docs/code-standard/frontend-conventions.md` — update dark-only styling conventions.

---

## Task 0: Install and Verify shadcn-vue Foundation

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Verify/Modify: `frontend/components.json`
- Verify/Modify: `frontend/jsconfig.json`
- Create/Verify: `frontend/src/components/ui/*`

This task is mandatory because implementers must not assume shadcn-vue is globally installed. The CLI must be available from the frontend project and the required primitives must exist before UI migration tasks begin.

- [ ] **Step 1: Verify shadcn-vue is missing or present locally**

Run:

```bash
cd frontend && npm ls shadcn-vue --depth=0
```

Expected before this task in the current repo: FAIL / missing dependency. If it already passes in a future branch, continue to Step 3 and still verify primitives.

- [ ] **Step 2: Install local shadcn-vue CLI and required runtime packages**

Run:

```bash
cd frontend && npm install -D shadcn-vue && npm install reka-ui lucide-vue-next tailwind-merge clsx class-variance-authority tw-animate-css vue-sonner
```

Expected: `package.json` and `package-lock.json` include `shadcn-vue` plus required runtime dependencies. Existing dependencies may be reported as up to date.

- [ ] **Step 3: Verify `components.json` uses JavaScript mode and aliases**

Ensure `frontend/components.json` exists with this shape. If it differs, update it to match existing project paths:

```json
{
  "$schema": "https://shadcn-vue.com/schema.json",
  "style": "new-york",
  "typescript": false,
  "tsConfigPath": "jsconfig.json",
  "tailwind": {
    "config": "",
    "css": "src/style.css",
    "baseColor": "zinc",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "composables": "@/composables",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib"
  }
}
```

- [ ] **Step 4: Verify `jsconfig.json` has the `@/*` alias**

Ensure `frontend/jsconfig.json` exists:

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 5: Generate required shadcn-vue primitives**

Run:

```bash
cd frontend && npx shadcn-vue@latest add button input textarea select dialog sheet tabs badge dropdown-menu table separator switch checkbox card sonner
```

Expected: component directories exist under `frontend/src/components/ui/` for every primitive listed in the command. If a component already exists, accept overwrite only when it does not remove project-specific fixes; otherwise skip overwrite and verify exports.

- [ ] **Step 6: Verify generated primitive imports**

Run:

```bash
cd frontend && node -e "const fs=require('fs'); for (const name of ['button','input','textarea','select','dialog','sheet','tabs','badge','dropdown-menu','table','separator','switch','checkbox','card','sonner']) { const p='src/components/ui/'+name+'/index.js'; if (!fs.existsSync(p)) { console.error('missing '+p); process.exit(1); } } console.log('shadcn primitives ready')"
```

Expected: `shadcn primitives ready`.

- [ ] **Step 7: Verify dependency installation**

Run:

```bash
cd frontend && npm ls shadcn-vue reka-ui lucide-vue-next tailwind-merge clsx class-variance-authority tw-animate-css vue-sonner --depth=0
```

Expected: PASS with all packages listed.

- [ ] **Step 8: Run frontend tests and build smoke check**

Run:

```bash
cd frontend && npm test && npm run build
```

Expected: PASS. If generated primitives changed snapshots or markup, fix only shadcn import/export issues before moving to Task 1.

- [ ] **Step 9: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/components.json frontend/jsconfig.json frontend/src/components/ui
git commit -m "chore: install shadcn-vue foundation"
```

---

## Task 1: Dark-Only Theme Foundation

**Files:**
- Create: `frontend/src/lib/darkTheme.js`
- Create: `frontend/src/lib/__tests__/darkTheme.spec.js`
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/style.css`
- Delete: `frontend/src/components/ThemeToggle.vue`
- Delete: `frontend/src/composables/useTheme.js`

- [ ] **Step 1: Write the failing dark theme tests**

Create `frontend/src/lib/__tests__/darkTheme.spec.js`:

```js
import { beforeEach, describe, expect, it } from 'vitest'
import { applyDarkTheme } from '@/lib/darkTheme'

describe('applyDarkTheme', () => {
  beforeEach(() => {
    document.documentElement.className = ''
    document.documentElement.style.colorScheme = ''
    localStorage.clear()
  })

  it('forces the document into dark mode', () => {
    localStorage.setItem('theme', 'light')

    applyDarkTheme()

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')
  })

  it('is safe to call more than once', () => {
    applyDarkTheme()
    applyDarkTheme()

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe('dark')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd frontend && npm test -- src/lib/__tests__/darkTheme.spec.js
```

Expected: FAIL because `@/lib/darkTheme` does not exist.

- [ ] **Step 3: Implement dark-only theme bootstrap**

Create `frontend/src/lib/darkTheme.js`:

```js
export function applyDarkTheme() {
  if (typeof document === 'undefined') return

  document.documentElement.classList.add('dark')
  document.documentElement.style.colorScheme = 'dark'

  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('theme', 'dark')
  }
}
```

Modify `frontend/src/main.js`:

```js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { useI18nStore } from './stores/i18n'
import { applyDarkTheme } from './lib/darkTheme'

applyDarkTheme()

const app = createApp(App)

app.use(createPinia())
app.use(router)

const authStore = useAuthStore()
if (authStore.isAuthenticated) {
  useI18nStore().loadCatalog()
}

app.mount('#app')
```

- [ ] **Step 4: Replace `frontend/src/style.css` with dark command-center tokens**

Use this structure and preserve the `@import` lines:

```css
@import "tailwindcss";
@import "tw-animate-css";

:root,
.dark {
  --background: oklch(0.035 0 0);
  --foreground: oklch(0.94 0.003 95);
  --card: oklch(0.075 0.004 285);
  --card-foreground: oklch(0.94 0.003 95);
  --muted: oklch(0.12 0.004 285);
  --muted-foreground: oklch(0.68 0.01 95);
  --border: oklch(0.18 0.005 285);
  --input: oklch(0.18 0.005 285);
  --ring: oklch(0.78 0.11 210);
  --primary: oklch(0.78 0.11 210);
  --primary-foreground: oklch(0.06 0 0);
  --success: oklch(0.72 0.13 150);
  --warning: oklch(0.78 0.14 80);
  --destructive: oklch(0.68 0.18 25);
  --sidebar: oklch(0.06 0.003 285);
  --sidebar-foreground: oklch(0.9 0.003 95);
  --surface-raised: oklch(0.105 0.004 285);
  --surface-hover: oklch(0.14 0.004 285);
  --surface-selected: oklch(0.18 0.006 285);
  --border-strong: oklch(0.27 0.008 285);
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
  --color-surface-raised: var(--surface-raised);
  --color-surface-hover: var(--surface-hover);
  --color-surface-selected: var(--surface-selected);
  --color-border-strong: var(--border-strong);
}

@layer base {
  * {
    @apply border-border;
  }

  html {
    color-scheme: dark;
    background: var(--background);
  }

  body {
    @apply min-h-screen bg-background text-foreground antialiased;
  }
}
```

- [ ] **Step 5: Remove theme toggle files after imports are removed in later tasks**

Do not delete `ThemeToggle.vue` or `useTheme.js` until Tasks 3 and 4 remove their imports from `DashboardLayout.vue` and `LoginView.vue`.

- [ ] **Step 6: Run the theme test**

Run:

```bash
cd frontend && npm test -- src/lib/__tests__/darkTheme.spec.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/darkTheme.js frontend/src/lib/__tests__/darkTheme.spec.js frontend/src/main.js frontend/src/style.css
git commit -m "feat: force dark command center theme"
```

---

## Task 2: Shared Command-Center Primitives

**Files:**
- Create: `frontend/src/components/SummaryMetric.vue`
- Create: `frontend/src/components/EntityInspector.vue`
- Create: `frontend/src/components/ImpactConfirmDialog.vue`
- Create: `frontend/src/components/__tests__/CommandCenterPrimitives.spec.js`

- [ ] **Step 1: Write failing primitive tests**

Create `frontend/src/components/__tests__/CommandCenterPrimitives.spec.js`:

```js
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SummaryMetric from '@/components/SummaryMetric.vue'
import EntityInspector from '@/components/EntityInspector.vue'
import ImpactConfirmDialog from '@/components/ImpactConfirmDialog.vue'

describe('command center primitives', () => {
  it('renders a compact summary metric', () => {
    const wrapper = mount(SummaryMetric, {
      props: { label: 'Active', value: '12', tone: 'success' },
    })

    expect(wrapper.text()).toContain('Active')
    expect(wrapper.text()).toContain('12')
    expect(wrapper.classes()).toContain('border-border')
  })

  it('renders inspector fields and emits edit', async () => {
    const wrapper = mount(EntityInspector, {
      props: {
        title: 'Client detail',
        description: 'Selected client',
        fields: [
          { label: 'Name', value: 'Ana' },
          { label: 'Status', value: 'Active' },
        ],
      },
    })

    expect(wrapper.text()).toContain('Client detail')
    expect(wrapper.text()).toContain('Ana')
    expect(wrapper.classes()).toContain('border-primary')

    await wrapper.get('[data-testid="inspector-edit"]').trigger('click')
    expect(wrapper.emitted('edit')).toHaveLength(1)
  })

  it('renders destructive impact details and emits confirm', async () => {
    const wrapper = mount(ImpactConfirmDialog, {
      props: {
        open: true,
        title: 'Delete client',
        description: 'This client will be removed.',
        targetName: 'Ana',
        impacts: [
          { label: 'Subscriptions', value: '2 affected' },
        ],
        confirmLabel: 'Delete',
      },
    })

    expect(wrapper.text()).toContain('Delete client')
    expect(wrapper.text()).toContain('Ana')
    expect(wrapper.text()).toContain('2 affected')

    await wrapper.get('[data-testid="impact-confirm"]').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd frontend && npm test -- src/components/__tests__/CommandCenterPrimitives.spec.js
```

Expected: FAIL because the components do not exist.

- [ ] **Step 3: Create `SummaryMetric.vue`**

```vue
<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  hint: { type: String, default: '' },
  tone: { type: String, default: 'neutral' },
})

const toneClasses = computed(() => ({
  neutral: 'text-foreground',
  success: 'text-success',
  warning: 'text-warning',
  destructive: 'text-destructive',
  accent: 'text-primary',
}[props.tone] || 'text-foreground'))
</script>

<template>
  <section class="rounded-xl border border-border bg-card p-4">
    <p class="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">{{ label }}</p>
    <p :class="cn('mt-2 text-2xl font-semibold tracking-tight', toneClasses)">{{ value }}</p>
    <p v-if="hint" class="mt-1 text-xs text-muted-foreground">{{ hint }}</p>
  </section>
</template>
```

- [ ] **Step 4: Create `EntityInspector.vue`**

```vue
<script setup>
import { Button } from '@/components/ui/button'

const props = defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  fields: { type: Array, default: () => [] },
  editLabel: { type: String, default: 'Edit' },
  canEdit: { type: Boolean, default: true },
})

defineEmits(['edit'])
</script>

<template>
  <aside class="rounded-xl border border-primary bg-card p-4 shadow-2xl shadow-black/20">
    <div class="flex items-start justify-between gap-3">
      <div>
        <h2 class="text-sm font-semibold tracking-tight text-foreground">{{ title }}</h2>
        <p v-if="description" class="mt-1 text-xs text-muted-foreground">{{ description }}</p>
      </div>
      <Button v-if="canEdit" data-testid="inspector-edit" size="sm" variant="outline" @click="$emit('edit')">
        {{ editLabel }}
      </Button>
    </div>

    <dl class="mt-4 space-y-3">
      <div v-for="field in fields" :key="field.label" class="rounded-lg border border-border bg-background p-3">
        <dt class="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">{{ field.label }}</dt>
        <dd class="mt-1 text-sm text-foreground">{{ field.value || '—' }}</dd>
      </div>
    </dl>

    <slot />
  </aside>
</template>
```

- [ ] **Step 5: Create `ImpactConfirmDialog.vue`**

```vue
<script setup>
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, required: true },
  description: { type: String, required: true },
  targetName: { type: String, default: '' },
  impacts: { type: Array, default: () => [] },
  confirmLabel: { type: String, default: 'Confirm' },
  cancelLabel: { type: String, default: 'Cancel' },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:open', 'confirm'])
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>{{ title }}</DialogTitle>
        <DialogDescription>{{ description }}</DialogDescription>
      </DialogHeader>

      <div class="space-y-3">
        <div v-if="targetName" class="rounded-lg border border-border bg-background p-3">
          <p class="text-xs text-muted-foreground">Target</p>
          <p class="text-sm font-medium text-foreground">{{ targetName }}</p>
        </div>

        <div v-if="impacts.length" class="rounded-lg border border-destructive/40 bg-destructive/10 p-3">
          <p class="text-xs font-medium uppercase tracking-[0.16em] text-destructive">Impact</p>
          <dl class="mt-2 space-y-2">
            <div v-for="impact in impacts" :key="impact.label" class="flex items-center justify-between gap-3 text-sm">
              <dt class="text-muted-foreground">{{ impact.label }}</dt>
              <dd class="font-medium text-foreground">{{ impact.value }}</dd>
            </div>
          </dl>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" :disabled="loading" @click="emit('update:open', false)">{{ cancelLabel }}</Button>
        <Button data-testid="impact-confirm" variant="destructive" :disabled="loading" @click="emit('confirm')">
          {{ loading ? 'Working…' : confirmLabel }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
```

- [ ] **Step 6: Run the primitive tests**

Run:

```bash
cd frontend && npm test -- src/components/__tests__/CommandCenterPrimitives.spec.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/SummaryMetric.vue frontend/src/components/EntityInspector.vue frontend/src/components/ImpactConfirmDialog.vue frontend/src/components/__tests__/CommandCenterPrimitives.spec.js
git commit -m "feat: add command center workspace primitives"
```

---

## Task 3: Dark-Only App Shell

**Files:**
- Modify: `frontend/src/components/DashboardLayout.vue`
- Modify: `frontend/src/components/__tests__/DashboardLayout.spec.js`
- Delete: `frontend/src/components/ThemeToggle.vue` after imports are removed
- Delete: `frontend/src/composables/useTheme.js` after imports are removed

- [ ] **Step 1: Update the failing app shell tests first**

In `frontend/src/components/__tests__/DashboardLayout.spec.js`, add tests that assert no theme toggle is rendered and active nav uses command-center classes:

```js
it('does not render a theme toggle in the dark-only shell', async () => {
  const { wrapper } = renderWithApp(DashboardLayout, {
    auth: { user: { role: 'tenant', username: 'tenant' }, token: 'token' },
    route: '/admin/overview',
  })

  await wrapper.vm.$nextTick()

  expect(wrapper.find('[aria-label="Toggle Theme"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('Trackpal')
})

it('keeps support mode exit visible in the sidebar', async () => {
  const { wrapper } = renderWithApp(DashboardLayout, {
    auth: { user: { role: 'master', username: 'master' }, token: 'token', activeTenantId: 1 },
    route: '/admin/overview',
  })

  await wrapper.vm.$nextTick()

  expect(wrapper.text()).toContain('Exit support')
})
```

Use the existing test helper shape in the file. If the helper uses a different auth injection shape, set the Pinia auth store in the same way existing tests do.

- [ ] **Step 2: Run the shell test to verify it fails**

Run:

```bash
cd frontend && npm test -- src/components/__tests__/DashboardLayout.spec.js
```

Expected: FAIL because `ThemeToggle` still renders.

- [ ] **Step 3: Remove `ThemeToggle` import and usage**

In `DashboardLayout.vue`:

- Remove `import ThemeToggle from '@/components/ThemeToggle.vue'`.
- Remove both `<ThemeToggle />` instances.
- Keep the language selector.
- Replace light/dark classes with dark-only classes.
- Replace indigo active nav with cyan/primary active nav.

Use this active nav function:

```js
function navLinkClasses(itemPath) {
  return [
    route.path === itemPath
      ? 'border-primary bg-primary/10 text-primary'
      : 'border-transparent text-muted-foreground hover:border-border-strong hover:bg-surface-hover hover:text-foreground',
    'flex items-center gap-3 rounded-md border px-3 py-2 text-sm font-medium transition-colors',
  ]
}
```

Use these shell surface classes:

```vue
<div class="min-h-screen bg-background text-foreground flex">
  <aside class="hidden md:flex flex-col h-screen w-64 bg-sidebar border-r border-border flex-shrink-0 sticky top-0">
```

Use this main content class:

```vue
<main class="flex-1 overflow-y-auto p-4 md:p-6">
  <slot />
</main>
```

- [ ] **Step 4: Delete old theme files**

After DashboardLayout and LoginView no longer import them, delete:

```bash
rm frontend/src/components/ThemeToggle.vue frontend/src/composables/useTheme.js
```

If deletion fails because LoginView still imports `ThemeToggle`, wait until Task 4 and delete then.

- [ ] **Step 5: Run shell tests**

Run:

```bash
cd frontend && npm test -- src/components/__tests__/DashboardLayout.spec.js
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/DashboardLayout.vue frontend/src/components/__tests__/DashboardLayout.spec.js
git add -u frontend/src/components/ThemeToggle.vue frontend/src/composables/useTheme.js
git commit -m "feat: make app shell dark-only"
```

---

## Task 4: Compact Single-Card Login

**Files:**
- Modify: `frontend/src/views/LoginView.vue`
- Modify: `frontend/src/views/__tests__/LoginView.spec.js`
- Delete: `frontend/src/components/ThemeToggle.vue` if still present
- Delete: `frontend/src/composables/useTheme.js` if still present

- [ ] **Step 1: Update LoginView tests first**

In `frontend/src/views/__tests__/LoginView.spec.js`, add or update tests:

```js
it('renders the compact single-card login without theme toggle', () => {
  const wrapper = mount(LoginView, {
    global: {
      plugins: [createTestingPinia()],
      mocks: { $router: { push: vi.fn() } },
      stubs: ['RouterLink'],
    },
  })

  expect(wrapper.find('[data-testid="login-card"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="login-divider"]').exists()).toBe(true)
  expect(wrapper.find('[aria-label="Toggle Theme"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('Trackpal')
})
```

Keep the existing async redirect test and ensure it still asserts the route path after `flushPromises()`.

- [ ] **Step 2: Run the login tests to verify failure**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/LoginView.spec.js
```

Expected: FAIL because current login uses a two-zone layout and theme toggle.

- [ ] **Step 3: Preserve script logic and update imports**

In `LoginView.vue`:

- Keep `handleSubmit()` logic.
- Remove `ThemeToggle` import.
- Add shadcn imports:

```js
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import InlineAlert from '@/components/InlineAlert.vue'
```

Convert relative imports to alias imports:

```js
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import { usePublicI18n } from '@/i18n/usePublicI18n'
```

- [ ] **Step 4: Replace template with compact single-card layout**

Use this structure:

```vue
<template>
  <main class="flex min-h-screen items-center justify-center bg-background px-4 py-8 text-foreground">
    <section
      data-testid="login-card"
      class="grid w-full max-w-2xl grid-cols-1 gap-6 rounded-2xl border border-border bg-card p-5 shadow-2xl shadow-black/40 md:grid-cols-[220px_1px_1fr] md:items-center md:p-6"
    >
      <div class="space-y-5">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-foreground text-sm font-bold text-background">T</div>
          <p class="text-lg font-semibold tracking-tight">Trackpal</p>
        </div>
        <div class="space-y-2">
          <h1 class="text-2xl font-semibold tracking-tight">{{ t('login.title') }}</h1>
          <p class="text-sm leading-6 text-muted-foreground">Control tenants, clients, subscriptions and mailbox access from one dark command center.</p>
        </div>
      </div>

      <div data-testid="login-divider" class="hidden h-56 w-px bg-border md:block" />

      <form class="space-y-4" @submit.prevent="handleSubmit">
        <div class="space-y-1.5">
          <label for="username" class="text-sm font-medium">{{ t('login.username') }}</label>
          <Input id="username" v-model="username" type="text" autocomplete="username" required />
        </div>
        <div class="space-y-1.5">
          <label for="password" class="text-sm font-medium">{{ t('login.password') }}</label>
          <Input id="password" v-model="password" type="password" autocomplete="current-password" required />
        </div>
        <InlineAlert v-if="errorMessage" variant="error" :message="errorMessage" />
        <div class="flex items-center justify-between gap-3">
          <select id="locale-select" v-model="locale" @change="setLocale(locale)" class="h-9 rounded-md border border-input bg-background px-3 text-xs text-muted-foreground">
            <option value="en">English</option>
            <option value="es">Español</option>
          </select>
          <Button type="submit" :disabled="isLoading" class="min-w-32">
            {{ isLoading ? t('login.signing_in') : t('login.sign_in') }}
          </Button>
        </div>
      </form>
    </section>
  </main>
</template>
```

- [ ] **Step 5: Delete old theme files if still present**

Run:

```bash
rm -f frontend/src/components/ThemeToggle.vue frontend/src/composables/useTheme.js
```

- [ ] **Step 6: Run login and theme tests**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/LoginView.spec.js src/lib/__tests__/darkTheme.spec.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/LoginView.vue frontend/src/views/__tests__/LoginView.spec.js
git add -u frontend/src/components/ThemeToggle.vue frontend/src/composables/useTheme.js
git commit -m "feat: redesign login as compact dark card"
```

---

## Task 5: Master Tenants Workspace

**Files:**
- Modify: `frontend/src/views/MasterDashboardView.vue`
- Modify: `frontend/src/views/__tests__/RoleDashboards.spec.js`
- Use: `frontend/src/components/SummaryMetric.vue`
- Use: `frontend/src/components/EntityInspector.vue`
- Use: `frontend/src/components/ImpactConfirmDialog.vue`

- [ ] **Step 1: Add failing master workspace tests**

In `RoleDashboards.spec.js`, add tests for summary metrics, inspector, visible actions, and dialog editing:

```js
it('renders tenants as a summary-first selectable workspace', async () => {
  api.get.mockResolvedValueOnce({
    data: {
      total_tenants: 2,
      active_tenants: 1,
      inactive_tenants: 1,
      tenants: [
        { id: 1, full_name: 'Tenant A', email: 'a@example.com', phone: '111', is_active: true },
        { id: 2, full_name: 'Tenant B', email: 'b@example.com', phone: '222', is_active: false },
      ],
    },
  })

  const wrapper = mountWithRoute(MasterDashboardView, '/master/overview')
  await flushPromises()

  expect(wrapper.text()).toContain('Total')
  expect(wrapper.text()).toContain('Active')
  expect(wrapper.find('[data-testid="tenant-row-1"]').exists()).toBe(true)

  await wrapper.get('[data-testid="tenant-row-1"]').trigger('click')
  expect(wrapper.find('[data-testid="tenant-inspector"]').exists()).toBe(true)
})

it('opens tenant edit dialog from visible row action without selecting the row', async () => {
  api.get.mockResolvedValueOnce({ data: { total_tenants: 1, active_tenants: 1, inactive_tenants: 0, tenants: [{ id: 1, full_name: 'Tenant A', email: 'a@example.com', phone: '111', is_active: true }] } })

  const wrapper = mountWithRoute(MasterDashboardView, '/master/overview')
  await flushPromises()

  await wrapper.get('[data-testid="tenant-edit-1"]').trigger('click')

  expect(wrapper.find('[data-testid="tenant-form-dialog"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="tenant-inspector"]').exists()).toBe(false)
})
```

Adapt `mountWithRoute` to the helper names already present in the file.

- [ ] **Step 2: Run the master dashboard tests to verify failure**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/RoleDashboards.spec.js
```

Expected: FAIL because selected inspectors and new test IDs do not exist.

- [ ] **Step 3: Add local state for selection/dialogs**

In `MasterDashboardView.vue`, preserve existing API functions and add:

```js
const selectedTenant = ref(null)
const isTenantDialogOpen = ref(false)
const tenantDialogMode = ref('create')
const deleteDialogOpen = ref(false)
const deleteTarget = ref(null)

function selectTenant(tenant) {
  selectedTenant.value = tenant
}

function openCreateTenantDialog() {
  tenantDialogMode.value = 'create'
  resetForm()
  isTenantDialogOpen.value = true
}

function openEditTenantDialog(tenant) {
  tenantDialogMode.value = 'edit'
  editTenant(tenant)
  isTenantDialogOpen.value = true
}

function openDeleteTenantDialog(tenant) {
  deleteTarget.value = tenant
  deleteDialogOpen.value = true
}
```

Replace direct `window.confirm` delete entry with `openDeleteTenantDialog(tenant)`. Keep the existing API delete logic in a `confirmTenantDelete()` function.

- [ ] **Step 4: Replace template with summary-first workspace**

The template must include:

- `PageHeader` with primary create button.
- `SummaryMetric` row for total/active/inactive.
- shadcn `Table` for tenants.
- Row `@click="selectTenant(tenant)"`.
- Row action buttons with `@click.stop`.
- `EntityInspector` rendered when `selectedTenant` exists.
- `Dialog` for create/edit form.
- `ImpactConfirmDialog` for tenant delete.

Required test IDs:

```vue
<TableRow
  v-for="tenant in tenants"
  :key="tenant.id"
  :data-testid="`tenant-row-${tenant.id}`"
  :class="selectedTenant?.id === tenant.id ? 'bg-surface-selected border-border-strong' : 'hover:bg-surface-hover'"
  @click="selectTenant(tenant)"
>
```

```vue
<Button :data-testid="`tenant-edit-${tenant.id}`" size="sm" variant="outline" @click.stop="openEditTenantDialog(tenant)">Edit</Button>
<Button size="sm" variant="outline" @click.stop="toggleTenantStatus(tenant)">{{ tenant.is_active ? 'Deactivate' : 'Activate' }}</Button>
<Button size="sm" variant="destructive" @click.stop="openDeleteTenantDialog(tenant)">Delete</Button>
```

```vue
<EntityInspector
  v-if="selectedTenant"
  data-testid="tenant-inspector"
  title="Tenant detail"
  :description="selectedTenant.full_name"
  :fields="[
    { label: 'Email', value: selectedTenant.email },
    { label: 'Phone', value: selectedTenant.phone },
    { label: 'Status', value: selectedTenant.is_active ? 'Active' : 'Inactive' },
  ]"
  @edit="openEditTenantDialog(selectedTenant)"
/>
```

- [ ] **Step 5: Run master dashboard tests**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/RoleDashboards.spec.js
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/MasterDashboardView.vue frontend/src/views/__tests__/RoleDashboards.spec.js
git commit -m "feat: convert tenants to command center workspace"
```

---

## Task 6: Tenant Clients Workspace

**Files:**
- Modify: `frontend/src/components/ClientManagementPanel.vue`
- Modify: `frontend/src/views/__tests__/TenantSectionViews.spec.js`
- Use: `SummaryMetric`, `EntityInspector`, `ImpactConfirmDialog`

- [ ] **Step 1: Add failing clients workspace tests**

In `TenantSectionViews.spec.js`, add a test that mounts `TenantClientsView` and verifies client selection opens an inspector and edit opens a dialog:

```js
it('renders clients with visible actions, dialog editing, and inspector selection', async () => {
  api.get.mockResolvedValueOnce({
    data: [
      { id: 10, full_name: 'Client A', username: 'clienta', phone: '555', is_active: true },
    ],
  })

  const wrapper = mountTenantRoute(TenantClientsView, '/admin/clients')
  await flushPromises()

  expect(wrapper.find('[data-testid="client-row-10"]').exists()).toBe(true)

  await wrapper.get('[data-testid="client-row-10"]').trigger('click')
  expect(wrapper.find('[data-testid="client-inspector"]').exists()).toBe(true)

  await wrapper.get('[data-testid="client-edit-10"]').trigger('click')
  expect(wrapper.find('[data-testid="client-form-dialog"]').exists()).toBe(true)
})
```

Use the mount helper already defined in `TenantSectionViews.spec.js`. If it has a different name, keep its current setup and only add the assertions.

- [ ] **Step 2: Run tenant section tests to verify failure**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/TenantSectionViews.spec.js
```

Expected: FAIL because clients do not expose the new inspector/dialog test IDs.

- [ ] **Step 3: Add selection and dialog state to `ClientManagementPanel.vue`**

Preserve API functions. Add:

```js
const selectedClient = ref(null)
const isClientDialogOpen = ref(false)
const clientDialogMode = ref('create')
const deleteDialogOpen = ref(false)
const deleteTarget = ref(null)

function selectClient(client) {
  selectedClient.value = client
}

function openCreateClientDialog() {
  clientDialogMode.value = 'create'
  resetForm()
  isClientDialogOpen.value = true
}

function openEditClientDialog(client) {
  clientDialogMode.value = 'edit'
  editClient(client)
  isClientDialogOpen.value = true
}

function openDeleteClientDialog(client) {
  deleteTarget.value = client
  deleteDialogOpen.value = true
}
```

- [ ] **Step 4: Replace inline forms with Dialog**

The client create/edit form must be inside:

```vue
<Dialog v-model:open="isClientDialogOpen">
  <DialogContent data-testid="client-form-dialog" class="sm:max-w-2xl">
    <DialogHeader>
      <DialogTitle>{{ clientDialogMode === 'create' ? i18nStore.t('frontend.clients.create') : i18nStore.t('frontend.clients.edit') }}</DialogTitle>
      <DialogDescription>Manage client access and contact details.</DialogDescription>
    </DialogHeader>
    <!-- existing form fields with shadcn Input controls -->
    <DialogFooter>
      <Button variant="outline" @click="isClientDialogOpen = false">{{ i18nStore.t('frontend.common.cancel') }}</Button>
      <Button @click="submitForm">{{ clientDialogMode === 'create' ? i18nStore.t('frontend.common.create') : i18nStore.t('frontend.common.save') }}</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

If a listed i18n key is missing, use the closest existing frontend key in the catalog instead of hardcoding a translated sentence.

- [ ] **Step 5: Add selectable rows and visible actions**

Use `@click.stop` on row action buttons:

```vue
<Button :data-testid="`client-edit-${client.id}`" size="sm" variant="outline" @click.stop="openEditClientDialog(client)">Edit</Button>
<Button size="sm" variant="outline" @click.stop="toggleClientStatus(client)">{{ client.is_active ? 'Deactivate' : 'Activate' }}</Button>
<Button size="sm" variant="destructive" @click.stop="openDeleteClientDialog(client)">Delete</Button>
```

- [ ] **Step 6: Run clients tests**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/TenantSectionViews.spec.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ClientManagementPanel.vue frontend/src/views/__tests__/TenantSectionViews.spec.js
git commit -m "feat: convert clients to command center workspace"
```

---

## Task 7: Catalog Workspace with Typed Delete Preview Preserved

**Files:**
- Modify: `frontend/src/components/CatalogPanel.vue`
- Modify: `frontend/src/components/__tests__/catalogDeletePreview.spec.js`
- Modify: `frontend/src/views/__tests__/TenantSectionViews.spec.js`

- [ ] **Step 1: Add failing catalog UI regression test**

In `TenantSectionViews.spec.js`, add a test that verifies service row actions and the typed delete preview dialog still render:

```js
it('keeps catalog service and plan actions visible with typed delete preview', async () => {
  api.get.mockResolvedValueOnce({
    data: [
      { id: 1, name: 'Netflix', description: 'Streaming', plans: [{ id: 2, name: 'Premium', duration_days: 30, price: 10 }] },
    ],
  })
  api.get.mockResolvedValueOnce({
    data: {
      target_type: 'service',
      target_name: 'Netflix',
      affected_plan_count: 1,
      active_subscription_count: 2,
      historical_subscription_count: 3,
      total_subscription_count: 5,
      active_subscriptions: [],
      pagination: { total_pages: 1, has_next: false },
    },
  })

  const wrapper = mountTenantRoute(TenantCatalogView, '/admin/catalog')
  await flushPromises()

  expect(wrapper.find('[data-testid="service-edit-1"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="service-delete-1"]').exists()).toBe(true)

  await wrapper.get('[data-testid="service-delete-1"]').trigger('click')
  await flushPromises()

  expect(wrapper.text()).toContain('Netflix')
  expect(wrapper.find('[data-testid="catalog-delete-confirm-input"]').exists()).toBe(true)
})
```

- [ ] **Step 2: Run catalog tests to verify failure**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/TenantSectionViews.spec.js src/components/__tests__/catalogDeletePreview.spec.js
```

Expected: FAIL for missing test IDs or new layout markers.

- [ ] **Step 3: Preserve delete preview logic exactly**

Do not change these existing functions except for import paths or button wiring:

- `closeDeleteModal`
- `deletePreviewTitle`
- `countText`
- `loadDeletePreview`
- `openDeleteService`
- `openDeletePlan`
- `confirmDelete`
- `isDeleteConfirmationValid`
- `formatPreviewRow`

Keep delete URLs:

```js
`/catalog/services/${target.serviceId}?confirm=true`
`/catalog/services/${selectedServiceId.value}/plans/${target.planId}?confirm=true`
```

- [ ] **Step 4: Convert service/plan create/edit to large Dialogs**

Use two dialog states if not already present:

```js
const serviceDialogOpen = ref(false)
const planDialogOpen = ref(false)
const serviceDialogMode = ref('create')
const planDialogMode = ref('create')
```

Service and plan forms must use `DialogContent class="sm:max-w-2xl"` and visible labels.

- [ ] **Step 5: Add visible row actions and delete test IDs**

Required service buttons:

```vue
<Button :data-testid="`service-edit-${service.id}`" size="sm" variant="outline" @click.stop="openEditService(service)">Edit</Button>
<Button :data-testid="`service-delete-${service.id}`" size="sm" variant="destructive" @click.stop="openDeleteService(service)">Delete</Button>
```

Required plan buttons:

```vue
<Button :data-testid="`plan-edit-${plan.id}`" size="sm" variant="outline" @click.stop="openEditPlan(plan)">Edit</Button>
<Button :data-testid="`plan-delete-${plan.id}`" size="sm" variant="destructive" @click.stop="openDeletePlan(plan)">Delete</Button>
```

Add to the existing delete confirmation input:

```vue
<Input data-testid="catalog-delete-confirm-input" v-model.trim="deleteConfirmText" type="text" :placeholder="i18nStore.t('frontend.catalog.confirm_placeholder')" />
```

- [ ] **Step 6: Run catalog tests**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/TenantSectionViews.spec.js src/components/__tests__/catalogDeletePreview.spec.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/CatalogPanel.vue frontend/src/components/__tests__/catalogDeletePreview.spec.js frontend/src/views/__tests__/TenantSectionViews.spec.js
git commit -m "feat: convert catalog to command center workspace"
```

---

## Task 8: Subscriptions Workspace Regression-Safe Migration

**Files:**
- Modify: `frontend/src/views/SubscriptionsView.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionTable.vue`
- Modify: `frontend/src/components/subscriptions/SubscriptionFilters.vue`
- Modify: `frontend/src/components/subscriptions/ReminderSettingsModal.vue`
- Modify: `frontend/src/views/__tests__/SubscriptionsView.spec.js`

- [ ] **Step 1: Add failing subscription regression tests**

In `SubscriptionsView.spec.js`, add tests for route-query hydration, inspector selection, visible actions, and reminder settings modal:

```js
it('hydrates filters from route query and keeps the client filter after interaction', async () => {
  const wrapper = mountSubscriptionsView('/admin/subscriptions?client_id=7')
  await flushPromises()

  const clientFilter = wrapper.get('[data-testid="filter-client"]')
  expect(clientFilter.element.value).toBe('7')
})

it('selects a subscription row without breaking visible row actions', async () => {
  api.get.mockResolvedValueOnce({ data: { items: [{ id: 1, client_name: 'Client A', service_name: 'Netflix', status: 'active', streaming_email: 'a@example.com' }], total: 1 } })

  const wrapper = mountSubscriptionsView('/admin/subscriptions')
  await flushPromises()

  await wrapper.get('[data-testid="subscription-row-1"]').trigger('click')
  expect(wrapper.find('[data-testid="subscription-inspector"]').exists()).toBe(true)

  await wrapper.get('[data-testid="subscription-edit-1"]').trigger('click')
  expect(wrapper.find('[data-testid="subscription-form-dialog"]').exists()).toBe(true)
})

it('opens reminder settings modal with the isOpen prop contract', async () => {
  const wrapper = mountSubscriptionsView('/admin/subscriptions')
  await flushPromises()

  await wrapper.get('[data-testid="reminder-settings-open"]').trigger('click')
  expect(wrapper.text()).toContain('Reminder')
})
```

Use existing API mocks from the file. If endpoint shapes differ, adapt only mocked data fields; keep the assertions.

- [ ] **Step 2: Run subscription tests to verify failure**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/SubscriptionsView.spec.js
```

Expected: FAIL for missing inspector/action/dialog test IDs.

- [ ] **Step 3: Preserve `SubscriptionFilters` hydration contract**

`SubscriptionFilters.vue` must keep:

```js
const props = defineProps({
  initialFilters: { type: Object, default: () => ({}) },
})

watch(
  () => props.initialFilters,
  (value) => {
    filters.value = { ...filters.value, ...value }
  },
  { deep: true, immediate: true },
)
```

The client select must keep:

```vue
<select data-testid="filter-client" v-model="filters.client_id">
```

- [ ] **Step 4: Add subscription selection in `SubscriptionsView.vue`**

Add:

```js
const selectedSubscription = ref(null)

function selectSubscription(subscription) {
  selectedSubscription.value = subscription
}

function openEditFromInspector() {
  if (!selectedSubscription.value) return
  openEditModal(selectedSubscription.value)
}
```

Pass handlers to `SubscriptionTable`:

```vue
<SubscriptionTable
  :subscriptions="subscriptions"
  :selected-id="selectedSubscription?.id"
  @select="selectSubscription"
  @edit="openEditModal"
  @renew="openRenewModal"
  @cancel="openCancelModal"
  @reactivate="openReactivateModal"
/>
```

Render inspector:

```vue
<EntityInspector
  v-if="selectedSubscription"
  data-testid="subscription-inspector"
  title="Subscription detail"
  :description="selectedSubscription.streaming_email"
  :fields="[
    { label: 'Client', value: selectedSubscription.client_name },
    { label: 'Service', value: selectedSubscription.service_name },
    { label: 'Status', value: selectedSubscription.status },
  ]"
  @edit="openEditFromInspector"
/>
```

- [ ] **Step 5: Update `SubscriptionTable.vue` row behavior**

Add props and emits:

```js
const props = defineProps({
  subscriptions: { type: Array, default: () => [] },
  selectedId: { type: [Number, String, null], default: null },
})

const emit = defineEmits(['select', 'edit', 'renew', 'cancel', 'reactivate'])
```

Rows must include:

```vue
<TableRow
  v-for="subscription in subscriptions"
  :key="subscription.id"
  :data-testid="`subscription-row-${subscription.id}`"
  :class="selectedId === subscription.id ? 'bg-surface-selected border-border-strong' : 'hover:bg-surface-hover'"
  @click="emit('select', subscription)"
>
```

Edit button must include:

```vue
<Button :data-testid="`subscription-edit-${subscription.id}`" size="sm" variant="outline" @click.stop="emit('edit', subscription)">Edit</Button>
```

Keep the existing credential reveal button/API behavior unchanged.

- [ ] **Step 6: Keep reminder settings `isOpen` contract**

`ReminderSettingsModal.vue` must continue to accept:

```js
const props = defineProps({
  isOpen: { type: Boolean, default: false },
})
```

`SubscriptionsView.vue` must continue to render:

```vue
<ReminderSettingsModal :is-open="isReminderSettingsOpen" @close="isReminderSettingsOpen = false" />
```

The open button must include:

```vue
<Button data-testid="reminder-settings-open" variant="outline" @click="isReminderSettingsOpen = true">
```

- [ ] **Step 7: Run subscription tests**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/SubscriptionsView.spec.js
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/SubscriptionsView.vue frontend/src/components/subscriptions/SubscriptionTable.vue frontend/src/components/subscriptions/SubscriptionFilters.vue frontend/src/components/subscriptions/ReminderSettingsModal.vue frontend/src/views/__tests__/SubscriptionsView.spec.js
git commit -m "feat: convert subscriptions to command center workspace"
```

---

## Task 9: Mailbox, Code Services, and Client Portal Dark-Only Migration

**Files:**
- Modify: `frontend/src/views/TenantMailboxView.vue`
- Modify: `frontend/src/components/MailboxConfigPanel.vue`
- Modify: `frontend/src/components/CodeServicesGlobalPanel.vue`
- Modify: `frontend/src/components/CodeServicesTenantPanel.vue`
- Modify: `frontend/src/views/ClientDashboardView.vue`
- Modify: `frontend/src/views/__tests__/TenantMailboxView.spec.js`
- Modify: `frontend/src/views/__tests__/RoleDashboards.spec.js`
- Modify: `frontend/src/views/__tests__/TenantSectionViews.spec.js`

- [ ] **Step 1: Add mailbox regression tests**

In `TenantMailboxView.spec.js`, keep or add:

```js
it('treats mailbox 404 as an empty configuration state', async () => {
  api.get.mockRejectedValueOnce({ response: { status: 404, data: { detail: 'Not found' } } })

  const wrapper = mountTenantMailboxView('/admin/mailbox')
  await flushPromises()

  expect(wrapper.text()).not.toContain('Not found')
  expect(wrapper.find('[data-testid="mailbox-empty-state"]').exists()).toBe(true)
})

it('shows OAuth success feedback from query params', async () => {
  api.get.mockResolvedValueOnce({ data: null })

  const wrapper = mountTenantMailboxView('/admin/mailbox?mailbox_oauth=success')
  await flushPromises()

  expect(wrapper.text()).toContain('OAuth')
})
```

Use the existing mount helper name from the file.

- [ ] **Step 2: Run mailbox tests to verify current behavior is protected**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/TenantMailboxView.spec.js
```

Expected: PASS before style changes or FAIL only for missing new test ID. If it fails for 404 behavior, fix the behavior before continuing.

- [ ] **Step 3: Re-skin mailbox without changing API functions**

In `MailboxConfigPanel.vue` preserve functions for:

- save
- test
- connect OAuth
- disconnect
- status display

Add `data-testid="mailbox-empty-state"` to the empty/unconfigured state. Use shadcn `Button`, `Input`, `InlineAlert`, `StatusBadge`, and dark-only surfaces.

- [ ] **Step 4: Re-skin code-service panels**

For `CodeServicesGlobalPanel.vue` and `CodeServicesTenantPanel.vue`:

- Keep existing fetch/save/toggle logic.
- Use summary-first header where metrics are available.
- Use dark table/list surfaces.
- Use visible shadcn `Switch` or `Button` controls.
- Preserve loading/error/success messages.

- [ ] **Step 5: Re-skin client portal**

In `ClientDashboardView.vue`:

- Remove dependency on legacy light CSS files if present.
- Use dark-only surfaces.
- Keep password change logic.
- Keep subscription display.
- Use `StatusBadge` for statuses.

- [ ] **Step 6: Run affected tests**

Run:

```bash
cd frontend && npm test -- src/views/__tests__/TenantMailboxView.spec.js src/views/__tests__/RoleDashboards.spec.js src/views/__tests__/TenantSectionViews.spec.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/TenantMailboxView.vue frontend/src/components/MailboxConfigPanel.vue frontend/src/components/CodeServicesGlobalPanel.vue frontend/src/components/CodeServicesTenantPanel.vue frontend/src/views/ClientDashboardView.vue frontend/src/views/__tests__/TenantMailboxView.spec.js frontend/src/views/__tests__/RoleDashboards.spec.js frontend/src/views/__tests__/TenantSectionViews.spec.js
git commit -m "feat: migrate remaining surfaces to dark command center"
```

---

## Task 10: Mobile Functional Pass

**Files:**
- Modify: `frontend/src/components/DashboardLayout.vue`
- Modify: `frontend/src/components/EntityInspector.vue`
- Modify: affected workspace components from Tasks 5-9 if mobile actions are hidden
- Modify: relevant test files for mobile assertions

- [ ] **Step 1: Add mobile behavior tests**

Add tests to affected files that assert mobile controls exist. Example for DashboardLayout:

```js
it('renders mobile navigation drawer controls', async () => {
  const { wrapper } = renderWithApp(DashboardLayout, {
    auth: { user: { role: 'tenant', username: 'tenant' }, token: 'token' },
    route: '/admin/overview',
  })

  await wrapper.vm.$nextTick()

  expect(wrapper.find('[data-testid="mobile-nav-trigger"]').exists()).toBe(true)
})
```

Add `data-testid="mobile-nav-trigger"` to the mobile nav button.

- [ ] **Step 2: Run mobile-related tests to verify failure**

Run:

```bash
cd frontend && npm test -- src/components/__tests__/DashboardLayout.spec.js src/views/__tests__/TenantSectionViews.spec.js src/views/__tests__/SubscriptionsView.spec.js
```

Expected: FAIL for missing mobile nav trigger test ID or mobile layout markers.

- [ ] **Step 3: Ensure responsive layout rules**

Apply these patterns:

- Summary metrics: `grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4`
- Main workspace: `grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]`
- Tables: wrap in `overflow-x-auto`; if columns remain too dense, render compact card list below `md:hidden` and table as `hidden md:block`.
- Inspector: `xl:block`; for mobile, render the same details in a `Sheet` opened by selection.
- Row actions: allow wrapping with `flex flex-wrap gap-2`.

- [ ] **Step 4: Run mobile tests**

Run:

```bash
cd frontend && npm test -- src/components/__tests__/DashboardLayout.spec.js src/views/__tests__/TenantSectionViews.spec.js src/views/__tests__/SubscriptionsView.spec.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DashboardLayout.vue frontend/src/components/EntityInspector.vue frontend/src/views frontend/src/components
git commit -m "feat: complete mobile command center interactions"
```

---

## Task 11: Documentation Refresh and Final Verification

**Files:**
- Modify: `docs/architecture/frontend-architecture.md`
- Modify: `docs/codebase/frontend-structure.md`
- Modify: `docs/code-standard/frontend-conventions.md`
- Modify: `docs/SUMMARY.md` if frontend descriptions reference removed theme behavior

- [ ] **Step 1: Update frontend architecture documentation**

In `docs/architecture/frontend-architecture.md`:

- Replace light/dark theme language with dark-only command-center language.
- Remove `ThemeToggle` from shared components.
- Add `SummaryMetric`, `EntityInspector`, and `ImpactConfirmDialog`.
- Document that `darkTheme.js` forces dark mode during bootstrap.
- Document summary-first workspace pages.
- Document inspectors and dialog-only entity editing.

- [ ] **Step 2: Update frontend structure documentation**

In `docs/codebase/frontend-structure.md`:

- Add `src/lib/darkTheme.js`.
- Remove `ThemeToggle.vue` and `useTheme.js`.
- Add new shared components.
- Remove legacy light CSS references if removed from code.

- [ ] **Step 3: Update frontend conventions**

In `docs/code-standard/frontend-conventions.md`:

- State that Trackpal is dark-only.
- State that shadcn `Button` is required for buttons.
- State that create/edit uses `Dialog`.
- State that data pages use summary-first layout.
- State that selected rows use gray, not cyan.
- State that cyan is reserved for nav/focus/inspector.
- State that user-facing strings still use i18n.

- [ ] **Step 4: Scan for rejected design leftovers**

Run:

```bash
rg -n "light mode|light/dark|ThemeToggle|useTheme|bg-white|bg-stone|indigo|glassmorphism|gradient" frontend/src docs/architecture/frontend-architecture.md docs/codebase/frontend-structure.md docs/code-standard/frontend-conventions.md
```

Expected:

- No `ThemeToggle` or `useTheme` references.
- No `bg-white` or `bg-stone` in `frontend/src`.
- Any `gradient` or `glassmorphism` matches only appear in design bans, not implementation guidance.
- Any `indigo` matches are unrelated assets or must be replaced with primary/cyan styling.

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd frontend && npm test
```

Expected: PASS.

- [ ] **Step 6: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit docs and final cleanup**

```bash
git add docs/architecture/frontend-architecture.md docs/codebase/frontend-structure.md docs/code-standard/frontend-conventions.md docs/SUMMARY.md
git commit -m "docs: update frontend docs for dark command center"
```

---

## Self-Review Checklist

- Spec coverage: Tasks 1-4 cover dark-only foundation, shell, and login. Tasks 5-9 cover primary workspaces and preservation of high-risk workflows. Task 10 covers mobile. Task 11 covers documentation and final verification.
- Placeholder scan: This plan contains no unresolved marker text and no blank implementation steps.
- Type consistency: New shared components use JavaScript props and Vue events. Event names used in tasks match emitted names.
- Regression coverage: Subscription filter hydration, reminder modal `isOpen`, mailbox 404/OAuth behavior, support mode, and service/plan typed delete preview are explicitly tested.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-10-dark-command-center-frontend.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.
