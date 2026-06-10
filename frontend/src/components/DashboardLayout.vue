<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import api from '@/services/api'
import { getNavigationContext } from '@/config/navigation'
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
      ? 'border-primary bg-primary/10 text-primary'
      : 'border-transparent text-muted-foreground hover:border-border hover:bg-accent hover:text-accent-foreground',
    'flex items-center gap-3 rounded-md border px-3 py-2 text-sm font-medium transition-colors',
  ]
}
</script>

<template>
  <div class="min-h-screen bg-background text-foreground flex">

    <!-- ========== DESKTOP SIDEBAR ========== -->
    <aside
      class="hidden md:flex flex-col h-screen w-64 bg-background border-r border-border flex-shrink-0 sticky top-0"
    >
      <!-- Sidebar Header -->
      <div class="h-14 border-b border-border flex items-center px-6 flex-shrink-0">
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 bg-primary rounded-md flex items-center justify-center text-primary-foreground font-bold text-xs shadow-sm">T</div>
          <span class="font-bold tracking-tight text-foreground">Trackpal</span>
        </div>
      </div>

      <!-- Exit support banner (desktop) -->
      <div v-if="isSupportMode" class="px-4 pt-4">
        <Button
          variant="outline"
          size="sm"
          class="w-full gap-2 border-warning/40 text-warning hover:bg-warning/10"
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
            class="text-xs text-muted-foreground bg-transparent border border-border rounded px-1.5 py-1 focus:outline-none cursor-pointer"
            aria-label="Language Selector"
          >
            <option value="en">EN</option>
            <option value="es">ES</option>
          </select>
        </div>

        <!-- User card + logout -->
        <div class="flex items-center gap-3 bg-background/70 border border-border p-2.5 rounded-md">
          <div class="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center font-bold text-sm text-primary">
            {{ userInitial }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-xs font-semibold text-foreground truncate">{{ authStore.username || 'User' }}</p>
            <p class="text-[10px] text-muted-foreground truncate capitalize">{{ authStore.role }}</p>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            @click="handleLogout"
            title="Log out"
            class="text-muted-foreground hover:text-destructive"
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
      <header class="h-14 bg-background border-b border-border px-4 flex items-center justify-between md:hidden flex-shrink-0">
        <Sheet v-model:open="mobileSheetOpen">
          <SheetTrigger as-child>
            <Button data-testid="mobile-nav-trigger" variant="ghost" size="icon" class="text-muted-foreground">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
              </svg>
            </Button>
          </SheetTrigger>

          <SheetContent side="left" class="w-64 p-0 flex flex-col">
            <!-- Sheet sidebar header -->
            <div class="h-14 border-b border-border flex items-center px-6 flex-shrink-0">
              <div class="flex items-center gap-2">
                <div class="w-6 h-6 bg-primary rounded-md flex items-center justify-center text-primary-foreground font-bold text-xs shadow-sm">T</div>
                <span class="font-bold tracking-tight text-foreground">Trackpal</span>
              </div>
            </div>

            <!-- Exit support banner (mobile) -->
            <div v-if="isSupportMode" class="px-4 pt-4">
              <Button
                variant="outline"
                size="sm"
                class="w-full gap-2 border-warning/40 text-warning hover:bg-warning/10"
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
                  class="text-xs text-muted-foreground bg-transparent border border-border rounded px-1.5 py-1 focus:outline-none cursor-pointer"
                  aria-label="Language Selector"
                >
                  <option value="en">EN</option>
                  <option value="es">ES</option>
                </select>
                    </div>

              <div class="flex items-center gap-3 bg-background/70 border border-border p-2.5 rounded-md">
                <div class="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center font-bold text-sm text-primary">
                  {{ userInitial }}
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-xs font-semibold text-foreground truncate">{{ authStore.username || 'User' }}</p>
                  <p class="text-[10px] text-muted-foreground truncate capitalize">{{ authStore.role }}</p>
                </div>
                <SheetClose as-child>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    @click="handleLogout"
                    title="Log out"
                    class="text-muted-foreground hover:text-destructive"
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
      <main class="flex-1 overflow-y-auto p-4 md:p-6">
        <slot />
      </main>
    </div>

  </div>
</template>
