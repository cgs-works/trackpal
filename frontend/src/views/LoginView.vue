<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import { usePublicI18n } from '@/i18n/usePublicI18n'
import InlineAlert from '@/components/InlineAlert.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

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
