<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'

const router = useRouter()
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
const services = ref([])
const selectedServiceId = ref('')
const plans = ref([])
const serviceName = ref('')
const planName = ref('')
const catalogMessage = ref('')
const clients = ref([])
const clientForm = ref(getEmptyClientForm())
const clientMessage = ref('')
const clientError = ref('')
const isSavingClient = ref(false)
const isLoadingClients = ref(false)
const isEditingClient = computed(() => !!clientForm.value.id)

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

function getEmptyClientForm() {
  return {
    id: null,
    full_name: '',
    local_username: '',
    phone: '',
    password: '',
  }
}

function resetClientForm() {
  clientForm.value = getEmptyClientForm()
}

function getClientError(error, fallback) {
  return getApiError(error, fallback)
}

async function loadClients() {
  clientError.value = ''
  isLoadingClients.value = true

  try {
    const response = await api.get('/clients')
    clients.value = response.data || []
  } catch (error) {
    clientError.value = getClientError(error, i18nStore.t('frontend.clients.error_load'))
  } finally {
    isLoadingClients.value = false
  }
}

function editClient(client) {
  clientError.value = ''
  clientMessage.value = ''
  clientForm.value = {
    id: client.id,
    full_name: client.full_name || '',
    local_username: client.local_username || '',
    phone: client.phone || '',
    password: '',
  }
}

function cancelClientEdit() {
  resetClientForm()
  clientError.value = ''
}

async function saveClient() {
  clientError.value = ''
  clientMessage.value = ''
  isSavingClient.value = true

  try {
    if (isEditingClient.value) {
      const response = await api.put(`/clients/${clientForm.value.id}`, {
        full_name: clientForm.value.full_name,
        local_username: clientForm.value.local_username,
        phone: clientForm.value.phone,
      })
      clientMessage.value = i18nStore.t('frontend.clients.updated', { login: response.data.username })
    } else {
      const response = await api.post('/clients', {
        full_name: clientForm.value.full_name,
        local_username: clientForm.value.local_username,
        phone: clientForm.value.phone,
        password: clientForm.value.password,
      })
      clientMessage.value = i18nStore.t('frontend.clients.created', { login: response.data.username })
    }
    resetClientForm()
    await loadClients()
  } catch (error) {
    clientError.value = getClientError(error, i18nStore.t('frontend.clients.error_save'))
  } finally {
    isSavingClient.value = false
  }
}

async function toggleClientStatus(client) {
  clientError.value = ''
  clientMessage.value = ''
  const endpoint = client.is_active
    ? `/clients/${client.id}/deactivate`
    : `/clients/${client.id}/activate`

  try {
    const response = await api.patch(endpoint)
    clientMessage.value = client.is_active ? i18nStore.t('frontend.clients.deactivated') : i18nStore.t('frontend.clients.activated')
    clients.value = clients.value.map((entry) => (entry.id === client.id ? response.data : entry))
  } catch (error) {
    clientError.value = getClientError(error, i18nStore.t('frontend.clients.error_toggle_status'))
  }
}

async function deleteClient(client) {
  clientError.value = ''
  clientMessage.value = ''

  if (client.is_active) {
    clientError.value = i18nStore.t('frontend.clients.cannot_delete_active')
    return
  }

  if (!window.confirm(i18nStore.t('frontend.clients.confirm_delete', { name: client.full_name }))) {
    return
  }

  try {
    await api.delete(`/clients/${client.id}`)
    clientMessage.value = i18nStore.t('frontend.clients.deleted')
    await loadClients()
  } catch (error) {
    clientError.value = getClientError(error, i18nStore.t('frontend.clients.error_delete'))
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
    await loadServices()
    if (!isMasterSupport.value) {
      await loadClients()
    }
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.dashboard.error_load'))
  } finally {
    isLoading.value = false
  }
}

async function loadServices() {
  const response = await api.get('/catalog/services')
  services.value = response.data || []
  if (!selectedServiceId.value && services.value.length) selectedServiceId.value = services.value[0].id
  if (selectedServiceId.value) await loadPlans()
}

async function loadPlans() {
  if (!selectedServiceId.value) {
    plans.value = []
    return
  }
  const response = await api.get(`/catalog/services/${selectedServiceId.value}/plans`)
  plans.value = response.data || []
}

async function createService() {
  catalogMessage.value = ''
  try {
    const response = await api.post('/catalog/services', { name: serviceName.value })
    serviceName.value = ''
    selectedServiceId.value = response.data.id
    await loadServices()
    catalogMessage.value = i18nStore.t('frontend.catalog.service_created')
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_create_service'))
  }
}

async function renameService(service) {
  const name = window.prompt(i18nStore.t('frontend.catalog.rename_service_prompt'), service.name)
  if (!name) return
  try {
    await api.put(`/catalog/services/${service.id}`, { name })
    await loadServices()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_update_service'))
  }
}

async function deleteService(service) {
  if (!window.confirm(i18nStore.t('frontend.catalog.delete_service_confirm', { name: service.name }))) return
  try {
    await api.delete(`/catalog/services/${service.id}`)
    if (selectedServiceId.value === service.id) selectedServiceId.value = ''
    await loadServices()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_delete_service'))
  }
}

async function createPlan() {
  if (!selectedServiceId.value) return
  try {
    await api.post(`/catalog/services/${selectedServiceId.value}/plans`, { name: planName.value })
    planName.value = ''
    await loadPlans()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_create_plan'))
  }
}

async function renamePlan(plan) {
  const name = window.prompt(i18nStore.t('frontend.catalog.rename_plan_prompt'), plan.name)
  if (!name) return
  try {
    await api.put(`/catalog/services/${selectedServiceId.value}/plans/${plan.id}`, { name })
    await loadPlans()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_update_plan'))
  }
}

async function deletePlan(plan) {
  if (!window.confirm(i18nStore.t('frontend.catalog.delete_plan_confirm', { name: plan.name }))) return
  try {
    await api.delete(`/catalog/services/${selectedServiceId.value}/plans/${plan.id}`)
    await loadPlans()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_delete_plan'))
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

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}

onMounted(loadDashboard)
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

      <section class="content-card welcome-card">
        <p class="eyebrow">{{ isMasterSupport ? 'Soporte Master' : i18nStore.t('frontend.dashboard.tenant.title') }}</p>
        <h2>{{ i18nStore.t('frontend.dashboard.tenant.welcome', { name: displayName }) }}</h2>
        <p v-if="isMasterSupport">{{ i18nStore.t('frontend.dashboard.master_support') }}</p>
        <p v-else>{{ i18nStore.t('frontend.dashboard.tenant.under_construction', { name: displayName }) }}</p>
        <button class="button button-primary" type="button" @click="router.push('/admin/subscriptions')" style="margin-top: 16px;">
          {{ i18nStore.t('frontend.dashboard.tenant.go_subscriptions') }}
        </button>
      </section>

      <section v-if="!isMasterSupport" class="content-card profile-card">
        <div class="section-header">
          <div>
            <p class="eyebrow">{{ i18nStore.t('frontend.catalog.section_title') }}</p>
            <h2>{{ i18nStore.t('frontend.catalog.section_heading') }}</h2>
          </div>
        </div>
        <p v-if="catalogMessage" class="alert alert-success">{{ catalogMessage }}</p>
        <form class="form-grid" @submit.prevent="createService">
          <label>{{ i18nStore.t('frontend.catalog.new_service') }}<input v-model.trim="serviceName" type="text" required /></label>
          <div class="form-actions"><button class="button button-primary" type="submit">{{ i18nStore.t('frontend.catalog.create_service') }}</button></div>
        </form>
        <ul>
          <li v-for="service in services" :key="service.id">
            <button class="link-button" type="button" @click="selectedServiceId = service.id; loadPlans()">{{ service.name }}</button>
            <button class="link-button" type="button" @click="renameService(service)">{{ i18nStore.t('frontend.catalog.edit') }}</button>
            <button class="link-button danger" type="button" @click="deleteService(service)">{{ i18nStore.t('frontend.catalog.delete') }}</button>
          </li>
        </ul>
        <form v-if="selectedServiceId" class="form-grid" @submit.prevent="createPlan">
          <label>{{ i18nStore.t('frontend.catalog.new_plan') }}<input v-model.trim="planName" type="text" required /></label>
          <div class="form-actions"><button class="button button-primary" type="submit">{{ i18nStore.t('frontend.catalog.create_plan') }}</button></div>
        </form>
        <ul v-if="selectedServiceId">
          <li v-for="plan in plans" :key="plan.id">
            {{ plan.name }}
            <button class="link-button" type="button" @click="renamePlan(plan)">{{ i18nStore.t('frontend.catalog.edit') }}</button>
            <button class="link-button danger" type="button" @click="deletePlan(plan)">{{ i18nStore.t('frontend.catalog.delete') }}</button>
          </li>
        </ul>
      </section>

      <section v-if="!isMasterSupport" class="content-card profile-card">
        <div class="section-header">
          <div>
            <p class="eyebrow">{{ i18nStore.t('frontend.clients.section_title') }}</p>
            <h2>{{ i18nStore.t('frontend.clients.section_heading') }}</h2>
          </div>
        </div>

        <p v-if="clientError" class="alert alert-error">{{ clientError }}</p>
        <p v-if="clientMessage" class="alert alert-success">{{ clientMessage }}</p>

        <form class="form-grid" @submit.prevent="saveClient">
          <label>
            {{ i18nStore.t('frontend.profile.full_name') }}
            <input v-model.trim="clientForm.full_name" type="text" required />
          </label>

          <label>
            {{ i18nStore.t('frontend.dashboard.client.local_user') }}
            <input v-model.trim="clientForm.local_username" type="text" required />
          </label>

          <label>
            {{ i18nStore.t('frontend.profile.phone') }}
            <input v-model.trim="clientForm.phone" type="tel" />
          </label>

          <label v-if="!isEditingClient">
            {{ i18nStore.t('frontend.clients.password') }}
            <input v-model="clientForm.password" type="password" autocomplete="new-password" required />
          </label>

          <div class="form-actions">
            <button class="button button-secondary" type="button" @click="cancelClientEdit">{{ i18nStore.t('frontend.clients.clear') }}</button>
            <button class="button button-primary" type="submit" :disabled="isSavingClient">
              {{ isSavingClient ? i18nStore.t('frontend.clients.saving') : (isEditingClient ? i18nStore.t('frontend.clients.update') : i18nStore.t('frontend.clients.create')) }}
            </button>
          </div>
        </form>

        <div v-if="isLoadingClients" class="empty-state">{{ i18nStore.t('frontend.clients.loading') }}</div>
        <div v-else-if="!clients.length" class="empty-state">{{ i18nStore.t('frontend.clients.no_clients') }}</div>
        <div v-else class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>{{ i18nStore.t('frontend.profile.full_name') }}</th>
                <th>{{ i18nStore.t('frontend.dashboard.client.local_user') }}</th>
                <th>Technical Username</th>
                <th>{{ i18nStore.t('frontend.profile.phone') }}</th>
                <th>{{ i18nStore.t('frontend.subscriptions.status') }}</th>
                <th>{{ i18nStore.t('frontend.subscriptions.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="client in clients" :key="client.id">
                <td>{{ client.full_name }}</td>
                <td>{{ client.local_username }}</td>
                <td>{{ client.username }}</td>
                <td>{{ client.phone || '—' }}</td>
                <td>
                  <span class="status-badge" :class="client.is_active ? 'active' : 'inactive'">
                    {{ client.is_active ? i18nStore.t('frontend.dashboard.client.status_active') : i18nStore.t('frontend.dashboard.client.status_inactive') }}
                  </span>
                </td>
                <td>
                  <div class="row-actions">
                    <button class="link-button" type="button" @click="editClient(client)">{{ i18nStore.t('frontend.clients.edit') }}</button>
                    <button class="link-button" type="button" @click="toggleClientStatus(client)">
                      {{ client.is_active ? i18nStore.t('frontend.clients.deactivate') : i18nStore.t('frontend.clients.activate') }}
                    </button>
                    <button class="link-button" type="button" @click="router.push('/admin/subscriptions?client_id=' + client.id)">{{ i18nStore.t('frontend.clients.subscriptions') }}</button>
                    <button class="link-button danger" type="button" @click="deleteClient(client)">{{ i18nStore.t('frontend.clients.delete') }}</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

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
