<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'
import MailboxConfigPanel from '../components/MailboxConfigPanel.vue'
import CatalogPanel from '../components/CatalogPanel.vue'
import ClientManagementPanel from '../components/ClientManagementPanel.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const i18nStore = useI18nStore()

const dashboard = ref(null)
const profile = ref({
  full_name: '',
  email: '',
  phone: '',
  locale: 'en',
})
const passwordForm = ref({
  old_password: '',
  new_password: '',
})
const isLoading = ref(false)
const isSavingProfile = ref(false)
const isSavingPassword = ref(false)
const errorMessage = ref('')
const profileSuccess = ref('')
const passwordSuccess = ref('')
// Mailbox state
const mailbox = ref(null)
const mailboxLoading = ref(false)
const mailboxError = ref('')
const mailboxSuccess = ref('')
const oauthToast = ref('')

const username = computed(() => authStore.username || authStore.user?.username || 'Usuario')
const isMasterSupport = computed(() => authStore.role === 'master' && !!authStore.activeTenantId)
const displayName = computed(() => profile.value.full_name || dashboard.value?.full_name || username.value)

function getApiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  }
  return detail || error.response?.data?.message || fallback
}

function setProfile(data) {
  profile.value = {
    full_name: data?.full_name || '',
    email: data?.email || '',
    phone: data?.phone || '',
    locale: data?.locale || 'en',
  }
}

async function loadDashboard() {
  errorMessage.value = ''
  isLoading.value = true

  try {
    if (isMasterSupport.value) {
      const tenantResponse = await api.get(`/tenants/${authStore.activeTenantId}`)
      dashboard.value = {
        full_name: tenantResponse.data?.full_name,
        message: 'Modo soporte Master activo.',
      }
      setProfile(tenantResponse.data)
    } else {
      const [dashboardResponse, profileResponse] = await Promise.all([
        api.get('/dashboard'),
        api.get('/me'),
      ])

      dashboard.value = dashboardResponse.data || null
      setProfile(profileResponse.data || dashboardResponse.data)
    }
    if (!isMasterSupport.value) {
      await loadMailbox()
    }
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.dashboard.error_load'))
  } finally {
    isLoading.value = false
  }
}

async function exitTenantContext() {
  await authStore.exitTenantContext()
  await router.push('/master/dashboard')
}

async function saveProfile() {
  errorMessage.value = ''
  profileSuccess.value = ''
  passwordSuccess.value = ''
  isSavingProfile.value = true

  try {
    const response = await api.put('/me', profile.value)
    setProfile(response.data || profile.value)
    profileSuccess.value = i18nStore.t('frontend.profile.saved')
    // Reload catalog after locale change
    await i18nStore.loadCatalog()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.profile.error_update'))
  } finally {
    isSavingProfile.value = false
  }
}

async function changePassword() {
  errorMessage.value = ''
  profileSuccess.value = ''
  passwordSuccess.value = ''
  isSavingPassword.value = true

  try {
    await api.put('/me/password', passwordForm.value)
    passwordForm.value = {
      old_password: '',
      new_password: '',
    }
    passwordSuccess.value = i18nStore.t('frontend.profile.password_updated')
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.profile.error_password'))
  } finally {
    isSavingPassword.value = false
  }
}

// Mailbox functions — delegated to MailboxConfigPanel component
async function loadMailbox() {
  mailboxError.value = ''
  mailboxLoading.value = true
  try {
    const response = await api.get('/tenant/mailbox/')
    mailbox.value = response.data
  } catch (error) {
    if (error.response?.status === 404) {
      mailbox.value = null
    } else {
      mailboxError.value = getApiError(error, i18nStore.t('frontend.mailbox.error_load'))
    }
  } finally {
    mailboxLoading.value = false
  }
}

function onMailboxUpdated() {
  loadMailbox()
}

function maybeShowOAuthToastFromQuery() {
  if (route.query.mailbox_oauth === 'success') {
    oauthToast.value = i18nStore.t('frontend.mailbox.oauth_connected')
    const nextQuery = { ...route.query }
    delete nextQuery.mailbox_oauth
    router.replace({ path: route.path, query: nextQuery })
    setTimeout(() => {
      oauthToast.value = ''
    }, 4000)
  }
}

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}

onMounted(async () => {
  maybeShowOAuthToastFromQuery()
  await loadDashboard()
})
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <p class="eyebrow">Trackpal</p>
        <h1>Trackpal</h1>
      </div>

      <div class="user-actions">
        <span class="username">{{ username }}</span>
        <button v-if="authStore.role === 'master' && authStore.activeTenantId" class="button button-secondary" type="button" @click="exitTenantContext">{{ i18nStore.t('frontend.dashboard.tenant.exit_tenant') }}</button>
        <button class="button button-secondary" type="button" @click="handleLogout">{{ i18nStore.t('frontend.dashboard.tenant.logout') }}</button>
      </div>
    </header>

    <section v-if="isLoading" class="content-card loading-card" aria-live="polite">
      <span class="spinner" aria-hidden="true"></span>
      <p>{{ i18nStore.t('frontend.dashboard.loading') }}</p>
    </section>

    <template v-else>
      <p v-if="errorMessage" class="alert alert-error">{{ errorMessage }}</p>
      <p v-if="oauthToast" class="toast toast-success">{{ oauthToast }}</p>

      <section class="content-card welcome-card">
        <p class="eyebrow">{{ isMasterSupport ? 'Soporte Master' : i18nStore.t('frontend.dashboard.tenant.title') }}</p>
        <h2>{{ i18nStore.t('frontend.dashboard.tenant.welcome', { name: displayName }) }}</h2>
        <p v-if="isMasterSupport">{{ i18nStore.t('frontend.dashboard.master_support') }}</p>
        <p v-else>{{ i18nStore.t('frontend.dashboard.tenant.under_construction', { name: displayName }) }}</p>
        <button class="button button-primary" type="button" @click="router.push('/admin/subscriptions')" style="margin-top: 16px;">
          {{ i18nStore.t('frontend.dashboard.tenant.go_subscriptions') }}
        </button>
      </section>

      <!-- Mailbox section -- delegated to MailboxConfigPanel -->
      <MailboxConfigPanel
        v-if="!isMasterSupport"
        :mailbox="mailbox"
        @updated="onMailboxUpdated"
      />

      <CatalogPanel v-if="!isMasterSupport" />
      <ClientManagementPanel v-if="!isMasterSupport" />

      <section v-if="!isMasterSupport" class="content-card profile-card">
        <div class="section-header">
          <div>
            <p class="eyebrow">{{ i18nStore.t('frontend.profile.section_title') }}</p>
            <h2>{{ i18nStore.t('frontend.profile.section_heading') }}</h2>
          </div>
        </div>

        <p v-if="profileSuccess" class="alert alert-success">{{ profileSuccess }}</p>

        <form class="form-grid" @submit.prevent="saveProfile">
          <label>
            {{ i18nStore.t('frontend.profile.full_name') }}
            <input v-model="profile.full_name" type="text" autocomplete="name" required />
          </label>

          <label>
            {{ i18nStore.t('frontend.profile.email') }}
            <input v-model="profile.email" type="email" autocomplete="email" required />
          </label>

          <label>
            {{ i18nStore.t('frontend.profile.phone') }}
            <input v-model="profile.phone" type="tel" autocomplete="tel" />
          </label>

          <label>
            {{ i18nStore.t('frontend.profile.locale') }}
            <select v-model="profile.locale">
              <option value="en">English</option>
              <option value="es">Español</option>
            </select>
          </label>

          <div class="form-actions">
            <button class="button button-primary" type="submit" :disabled="isSavingProfile">
              {{ isSavingProfile ? i18nStore.t('frontend.profile.saving') : i18nStore.t('frontend.profile.save') }}
            </button>
          </div>
        </form>
      </section>

      <section v-if="!isMasterSupport" class="content-card profile-card">
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

<style scoped>
:global(:root) {
  --primary: #4f46e5;
  --success: #22c55e;
  --danger: #ef4444;
  --bg: #f8fafc;
  --card-bg: #ffffff;
  --text: #1e293b;
  --text-secondary: #64748b;
  --border: #e2e8f0;
}

.dashboard-page {
  min-height: 100vh;
  padding: 32px;
  background: var(--bg);
  color: var(--text);
}

.dashboard-header,
.section-header,
.user-actions,
.form-actions,
.loading-card {
  display: flex;
  align-items: center;
}

.dashboard-header,
.section-header {
  justify-content: space-between;
  gap: 16px;
}

.dashboard-header {
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--text-secondary);
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 0;
  font-size: 2rem;
}

h2 {
  margin-bottom: 8px;
}

.user-actions {
  gap: 12px;
}

.username {
  color: var(--text-secondary);
  font-weight: 600;
}

.content-card {
  margin-bottom: 24px;
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 24px;
  background: var(--card-bg);
  box-shadow: 0 10px 25px rgb(15 23 42 / 8%);
}

.welcome-card p:last-child,
.profile-card p:last-child {
  margin-bottom: 0;
}

.placeholder-message {
  border-radius: 12px;
  padding: 14px 16px;
  background: var(--bg);
  color: var(--text-secondary);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

label {
  display: grid;
  gap: 8px;
  color: var(--text-secondary);
  font-weight: 700;
}

input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 11px 12px;
  color: var(--text);
  font: inherit;
}

input:focus {
  border-color: var(--primary);
  outline: 3px solid rgb(79 70 229 / 15%);
}

.form-actions {
  grid-column: 1 / -1;
  justify-content: flex-end;
}

.button {
  cursor: pointer;
  border: 0;
  border-radius: 10px;
  padding: 10px 16px;
  font: inherit;
  font-weight: 700;
}

.button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.button-primary {
  background: var(--primary);
  color: #ffffff;
}

.button-secondary {
  border: 1px solid var(--border);
  background: var(--card-bg);
  color: var(--text);
}

.alert {
  border-radius: 12px;
  padding: 12px 14px;
  font-weight: 700;
}

.alert-error {
  border: 1px solid rgb(239 68 68 / 30%);
  background: rgb(239 68 68 / 10%);
  color: #b91c1c;
}

.alert-success {
  border: 1px solid rgb(34 197 94 / 30%);
  background: rgb(34 197 94 / 10%);
  color: #15803d;
}

.toast {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
  border-radius: 12px;
  padding: 12px 14px;
  font-weight: 700;
  box-shadow: 0 8px 20px rgb(15 23 42 / 20%);
}

.toast-success {
  border: 1px solid rgb(34 197 94 / 35%);
  background: #f0fdf4;
  color: #15803d;
}

.table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 14px 12px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  white-space: nowrap;
}

th {
  color: var(--text-secondary);
  font-size: 0.8rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

tbody tr:hover {
  background: #f1f5f9;
}

.status-badge {
  display: inline-flex;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 0.8rem;
  font-weight: 700;
}

.status-badge.active {
  background: #dcfce7;
  color: #166534;
}

.status-badge.inactive {
  background: #fef3c7;
  color: #92400e;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.link-button {
  cursor: pointer;
  border: 0;
  background: transparent;
  color: var(--primary);
  font: inherit;
  font-weight: 700;
}

.link-button.danger {
  color: var(--danger);
}

.loading-card {
  justify-content: center;
  gap: 12px;
  color: var(--text-secondary);
}

.spinner {
  width: 22px;
  height: 22px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 999px;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 720px) {
  .dashboard-page {
    padding: 20px;
  }

  .dashboard-header,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .form-actions {
    justify-content: stretch;
  }

  .button {
    width: 100%;
  }
}
</style>
