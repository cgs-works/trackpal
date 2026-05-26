<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'
import '../styles/client-dashboard.css'
import '../styles/client-dashboard-responsive.css'

const router = useRouter()
const authStore = useAuthStore()
const i18nStore = useI18nStore()

const dashboard = ref(null)
const profile = ref(null)
const passwordForm = ref({
  old_password: '',
  new_password: '',
})
const isLoading = ref(false)
const isSavingPassword = ref(false)
const errorMessage = ref('')
const passwordSuccess = ref('')

const username = computed(() => authStore.username || authStore.user?.username || 'Cliente')
const clientInfo = computed(() => dashboard.value || profile.value || {})
const displayName = computed(() => clientInfo.value.full_name || username.value)

function getApiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  }
  return detail || error.response?.data?.message || fallback
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return isNaN(d.getTime()) ? dateStr : d.toLocaleDateString()
}

async function loadDashboard() {
  errorMessage.value = ''
  isLoading.value = true

  try {
    const [dashboardResponse, profileResponse] = await Promise.all([
      api.get('/dashboard'),
      api.get('/me'),
    ])
    dashboard.value = dashboardResponse.data || null
    profile.value = profileResponse.data || null
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.dashboard.error_load'))
  } finally {
    isLoading.value = false
  }
}

async function changePassword() {
  errorMessage.value = ''
  passwordSuccess.value = ''
  isSavingPassword.value = true

  try {
    await api.put('/me/password', passwordForm.value)
    passwordForm.value = {
      old_password: '',
      new_password: '',
    }
    passwordSuccess.value = i18nStore.t('frontend.dashboard.client.password_updated')
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.dashboard.client.error_password'))
  } finally {
    isSavingPassword.value = false
  }
}

async function handleLogout() {
  await authStore.logout()
  await router.push('/login')
}

onMounted(loadDashboard)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <p class="eyebrow">{{ i18nStore.t('frontend.dashboard.client.title') }}</p>
        <h1>Trackpal</h1>
      </div>

      <div class="user-actions">
        <span class="username">{{ username }}</span>
        <button class="button button-secondary" type="button" @click="handleLogout">{{ i18nStore.t('frontend.dashboard.tenant.logout') }}</button>
      </div>
    </header>

    <section v-if="isLoading" class="content-card loading-card" aria-live="polite">
      <span class="spinner" aria-hidden="true"></span>
      <p>{{ i18nStore.t('frontend.dashboard.loading') }}</p>
    </section>

    <template v-else>
      <p v-if="errorMessage" class="alert alert-error">{{ errorMessage }}</p>

      <section class="content-card welcome-card">
        <p class="eyebrow">{{ i18nStore.t('frontend.dashboard.client.role_label') }}</p>
        <h2>{{ i18nStore.t('frontend.dashboard.client.welcome', { name: displayName }) }}</h2>
        <p>{{ i18nStore.t('frontend.dashboard.client.readonly') }}</p>
      </section>

      <section class="content-card profile-card">
        <div class="section-header">
          <div>
            <p class="eyebrow">{{ i18nStore.t('frontend.dashboard.client.access_info') }}</p>
            <h2>{{ i18nStore.t('frontend.dashboard.client.access_info') }}</h2>
          </div>
        </div>

        <dl class="details-grid">
          <div>
            <dt>{{ i18nStore.t('frontend.dashboard.client.uuid') }}</dt>
            <dd>{{ clientInfo.id }}</dd>
          </div>
          <div>
            <dt>{{ i18nStore.t('frontend.profile.full_name') }}</dt>
            <dd>{{ clientInfo.full_name }}</dd>
          </div>
          <div>
            <dt>{{ i18nStore.t('frontend.dashboard.client.login') }}</dt>
            <dd>{{ clientInfo.username }}</dd>
          </div>
          <div>
            <dt>{{ i18nStore.t('frontend.dashboard.client.local_user') }}</dt>
            <dd>{{ clientInfo.local_username }}</dd>
          </div>
          <div>
            <dt>{{ i18nStore.t('frontend.profile.phone') }}</dt>
            <dd>{{ clientInfo.phone || '—' }}</dd>
          </div>
          <div>
            <dt>{{ i18nStore.t('frontend.dashboard.client.tenant') }}</dt>
            <dd>{{ clientInfo.tenant_name }}</dd>
          </div>
          <div>
            <dt>{{ i18nStore.t('frontend.dashboard.client.prefix') }}</dt>
            <dd>{{ clientInfo.client_prefix }}</dd>
          </div>
          <div>
            <dt>{{ i18nStore.t('frontend.subscriptions.status') }}</dt>
            <dd>{{ clientInfo.is_active ? i18nStore.t('frontend.dashboard.client.status_active') : i18nStore.t('frontend.dashboard.client.status_inactive') }}</dd>
          </div>
        </dl>
      </section>

      <section class="content-card subscriptions-card">
        <div class="section-header">
          <div>
            <p class="eyebrow">{{ i18nStore.t('frontend.dashboard.client.subscriptions') }}</p>
            <h2>{{ i18nStore.t('frontend.dashboard.client.subscriptions') }}</h2>
          </div>
        </div>

        <p class="subsection-desc">{{ i18nStore.t('frontend.dashboard.client.subscriptions_desc') }}</p>

        <div v-if="!clientInfo.subscriptions || !clientInfo.subscriptions.length" class="empty-state">
          <p>{{ i18nStore.t('frontend.dashboard.client.no_subscriptions') }}</p>
        </div>

        <div v-else class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>{{ i18nStore.t('frontend.dashboard.client.service') }}</th>
                <th>{{ i18nStore.t('frontend.dashboard.client.plan') }}</th>
                <th>{{ i18nStore.t('frontend.subscriptions.status') }}</th>
                <th>{{ i18nStore.t('frontend.dashboard.client.start') }}</th>
                <th>{{ i18nStore.t('frontend.dashboard.client.expiry') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="sub in clientInfo.subscriptions" :key="sub.id">
                <td>{{ sub.service_name }}</td>
                <td>{{ sub.plan_name }}</td>
                <td>
                  <span class="status-badge">
                    {{ sub.status }}
                  </span>
                </td>
                <td>{{ formatDate(sub.starts_at) }}</td>
                <td>{{ formatDate(sub.expires_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="content-card profile-card">
        <div class="section-header">
          <div>
            <p class="eyebrow">{{ i18nStore.t('frontend.dashboard.client.security') }}</p>
            <h2>{{ i18nStore.t('frontend.dashboard.client.change_password') }}</h2>
          </div>
        </div>

        <p v-if="passwordSuccess" class="alert alert-success">{{ passwordSuccess }}</p>

        <form class="form-grid" @submit.prevent="changePassword">
          <label>
            {{ i18nStore.t('frontend.dashboard.client.current_password') }}
            <input v-model="passwordForm.old_password" type="password" autocomplete="current-password" required />
          </label>

          <label>
            {{ i18nStore.t('frontend.dashboard.client.new_password') }}
            <input v-model="passwordForm.new_password" type="password" autocomplete="new-password" required />
          </label>

          <div class="form-actions">
            <button class="button button-primary" type="submit" :disabled="isSavingPassword">
              {{ isSavingPassword ? i18nStore.t('frontend.dashboard.client.updating') : i18nStore.t('frontend.dashboard.client.update_password') }}
            </button>
          </div>
        </form>
      </section>
    </template>
  </main>
</template>

