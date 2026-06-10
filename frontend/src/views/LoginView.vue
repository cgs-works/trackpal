<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'
import { usePublicI18n } from '../i18n/usePublicI18n'
import ThemeToggle from '../components/ThemeToggle.vue'
import InlineAlert from '../components/InlineAlert.vue'

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
      await router.push('/master/overview')
    } else if (role === 'tenant') {
      await router.push('/admin/overview')
    } else if (role === 'client') {
      await router.push('/client/overview')
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
      <div class="mt-6 flex items-center justify-center gap-3 text-sm text-muted-foreground lg:hidden">
        <ThemeToggle />
        <select id="locale-select-mobile" v-model="locale" @change="setLocale(locale)" class="h-9 rounded-md border border-input bg-background px-3">
          <option value="en">English</option>
          <option value="es">Español</option>
        </select>
      </div>
    </section>
  </main>
</template>


