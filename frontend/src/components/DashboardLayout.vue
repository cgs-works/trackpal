<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import api from '@/services/api'
import { getNavigationContext } from '@/config/navigation'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetClose,
} from '@/components/ui/sheet'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const i18nStore = useI18nStore()

const mobileSheetOpen = ref(false)

const userInitial = computed(() => {
  return authStore.username ? authStore.username.charAt(0).toUpperCase() : 'U'
})

const navContext = computed(() => getNavigationContext(authStore, route))

const isSupportMode = computed(() => navContext.value.mode === 'tenant-support')

async function handleLogout() {
  await authStore.logout()
  await router.push('/login')
}

async function handleExitSupport() {
  mobileSheetOpen.value = false
  await authStore.switchTenant(null)
  await router.push('/master/overview')
}

async function setLocale(lang) {
  if (authStore.role === 'tenant' || isSupportMode.value) {
    try {
      await api.put('/me', { locale: lang })
    } catch (err) {
      console.error('Failed to save language selection:', err)
    }
  }
  i18nStore.locale = lang
  localStorage.setItem('locale', lang)
  await i18nStore.loadCatalog()
}

function onNavClick() {
  mobileSheetOpen.value = false
}

function navLinkClasses(itemPath) {
  return [
    route.path === itemPath
      ? 'bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 dark:text-indigo-400 border border-indigo-200/30 dark:border-indigo-950/40'
      : 'hover:bg-stone-50 dark:hover:bg-zinc-800/50 text-stone-600 dark:text-zinc-300 border border-transparent',
    'flex items-center gap-3 px-3 py-2 rounded-md font-medium text-sm transition-colors',
  ]
}
</script>

<template>
  <div class="min-h-screen bg-stone-50 dark:bg-zinc-950 text-stone-900 dark:text-zinc-100 flex transition-colors duration-200">

    <!-- ========== DESKTOP SIDEBAR ========== -->
    <aside
      class="hidden md:flex flex-col h-screen w-64 bg-white dark:bg-zinc-900 border-r border-stone-200 dark:border-zinc-800 flex-shrink-0 sticky top-0"
    >
      <!-- Sidebar Header -->
      <div class="h-14 border-b border-stone-200 dark:border-zinc-800 flex items-center px-6 flex-shrink-0">
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 bg-indigo-600 rounded-md flex items-center justify-center text-white font-bold text-xs shadow-sm">T</div>
          <span class="font-bold tracking-tight text-stone-900 dark:text-zinc-100">Trackpal</span>
        </div>
      </div>

      <!-- Exit support banner (desktop) -->
      <div v-if="isSupportMode" class="px-4 pt-4">
        <Button
          variant="outline"
          size="sm"
          class="w-full gap-2 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800 hover:bg-amber-50 dark:hover:bg-amber-950/30"
          @click="handleExitSupport"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" />
          </svg>
          Exit support
        </Button>
      </div>

      <!-- Navigation Menu -->
      <nav class="flex-1 p-4 flex flex-col gap-1 overflow-y-auto">
        <router-link
          v-for="item in navContext.items"
          :key="item.to"
          :to="item.to"
          :class="navLinkClasses(item.to)"
          @click="onNavClick"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <Separator />

      <!-- Sidebar Footer -->
      <div class="p-4 flex flex-col gap-3 flex-shrink-0">
        <!-- Locale + Theme row -->
        <div class="flex items-center justify-between">
          <select
            :value="i18nStore.locale"
            @change="setLocale($event.target.value)"
            class="text-xs text-stone-500 dark:text-zinc-400 bg-transparent border border-stone-200 dark:border-zinc-800 rounded px-1.5 py-1 focus:outline-none cursor-pointer"
            aria-label="Language Selector"
          >
            <option value="en">EN</option>
            <option value="es">ES</option>
          </select>
          <ThemeToggle />
        </div>

        <!-- User card + logout -->
        <div class="flex items-center gap-3 bg-stone-50 dark:bg-zinc-950/50 border border-stone-200/50 dark:border-zinc-800/50 p-2.5 rounded-md">
          <div class="w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-950 flex items-center justify-center font-bold text-sm text-indigo-600 dark:text-indigo-400">
            {{ userInitial }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-xs font-semibold text-stone-800 dark:text-zinc-200 truncate">{{ authStore.username || 'User' }}</p>
            <p class="text-[10px] text-stone-400 dark:text-zinc-500 truncate capitalize">{{ authStore.role }}</p>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            @click="handleLogout"
            title="Log out"
            class="text-stone-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75" />
            </svg>
          </Button>
        </div>
      </div>
    </aside>

    <!-- ========== MAIN CONTENT ========== -->
    <div class="flex-1 flex flex-col min-w-0">

      <!-- Mobile header -->
      <header class="h-14 bg-white dark:bg-zinc-900 border-b border-stone-200 dark:border-zinc-800 px-4 flex items-center justify-between md:hidden flex-shrink-0">
        <Sheet v-model:open="mobileSheetOpen">
          <SheetTrigger as-child>
            <Button variant="ghost" size="icon" class="text-stone-500 dark:text-zinc-400">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
              </svg>
            </Button>
          </SheetTrigger>

          <SheetContent side="left" class="w-64 p-0 flex flex-col">
            <!-- Sheet sidebar header -->
            <div class="h-14 border-b border-stone-200 dark:border-zinc-800 flex items-center px-6 flex-shrink-0">
              <div class="flex items-center gap-2">
                <div class="w-6 h-6 bg-indigo-600 rounded-md flex items-center justify-center text-white font-bold text-xs shadow-sm">T</div>
                <span class="font-bold tracking-tight text-stone-900 dark:text-zinc-100">Trackpal</span>
              </div>
            </div>

            <!-- Exit support banner (mobile) -->
            <div v-if="isSupportMode" class="px-4 pt-4">
              <Button
                variant="outline"
                size="sm"
                class="w-full gap-2 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800 hover:bg-amber-50 dark:hover:bg-amber-950/30"
                @click="handleExitSupport"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" />
                </svg>
                Exit support
              </Button>
            </div>

            <!-- Sheet nav menu -->
            <nav class="flex-1 p-4 flex flex-col gap-1 overflow-y-auto">
              <router-link
                v-for="item in navContext.items"
                :key="item.to"
                :to="item.to"
                :class="navLinkClasses(item.to)"
                @click="onNavClick"
              >
                {{ item.label }}
              </router-link>
            </nav>

            <Separator />

            <!-- Sheet footer -->
            <div class="p-4 flex flex-col gap-3 flex-shrink-0">
              <div class="flex items-center justify-between">
                <select
                  :value="i18nStore.locale"
                  @change="setLocale($event.target.value)"
                  class="text-xs text-stone-500 dark:text-zinc-400 bg-transparent border border-stone-200 dark:border-zinc-800 rounded px-1.5 py-1 focus:outline-none cursor-pointer"
                  aria-label="Language Selector"
                >
                  <option value="en">EN</option>
                  <option value="es">ES</option>
                </select>
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
                <SheetClose as-child>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    @click="handleLogout"
                    title="Log out"
                    class="text-stone-400 hover:text-red-500 dark:text-zinc-500 dark:hover:text-red-400"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75" />
                    </svg>
                  </Button>
                </SheetClose>
              </div>
            </div>
          </SheetContent>
        </Sheet>

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
