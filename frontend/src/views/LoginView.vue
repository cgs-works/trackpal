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
  <main class="min-h-screen flex flex-col items-center justify-center p-6 bg-stone-50 dark:bg-zinc-950 transition-colors duration-200 relative">
    
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
