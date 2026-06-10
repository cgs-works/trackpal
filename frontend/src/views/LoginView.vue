<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'
import { usePublicI18n } from '../i18n/usePublicI18n'

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
    // Load i18n catalog after login (for post-auth views)
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
  <main class="login-layout">
    <div class="login-container">
      <div class="login-header">
        <h1 class="login-title">{{ t('login.title') }}</h1>
      </div>

      <form class="login-form" @submit.prevent="handleSubmit">
        <div class="form-group">
          <label for="username">{{ t('login.username') }}</label>
          <input
            id="username"
            v-model="username"
            type="text"
            autocomplete="username"
            required
            :disabled="isLoading"
          >
        </div>

        <div class="form-group">
          <label for="password">{{ t('login.password') }}</label>
          <input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            :disabled="isLoading"
          >
        </div>

        <Transition name="fade">
          <div v-if="errorMessage" class="error-alert" role="alert">
            {{ errorMessage }}
          </div>
        </Transition>

        <button type="submit" class="btn-primary" :disabled="isLoading">
          {{ isLoading ? t('login.signing_in') : t('login.sign_in') }}
        </button>
      </form>
    </div>

    <div class="login-footer">
      <div class="locale-selector">
        <select id="locale-select" v-model="locale" @change="setLocale(locale)" aria-label="Language">
          <option value="en">English</option>
          <option value="es">Español</option>
        </select>
      </div>
    </div>
  </main>
</template>
