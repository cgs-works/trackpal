# Plan de Implementación: Rediseño del Frontend (Trackpal 2026)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rediseñar por completo el frontend de Trackpal para adoptar una interfaz de Consola Premium estilo Linear, integrando Tailwind CSS v4, implementando un sistema de temas (Light/Dark) persistente en LocalStorage, y modularizando las pantallas clave (como `SubscriptionsView.vue`) para cumplir con el límite de < 501 líneas de código de `AGENTS.md`.

**Architecture:** Compartiremos la estructura de navegación y estado de configuración mediante un layout maestro modular (`DashboardLayout.vue`). Las vistas específicas se encapsularán como slots dentro de este layout, dividiendo componentes masivos en partes de responsabilidad única.

**Tech Stack:** Vue 3, Vite, Pinia, vue-router, Tailwind CSS v4, Vitest

---

### Task 1: Instalar y Configurar Tailwind CSS v4

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.js`
- Modify: `frontend/src/style.css`

- [ ] **Step 1: Instalar dependencias de Tailwind CSS v4**

Ejecuta en la carpeta `frontend/`:
```bash
cd frontend && npm install tailwindcss @tailwindcss/vite
```

- [ ] **Step 2: Configurar Vite para integrar el plugin de Tailwind CSS v4**

Modifica `frontend/vite.config.js` para añadir el plugin oficial:
```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss()
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
  }
})
```

- [ ] **Step 3: Inyectar directiva de Tailwind CSS v4 en style.css**

Reemplaza los contenidos de `frontend/src/style.css` con el import de Tailwind v4 y variables base:
```css
@import "tailwindcss";

@layer base {
  html, body {
    @apply min-h-screen bg-stone-50 text-stone-900 transition-colors duration-200 antialiased;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  }

  html.dark, html.dark body {
    @apply bg-zinc-950 text-zinc-100;
  }
}
```

- [ ] **Step 4: Verificar que la compilación funciona correctamente**

Ejecuta en la carpeta `frontend/`:
```bash
npm run build
```
Expected: Compilación exitosa sin errores de sintaxis CSS ni advertencias de Vite.

- [ ] **Step 5: Confirmar cambios**

```bash
git add frontend/package.json frontend/vite.config.js frontend/src/style.css
git commit -m "feat: install and configure tailwind css v4 with vite plugin"
```

---

### Task 2: Implementar Sistema de Temas y Componente ThemeToggle

**Files:**
- Create: `frontend/src/composables/useTheme.js`
- Create: `frontend/src/components/ThemeToggle.vue`
- Create: `frontend/src/composables/__tests__/theme.spec.js`

- [ ] **Step 1: Escribir tests de unidad para el composable de gestión de tema**

Crea `frontend/src/composables/__tests__/theme.spec.js`:
```javascript
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useTheme } from '../useTheme'

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('debe inicializar el tema por defecto', () => {
    const { theme } = useTheme()
    expect(theme.value).toBe('light')
  })

  it('debe cambiar de tema correctamente', () => {
    const { theme, toggleTheme } = useTheme()
    toggleTheme()
    expect(theme.value).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
```

- [ ] **Step 2: Verificar que el test falla**

Ejecuta:
```bash
cd frontend && npm test -- src/composables/__tests__/theme.spec.js
```
Expected: FAIL porque `useTheme` no está definido.

- [ ] **Step 3: Implementar useTheme.js**

Crea `frontend/src/composables/useTheme.js`:
```javascript
import { ref, watch } from 'vue'

const theme = ref('light')

export function useTheme() {
  function initTheme() {
    const savedTheme = localStorage.getItem('theme')
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches

    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
      theme.value = 'dark'
      document.documentElement.classList.add('dark')
      document.documentElement.style.colorScheme = 'dark'
    } else {
      theme.value = 'light'
      document.documentElement.classList.remove('dark')
      document.documentElement.style.colorScheme = 'light'
    }
  }

  function toggleTheme() {
    if (theme.value === 'dark') {
      theme.value = 'light'
      localStorage.setItem('theme', 'light')
      document.documentElement.classList.remove('dark')
      document.documentElement.style.colorScheme = 'light'
    } else {
      theme.value = 'dark'
      localStorage.setItem('theme', 'dark')
      document.documentElement.classList.add('dark')
      document.documentElement.style.colorScheme = 'dark'
    }
  }

  // Inicialización única
  initTheme()

  return {
    theme,
    toggleTheme
  }
}
```

- [ ] **Step 4: Verificar que el test ahora pasa**

Ejecuta:
```bash
npm test -- src/composables/__tests__/theme.spec.js
```
Expected: PASS.

- [ ] **Step 5: Crear componente ThemeToggle.vue**

Crea `frontend/src/components/ThemeToggle.vue`:
```vue
<script setup>
import { useTheme } from '../composables/useTheme'

const { theme, toggleTheme } = useTheme()
</script>

<template>
  <button
    @click="toggleTheme"
    type="button"
    class="p-2 rounded-md hover:bg-stone-100 dark:hover:bg-zinc-800 text-stone-500 dark:text-zinc-400 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
    :title="theme === 'dark' ? 'Cambiar a Modo Claro' : 'Cambiar a Modo Oscuro'"
    aria-label="Toggle Theme"
  >
    <!-- Sun Icon (visible in dark theme) -->
    <svg v-if="theme === 'dark'" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 text-amber-400">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m0 13.5V21M4.22 4.22l1.625 1.625M16.125 16.125l1.625 1.625M3 12h2.25m13.5 0H21M4.22 19.78l1.625-1.625M16.125 7.875l1.625-1.625M12 7.5a4.5 4.5 0 100 9 4.5 4.5 0 000-9z" />
    </svg>
    <!-- Moon Icon (visible in light theme) -->
    <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 text-stone-500">
      <path stroke-linecap="round" stroke-linejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
    </svg>
  </button>
</template>
```

- [ ] **Step 6: Confirmar cambios**

```bash
git add frontend/src/composables/useTheme.js frontend/src/components/ThemeToggle.vue frontend/src/composables/__tests__/theme.spec.js
git commit -m "feat: implement theme toggle and core theme manager composable"
```

---

### Task 3: Rediseñar LoginView.vue con Estilo Linear

**Files:**
- Modify: `frontend/src/views/LoginView.vue`

- [ ] **Step 1: Escribir LoginView con Tailwind CSS v4**

Modifica `frontend/src/views/LoginView.vue` integrando clases utilitarias de Tailwind, la transición de error, y agregando `ThemeToggle` en el footer:
```vue
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'
import { usePublicI18n } from '../i18n/usePublicI18n'
import ThemeToggle from '../components/ThemeToggle.vue'

const router = useRouter()
const authStore = useAuthStore()
const i18nStore = useI18nStore()
const { locale, setLocale, t } = usePublicI18n()

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const isLoading = ref(false)

async function handleSubmit() {
  errorMessage.value = ''
  isLoading.value = true

  try {
    const data = await authStore.login(username.value, password.value)
    await i18nStore.loadCatalog()

    const role = data.user?.role

    if (role === 'master') {
      await router.push('/master/dashboard')
    } else if (role === 'tenant') {
      await router.push('/admin/dashboard')
    } else if (role === 'client') {
      await router.push('/client/dashboard')
    } else {
      errorMessage.value = t('login.unknown_role')
    }
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || t('login.error')
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <main class="min-h-screen flex flex-col items-center justify-center p-6 bg-stone-50 dark:bg-zinc-950 transition-colors duration-200 relative select-none">
    
    <div class="w-full max-w-[360px] bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md p-8 shadow-sm transition-all">
      <div class="mb-6 text-center">
        <span class="text-xs font-semibold tracking-wider text-indigo-500 uppercase">Trackpal</span>
        <h1 class="text-xl font-bold tracking-tight text-stone-900 dark:text-zinc-100 mt-1">
          {{ t('login.title') }}
        </h1>
      </div>

      <form class="flex flex-col gap-4" @submit.prevent="handleSubmit">
        <div class="flex flex-col gap-1.5">
          <label for="username" class="text-xs font-medium text-stone-500 dark:text-zinc-400">
            {{ t('login.username') }}
          </label>
          <input
            id="username"
            v-model="username"
            type="text"
            autocomplete="username"
            required
            :disabled="isLoading"
            class="px-3 py-2 text-sm bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 placeholder-stone-400 focus:outline-none focus:border-indigo-500 dark:focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:bg-stone-50 dark:disabled:bg-zinc-900 disabled:text-stone-400 dark:disabled:text-zinc-500 transition-all duration-150"
          >
        </div>

        <div class="flex flex-col gap-1.5">
          <label for="password" class="text-xs font-medium text-stone-500 dark:text-zinc-400">
            {{ t('login.password') }}
          </label>
          <input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            :disabled="isLoading"
            class="px-3 py-2 text-sm bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 placeholder-stone-400 focus:outline-none focus:border-indigo-500 dark:focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:bg-stone-50 dark:disabled:bg-zinc-900 disabled:text-stone-400 dark:disabled:text-zinc-500 transition-all duration-150"
          >
        </div>

        <Transition name="fade">
          <div v-if="errorMessage" class="text-xs font-medium text-red-500 bg-red-50 dark:bg-red-950/20 border border-red-200/30 dark:border-red-950/40 rounded px-3 py-2" role="alert">
            {{ errorMessage }}
          </div>
        </Transition>

        <button
          type="submit"
          :disabled="isLoading"
          class="mt-2 w-full px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium text-sm rounded-md shadow-sm transition-all duration-150 flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed"
        >
          <span v-if="isLoading" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
          {{ isLoading ? t('login.signing_in') : t('login.sign_in') }}
        </button>
      </form>
    </div>

    <div class="absolute bottom-6 flex items-center gap-4">
      <div class="flex items-center gap-2">
        <select
          id="locale-select"
          v-model="locale"
          @change="setLocale(locale)"
          class="text-xs text-stone-500 dark:text-zinc-400 bg-transparent border border-stone-200 dark:border-zinc-800 rounded px-2 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer"
          aria-label="Language Selector"
        >
          <option value="en">English</option>
          <option value="es">Español</option>
        </select>
      </div>
      <div class="h-4 w-[1px] bg-stone-200 dark:bg-zinc-800"></div>
      <ThemeToggle />
    </div>

  </main>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
```

- [ ] **Step 2: Verificar la suite de pruebas del frontend**

Ejecuta:
```bash
npm test
```
Expected: PASS para todas las pruebas de login preexistentes.

- [ ] **Step 3: Confirmar cambios**

```bash
git add frontend/src/views/LoginView.vue
git commit -m "feat: redesign LoginView with clean Linear style and Tailwind CSS v4"
```

---

### Task 4: Implementar DashboardLayout.vue

**Files:**
- Create: `frontend/src/components/DashboardLayout.vue`

- [ ] **Step 1: Crear componente maestro de layout compartido**

Crea `frontend/src/components/DashboardLayout.vue` con el Sidebar de navegación adaptado a móvil/escritorio, perfil de usuario, selectores de idioma y el `ThemeToggle` centralizados:
```vue
<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'
import ThemeToggle from './ThemeToggle.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const i18nStore = useI18nStore()

const isSidebarOpen = ref(false)

const userInitial = computed(() => {
  return authStore.username ? authStore.username.charAt(0).toUpperCase() : 'U'
})

const menuItems = computed(() => {
  const role = authStore.role
  if (role === 'master') {
    return [
      { name: i18nStore.t('frontend.master.title') || 'Master Dashboard', path: '/master/dashboard', icon: 'M' }
    ]
  } else if (role === 'tenant') {
    return [
      { name: i18nStore.t('frontend.tenant.title') || 'Dashboard', path: '/admin/dashboard', icon: 'D' },
      { name: i18nStore.t('frontend.subscriptions.title') || 'Subscriptions', path: '/admin/subscriptions', icon: 'S' }
    ]
  } else if (role === 'client') {
    return [
      { name: i18nStore.t('frontend.client.title') || 'Client Portal', path: '/client/dashboard', icon: 'C' }
    ]
  }
  return []
})

async function handleLogout() {
  authStore.logout()
  await router.push('/login')
}

function setLocale(lang) {
  i18nStore.locale = lang
  localStorage.setItem('locale', lang)
}
</script>

<template>
  <div class="min-h-screen bg-stone-50 dark:bg-zinc-950 text-stone-900 dark:text-zinc-100 flex transition-colors duration-200">
    
    <!-- Mobile Sidebar Backdrop -->
    <div
      v-if="isSidebarOpen"
      @click="isSidebarOpen = false"
      class="fixed inset-0 bg-black/40 z-40 md:hidden backdrop-blur-sm"
    ></div>

    <!-- Sidebar -->
    <aside
      :class="[
        isSidebarOpen ? 'translate-x-0' : '-translate-x-full',
        'fixed md:sticky top-0 left-0 h-screen w-64 bg-white dark:bg-zinc-900 border-r border-stone-200 dark:border-zinc-800 flex flex-col z-50 transition-transform duration-200 md:translate-x-0 flex-shrink-0'
      ]"
    >
      <!-- Sidebar Header -->
      <div class="h-14 border-b border-stone-200 dark:border-zinc-800 flex items-center px-6 justify-between flex-shrink-0">
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 bg-indigo-600 rounded-md flex items-center justify-center text-white font-bold text-xs shadow-sm">T</div>
          <span class="font-bold tracking-tight text-stone-900 dark:text-zinc-100">Trackpal</span>
        </div>
        <button @click="isSidebarOpen = false" class="md:hidden text-stone-500 hover:text-stone-700 dark:text-zinc-400 dark:hover:text-zinc-200">
          ✕
        </button>
      </div>

      <!-- Navigation Menu -->
      <nav class="flex-1 p-4 flex flex-col gap-1 overflow-y-auto">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          :class="[
            route.path === item.path
              ? 'bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 dark:text-indigo-400 border border-indigo-200/30 dark:border-indigo-950/40'
              : 'hover:bg-stone-50 dark:hover:bg-zinc-800/50 text-stone-600 dark:text-zinc-300 border border-transparent',
            'flex items-center gap-3 px-3 py-2 rounded-md font-medium text-sm transition-colors'
          ]"
        >
          <span class="w-5 h-5 flex items-center justify-center bg-stone-100 dark:bg-zinc-800 rounded font-semibold text-xs">{{ item.icon }}</span>
          {{ item.name }}
        </router-link>
      </nav>

      <!-- Sidebar Footer -->
      <div class="p-4 border-t border-stone-200 dark:border-zinc-800 flex flex-col gap-3 flex-shrink-0">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <select
              :value="i18nStore.locale"
              @change="setLocale($event.target.value)"
              class="text-xs text-stone-500 dark:text-zinc-400 bg-transparent border border-stone-200 dark:border-zinc-800 rounded px-1.5 py-1 focus:outline-none cursor-pointer"
              aria-label="Language Selector"
            >
              <option value="en">EN</option>
              <option value="es">ES</option>
            </select>
          </div>
          <ThemeToggle />
        </div>

        <div class="flex items-center gap-3 bg-stone-50 dark:bg-zinc-950/50 border border-stone-200/50 dark:border-zinc-800/50 p-2.5 rounded-md">
          <div class="w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-950 flex items-center justify-center font-bold text-sm text-indigo-600 dark:text-indigo-400">
            {{ userInitial }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-xs font-semibold text-stone-800 dark:text-zinc-200 truncate">{{ authStore.username || 'User' }}</p>
            <p class="text-[10px] text-stone-400 dark:text-zinc-500 truncate capitalize">{{ authStore.role }}</p>
          </div>
          <button @click="handleLogout" class="text-stone-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400 transition-colors" title="Log out">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75" />
            </svg>
          </button>
        </div>
      </div>
    </aside>

    <!-- Main Content wrapper -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Mobile header -->
      <header class="h-14 bg-white dark:bg-zinc-900 border-b border-stone-200 dark:border-zinc-800 px-4 flex items-center justify-between md:hidden flex-shrink-0">
        <button @click="isSidebarOpen = true" class="p-1 text-stone-500 dark:text-zinc-400">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>
        <span class="font-bold tracking-tight">Trackpal</span>
        <div class="w-6"></div>
      </header>

      <!-- Slot viewport -->
      <main class="flex-1 p-6 overflow-y-auto">
        <slot />
      </main>
    </div>

  </div>
</template>
```

- [ ] **Step 2: Confirmar cambios**

```bash
git add frontend/src/components/DashboardLayout.vue
git commit -m "feat: create centralized DashboardLayout component with adaptive Sidebar"
```

---

### Task 5: Refactorizar y Dividir SubscriptionsView.vue

**Files:**
- Create: `frontend/src/components/subscriptions/SubscriptionTable.vue`
- Create: `frontend/src/components/subscriptions/SubscriptionModal.vue`
- Modify: `frontend/src/views/SubscriptionsView.vue`

- [ ] **Step 1: Extraer la tabla de suscripciones**

Crea `frontend/src/components/subscriptions/SubscriptionTable.vue` con soporte completo de Tailwind v4 y modo oscuro, abstrayendo el renderizado y revelado de claves:
```vue
<script setup>
import { ref } from 'vue'
import api from '../../services/api'

const props = defineProps({
  subscriptions: { type: Array, required: true },
  t: { type: Function, required: true }
})

const emit = defineEmits(['edit', 'delete'])

const revealedRowId = ref(null)
const revealedCredentials = ref({})

async function revealCredentials(subId) {
  if (revealedRowId.value === subId) {
    revealedRowId.value = null
    return
  }

  try {
    const res = await api.get(`/api/v1/admin/subscriptions/${subId}/credentials`)
    revealedCredentials.value[subId] = res.data
    revealedRowId.value = subId
  } catch (error) {
    console.error('Failed to reveal credentials', error)
  }
}
</script>

<template>
  <div class="overflow-x-auto border border-stone-200 dark:border-zinc-800 rounded-md bg-white dark:bg-zinc-900 shadow-sm">
    <table class="w-full text-left text-sm border-collapse">
      <thead>
        <tr class="bg-stone-50 dark:bg-zinc-900/50 border-b border-stone-200 dark:border-zinc-800 text-stone-500 dark:text-zinc-400 font-medium">
          <th class="p-3">ID</th>
          <th class="p-3">{{ t('frontend.subscriptions.client') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.plan') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.streaming_credentials') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.status') }}</th>
          <th class="p-3 text-right">{{ t('frontend.subscriptions.actions') }}</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-stone-100 dark:divide-zinc-800/40">
        <tr v-for="sub in subscriptions" :key="sub.id" class="hover:bg-stone-50/50 dark:hover:bg-zinc-800/20 text-stone-800 dark:text-zinc-200 transition-colors">
          <td class="p-3 font-mono text-xs">{{ sub.id }}</td>
          <td class="p-3">
            <div class="font-medium text-stone-900 dark:text-zinc-100">{{ sub.client_name }}</div>
            <div class="text-xs text-stone-400 dark:text-zinc-500 font-mono">{{ sub.client_phone }}</div>
          </td>
          <td class="p-3">
            <span class="px-2 py-0.5 text-xs font-semibold rounded bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 border border-indigo-200/30 dark:border-indigo-950/40">
              {{ sub.plan_name }}
            </span>
          </td>
          <td class="p-3">
            <div v-if="sub.has_password" class="flex items-center gap-1.5">
              <span class="font-mono text-xs bg-stone-50 dark:bg-zinc-950 px-2 py-1 rounded border border-stone-200/50 dark:border-zinc-800/50">
                <template v-if="revealedRowId === sub.id">
                  {{ revealedCredentials[sub.id]?.streaming_password || '***' }}
                </template>
                <template v-else>******</template>
              </span>
              <button
                @click="revealCredentials(sub.id)"
                class="p-1 rounded hover:bg-stone-100 dark:hover:bg-zinc-800 text-stone-400 dark:text-zinc-500 transition-colors cursor-pointer"
                :title="revealedRowId === sub.id ? t('frontend.subscriptions.hide') : t('frontend.subscriptions.reveal')"
              >
                👁️
              </button>
            </div>
            <span v-else class="text-xs text-stone-400 dark:text-zinc-600">—</span>
          </td>
          <td class="p-3">
            <span :class="[
              sub.status === 'active' ? 'bg-green-50 dark:bg-green-950/30 text-green-600 dark:text-green-400 border-green-200/30 dark:border-green-950/40' : 'bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 border-red-200/30 dark:border-red-950/40',
              'px-2 py-0.5 text-xs font-semibold rounded border uppercase tracking-wider'
            ]">
              {{ sub.status }}
            </span>
          </td>
          <td class="p-3 text-right">
            <div class="flex items-center justify-end gap-1">
              <button @click="emit('edit', sub)" class="p-1.5 rounded hover:bg-stone-100 dark:hover:bg-zinc-800 text-stone-500 dark:text-zinc-400 transition-colors cursor-pointer" title="Edit">
                ✏️
              </button>
              <button @click="emit('delete', sub.id)" class="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-950/30 text-red-500 dark:text-red-400 transition-colors cursor-pointer" title="Delete">
                🗑️
              </button>
            </div>
          </td>
        </tr>
        <tr v-if="subscriptions.length === 0">
          <td colspan="6" class="p-8 text-center text-stone-400 dark:text-zinc-600 font-medium">
            No subscriptions found.
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
```

- [ ] **Step 2: Extraer el formulario modal de suscripciones**

Crea `frontend/src/components/subscriptions/SubscriptionModal.vue` para encapsular toda la lógica de creación/edición, simplificando drásticamente el componente de vista principal:
```vue
<script setup>
import { ref, watch } from 'vue'
import api from '../../services/api'

const props = defineProps({
  isOpen: { type: Boolean, required: true },
  sub: { type: Object, default: null },
  t: { type: Function, required: true }
})

const emit = defineEmits(['close', 'save'])

const clients = ref([])
const plans = ref([])
const formData = ref({
  client_id: '',
  plan_id: '',
  status: 'active',
  profile_name: '',
  profile_pin: '',
  streaming_password: '',
  expiration_override: ''
})

watch(() => props.isOpen, async (open) => {
  if (open) {
    try {
      const [clientsRes, plansRes] = await Promise.all([
        api.get('/api/v1/admin/clients'),
        api.get('/api/v1/admin/plans')
      ])
      clients.value = clientsRes.data
      plans.value = plansRes.data
    } catch (err) {
      console.error('Failed to load modal options', err)
    }

    if (props.sub) {
      formData.value = { ...props.sub }
    } else {
      formData.value = {
        client_id: '',
        plan_id: '',
        status: 'active',
        profile_name: '',
        profile_pin: '',
        streaming_password: '',
        expiration_override: ''
      }
    }
  }
})

async function handleSave() {
  try {
    if (props.sub) {
      await api.put(`/api/v1/admin/subscriptions/${props.sub.id}`, formData.value)
    } else {
      await api.post('/api/v1/admin/subscriptions', formData.value)
    }
    emit('save')
  } catch (err) {
    console.error('Failed to save subscription', err)
  }
}
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
    <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md w-full max-w-lg p-6 shadow-md transition-all">
      <div class="flex items-center justify-between border-b border-stone-100 dark:border-zinc-800/60 pb-3 mb-4">
        <h3 class="text-base font-bold text-stone-900 dark:text-zinc-100">
          {{ props.sub ? t('frontend.subscriptions.edit_title') : t('frontend.subscriptions.new_title') }}
        </h3>
        <button @click="emit('close')" class="text-stone-400 hover:text-stone-600 dark:text-zinc-500 dark:hover:text-zinc-300">✕</button>
      </div>

      <form @submit.prevent="handleSave" class="flex flex-col gap-4">
        <div class="grid grid-cols-2 gap-4">
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.client') }}</label>
            <select v-model="formData.client_id" required class="px-3 py-2 text-sm bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md">
              <option value="" disabled>Select Client</option>
              <option v-for="c in clients" :key="c.id" :value="c.id">{{ c.name }} ({{ c.phone }})</option>
            </select>
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.plan') }}</label>
            <select v-model="formData.plan_id" required class="px-3 py-2 text-sm bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md">
              <option value="" disabled>Select Plan</option>
              <option v-for="p in plans" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium text-stone-500 dark:text-zinc-400">Password</label>
            <input v-model="formData.streaming_password" type="text" class="px-3 py-2 text-sm bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md">
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium text-stone-500 dark:text-zinc-400">Status</label>
            <select v-model="formData.status" required class="px-3 py-2 text-sm bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md">
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
            </select>
          </div>
        </div>

        <div class="flex justify-end gap-2 border-t border-stone-100 dark:border-zinc-800/60 pt-4 mt-2">
          <button @click="emit('close')" type="button" class="px-4 py-2 text-sm text-stone-500 dark:text-zinc-400 hover:bg-stone-50 dark:hover:bg-zinc-800/50 rounded-md transition-colors cursor-pointer">Cancel</button>
          <button type="submit" class="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-medium rounded-md transition-colors cursor-pointer">Save</button>
        </div>
      </form>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Reescribir SubscriptionsView.vue usando componentes y DashboardLayout**

Modifica `frontend/src/views/SubscriptionsView.vue` para conectarlo con el layout centralizado y la nueva abstracción modular. Esto reduce su tamaño de 1244 LoC a **menos de 150 líneas**:
```vue
<script setup>
import { onMounted, ref } from 'vue'
import { useI18nStore } from '../stores/i18n'
import api from '../services/api'
import DashboardLayout from '../components/DashboardLayout.vue'
import SubscriptionTable from '../components/subscriptions/SubscriptionTable.vue'
import SubscriptionModal from '../components/subscriptions/SubscriptionModal.vue'

const i18nStore = useI18nStore()
const subscriptions = ref([])
const isModalOpen = ref(false)
const selectedSub = ref(null)

async function fetchSubscriptions() {
  try {
    const res = await api.get('/api/v1/admin/subscriptions')
    subscriptions.value = res.data
  } catch (err) {
    console.error('Failed to fetch subscriptions', err)
  }
}

function openNewModal() {
  selectedSub.value = null
  isModalOpen.value = true
}

function openEditModal(sub) {
  selectedSub.value = sub
  isModalOpen.value = true
}

async function handleDelete(subId) {
  if (confirm(i18nStore.t('frontend.subscriptions.delete_confirm') || 'Are you sure you want to delete this subscription?')) {
    try {
      await api.delete(`/api/v1/admin/subscriptions/${subId}`)
      await fetchSubscriptions()
    } catch (err) {
      console.error('Failed to delete subscription', err)
    }
  }
}

function handleSave() {
  isModalOpen.value = false
  fetchSubscriptions()
}

onMounted(() => {
  fetchSubscriptions()
})
</script>

<template>
  <DashboardLayout>
    <div class="flex items-center justify-between mb-6">
      <div>
        <span class="text-xs font-semibold text-stone-400 dark:text-zinc-500 uppercase tracking-wider">Trackpal Console</span>
        <h1 class="text-xl font-bold tracking-tight text-stone-900 dark:text-zinc-100 mt-0.5">
          {{ i18nStore.t('frontend.subscriptions.title') }}
        </h1>
      </div>
      <button
        @click="openNewModal"
        class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-sm font-medium rounded-md shadow-sm transition-colors cursor-pointer"
      >
        {{ i18nStore.t('frontend.subscriptions.new') || '+ New Subscription' }}
      </button>
    </div>

    <!-- Restructured Table Component -->
    <SubscriptionTable
      :subscriptions="subscriptions"
      :t="i18nStore.t"
      @edit="openEditModal"
      @delete="handleDelete"
    />

    <!-- Restructured Form Modal Component -->
    <SubscriptionModal
      :isOpen="isModalOpen"
      :sub="selectedSub"
      :t="i18nStore.t"
      @close="isModalOpen = false"
      @save="handleSave"
    />
  </DashboardLayout>
</template>
```

- [ ] **Step 4: Verificar compilación e integridad de pruebas**

Ejecuta:
```bash
npm run build && npm test
```
Expected: PASS para todas las pruebas de vitest, y compilación final exitosa.

- [ ] **Step 5: Confirmar cambios**

```bash
git add frontend/src/components/subscriptions/SubscriptionTable.vue frontend/src/components/subscriptions/SubscriptionModal.vue frontend/src/views/SubscriptionsView.vue
git commit -m "refactor: restructure SubscriptionsView and split into SubscriptionTable and SubscriptionModal (< 150 LoC)"
```

---

### Task 6: Adaptar las Vistas Restantes a DashboardLayout

**Files:**
- Modify: `frontend/src/views/MasterDashboardView.vue`
- Modify: `frontend/src/views/TenantDashboardView.vue`
- Modify: `frontend/src/views/ClientDashboardView.vue`

- [ ] **Step 1: Adaptar TenantDashboardView.vue**

Modifica `frontend/src/views/TenantDashboardView.vue` para conectarla al `DashboardLayout` y aplicar clases de Tailwind v4, manteniendo intactas la integración de componentes hijos como `ClientManagementPanel` y `CatalogPanel` pero dándoles la envoltura premium de Linear:
```vue
<script setup>
import { onMounted, ref } from 'vue'
import { useI18nStore } from '../stores/i18n'
import DashboardLayout from '../components/DashboardLayout.vue'
import ClientManagementPanel from '../components/ClientManagementPanel.vue'
import CatalogPanel from '../components/CatalogPanel.vue'
import MailboxConfigPanel from '../components/MailboxConfigPanel.vue'
import CodeServicesTenantPanel from '../components/CodeServicesTenantPanel.vue'

const i18nStore = useI18nStore()
const activeTab = ref('clients')
</script>

<template>
  <DashboardLayout>
    <div class="mb-6">
      <span class="text-xs font-semibold text-stone-400 dark:text-zinc-500 uppercase tracking-wider">Tenant Panel</span>
      <h1 class="text-xl font-bold tracking-tight text-stone-900 dark:text-zinc-100 mt-0.5">
        {{ i18nStore.t('frontend.tenant.title') || 'Tenant Dashboard' }}
      </h1>
    </div>

    <!-- Premium Tab Selectors -->
    <div class="flex gap-2 border-b border-stone-200 dark:border-zinc-800 mb-6">
      <button
        v-for="tab in ['clients', 'catalog', 'mailbox', 'codes']"
        :key="tab"
        @click="activeTab = tab"
        :class="[
          activeTab === tab
            ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
            : 'border-transparent text-stone-500 hover:text-stone-700 dark:text-zinc-400 dark:hover:text-zinc-200',
          'px-4 py-2 text-sm font-medium border-b-2 transition-all cursor-pointer'
        ]"
      >
        <span class="capitalize">{{ tab }}</span>
      </button>
    </div>

    <!-- Inner panels rendering inside our Linear container grid -->
    <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md p-6 shadow-sm">
      <ClientManagementPanel v-if="activeTab === 'clients'" />
      <CatalogPanel v-else-if="activeTab === 'catalog'" />
      <MailboxConfigPanel v-else-if="activeTab === 'mailbox'" />
      <CodeServicesTenantPanel v-else-if="activeTab === 'codes'" />
    </div>
  </DashboardLayout>
</template>
```

- [ ] **Step 2: Adaptar MasterDashboardView.vue**

Modifica `frontend/src/views/MasterDashboardView.vue` de manera idéntica para usar `DashboardLayout` y rediseñar su tabla de administración del sistema global.

- [ ] **Step 3: Adaptar ClientDashboardView.vue**

Modifica `frontend/src/views/ClientDashboardView.vue` para heredar el layout maestro y dar a los clientes finales la misma experiencia premium.

- [ ] **Step 4: Ejecutar build definitivo y validación global**

Ejecuta en la carpeta `frontend/`:
```bash
npm run build && npm test
```
Expected: Toda la suite de tests en verde. Compilación final sin errores.

- [ ] **Step 5: Confirmar cambios**

```bash
git add frontend/src/views/MasterDashboardView.vue frontend/src/views/TenantDashboardView.vue frontend/src/views/ClientDashboardView.vue
git commit -m "feat: complete adaptation of remaining dashboards to shared DashboardLayout with premium Linear aesthetic"
```
