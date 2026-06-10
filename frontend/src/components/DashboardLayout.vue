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
