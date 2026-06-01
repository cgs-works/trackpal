<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'
import ReminderSettingsModal from '../components/subscriptions/ReminderSettingsModal.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const i18nStore = useI18nStore()

const subscriptions = ref([])
const clients = ref([])
const services = ref([])
const planMap = ref({})
const isLoading = ref(false)
const errorMessage = ref('')

// Modal state
const showCreateModal = ref(false)
const showEditModal = ref(false)
const showRenewModal = ref(false)
const showReactivateModal = ref(false)
const showCancelConfirm = ref(false)
const selectedSubscription = ref(null)
const confirmCancelId = ref(null)
const isSaving = ref(false)
const showPassword = ref(false)
const showProfile = ref(false)
const showReminderSettings = ref(false)
const reminderSettings = ref({
  reminders_enabled: false,
  timezone: 'UTC',
  warning_days: [7, 3, 1],
  reminder_time: '09:00',
  recipient_mode: 'tenant_only',
})
const availablePlans = ref([])

// Form data
const formData = ref({
  client_id: '',
  service_id: '',
  plan_id: '',
  streaming_email: '',
  streaming_password: '',
  starts_at: '',
  duration_type: '',
  expires_at: '',
  profile_name: '',
  profile_pin: '',
})

const renewForm = ref({
  duration_type: '',
  expires_at: '',
})

const reactivateForm = ref({
  duration_type: '',
  starts_at: '',
  expires_at: '',
})

const cancelNotes = ref('')

const durationOptions = computed(() => [
  { value: '1_month', label: i18nStore.t('frontend.subscriptions.duration_1_month') },
  { value: '3_months', label: i18nStore.t('frontend.subscriptions.duration_3_months') },
  { value: '6_months', label: i18nStore.t('frontend.subscriptions.duration_6_months') },
  { value: '9_months', label: i18nStore.t('frontend.subscriptions.duration_9_months') },
  { value: '1_year', label: i18nStore.t('frontend.subscriptions.duration_1_year') },
  { value: 'custom', label: i18nStore.t('frontend.subscriptions.duration_custom') },
])

const isCustomDuration = computed(() => formData.value.duration_type === 'custom')
const isRenewCustomDuration = computed(() => renewForm.value.duration_type === 'custom')
const isReactivateCustomDuration = computed(() => reactivateForm.value.duration_type === 'custom')

const filters = ref({
  status: '',
  client_id: '',
  service_id: '',
  expires_from: '',
  expires_to: '',
})

const username = computed(() => authStore.username || authStore.user?.username || 'Usuario')
const isMasterSupport = computed(() => authStore.role === 'master' && !!authStore.activeTenantId)

function getApiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  }
  return detail || error.response?.data?.message || fallback
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  return date.toLocaleDateString('es-ES', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

function getStatusClass(status) {
  switch (status) {
    case 'active': return 'status-active'
    case 'expired': return 'status-expired'
    case 'cancelled': return 'status-cancelled'
    default: return ''
  }
}

function getStatusLabel(status) {
  switch (status) {
    case 'active': return i18nStore.t('frontend.subscriptions.status_active')
    case 'expired': return i18nStore.t('frontend.subscriptions.status_expired')
    case 'cancelled': return i18nStore.t('frontend.subscriptions.status_cancelled')
    default: return status || '—'
  }
}

function getClientName(clientId) {
  const client = clients.value.find((c) => c.id === clientId)
  return client ? client.full_name : clientId
}

function getServiceName(serviceId) {
  const service = services.value.find((s) => s.id === serviceId)
  return service ? service.name : serviceId
}

function getPlanName(planId) {
  return planMap.value[planId] || planId
}

function setQuickFilter(key) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  if (key === 'this_week') {
    const end = new Date(today)
    end.setDate(end.getDate() + 7)
    filters.value.expires_from = today.toISOString().split('T')[0]
    filters.value.expires_to = end.toISOString().split('T')[0]
  } else if (key === 'this_month') {
    const end = new Date(today)
    end.setMonth(end.getMonth() + 1)
    filters.value.expires_from = today.toISOString().split('T')[0]
    filters.value.expires_to = end.toISOString().split('T')[0]
  } else if (key === 'expired') {
    filters.value.expires_to = today.toISOString().split('T')[0]
    filters.value.expires_from = ''
  }
}

function clearFilters() {
  filters.value = {
    status: '',
    client_id: '',
    service_id: '',
    expires_from: '',
    expires_to: '',
  }
}

async function loadClients() {
  try {
    const response = await api.get('/clients')
    clients.value = response.data || []
  } catch (error) {
    // Non-fatal; clients filter will be empty
  }
}

async function loadServices() {
  try {
    const response = await api.get('/catalog/services')
    services.value = response.data || []
  } catch (error) {
    // Non-fatal; services filter will be empty
  }
}

async function buildPlanMap() {
  const map = {}
  for (const service of services.value) {
    try {
      const response = await api.get(`/catalog/services/${service.id}/plans`)
      const plans = response.data || []
      for (const plan of plans) {
        map[plan.id] = plan.name
      }
    } catch (error) {
      // Skip plans for services that fail
    }
  }
  planMap.value = map
}

async function loadSubscriptions() {
  errorMessage.value = ''
  isLoading.value = true

  try {
    const params = {}
    if (filters.value.status) params.status = filters.value.status
    if (filters.value.client_id) params.client_id = filters.value.client_id
    if (filters.value.service_id) params.service_id = filters.value.service_id
    if (filters.value.expires_from) params.expires_from = filters.value.expires_from
    if (filters.value.expires_to) params.expires_to = filters.value.expires_to

    const response = await api.get('/subscriptions', { params })
    subscriptions.value = response.data || []
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.subscriptions.error_load'))
  } finally {
    isLoading.value = false
  }
}

async function goBack() {
  await router.push('/admin/dashboard')
}

async function init() {
  await Promise.all([loadClients(), loadServices()])
  await buildPlanMap()

  // Pre-set client_id from route query
  if (route.query.client_id) {
    filters.value.client_id = route.query.client_id
  }

  await loadSubscriptions()
}

// --- Modal helpers ---

async function loadPlans(serviceId) {
  if (!serviceId) {
    availablePlans.value = []
    formData.value.plan_id = ''
    return
  }
  try {
    const response = await api.get(`/catalog/services/${serviceId}/plans`)
    availablePlans.value = response.data || []
  } catch (error) {
    availablePlans.value = []
    formData.value.plan_id = ''
  }
}

function openCreateModal() {
  formData.value = {
    client_id: '',
    service_id: '',
    plan_id: '',
    streaming_email: '',
    streaming_password: '',
    starts_at: new Date().toISOString().split('T')[0],
    duration_type: '',
    expires_at: '',
    profile_name: '',
    profile_pin: '',
  }
  availablePlans.value = []
  showPassword.value = false
  showProfile.value = false
  showCreateModal.value = true
}

function openEditModal(sub) {
  selectedSubscription.value = sub
  formData.value = {
    client_id: sub.client_id || '',
    service_id: sub.service_id || '',
    plan_id: sub.plan_id || '',
    streaming_email: sub.streaming_email || '',
    streaming_password: sub.streaming_password || '',
    starts_at: sub.starts_at ? sub.starts_at.split('T')[0] : '',
    duration_type: sub.duration_type || '',
    expires_at: sub.expires_at ? sub.expires_at.split('T')[0] : '',
    profile_name: sub.profile_name || '',
    profile_pin: sub.profile_pin || '',
  }
  showPassword.value = false
  showProfile.value = !!(sub.profile_name || sub.profile_pin)
  showEditModal.value = true
  if (sub.service_id) loadPlans(sub.service_id)
}

function openRenewModal(sub) {
  selectedSubscription.value = sub
  renewForm.value = { duration_type: '', expires_at: '' }
  showRenewModal.value = true
}

function openReactivateModal(sub) {
  selectedSubscription.value = sub
  reactivateForm.value = { duration_type: '', starts_at: '', expires_at: '' }
  showReactivateModal.value = true
}

function confirmCancel(sub) {
  confirmCancelId.value = sub.id
  cancelNotes.value = ''
  showCancelConfirm.value = true
}

async function doCancel() {
  if (!confirmCancelId.value) return
  isSaving.value = true
  try {
    await api.post(`/subscriptions/${confirmCancelId.value}/cancel`, { notes: cancelNotes.value || '' })
    showCancelConfirm.value = false
    confirmCancelId.value = null
    await loadSubscriptions()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.subscriptions.error_cancel'))
  } finally {
    isSaving.value = false
  }
}

async function saveSubscription() {
  isSaving.value = true
  try {
    const payload = {
      client_id: formData.value.client_id,
      service_id: formData.value.service_id,
      plan_id: formData.value.plan_id,
      streaming_email: formData.value.streaming_email,
      streaming_password: formData.value.streaming_password || undefined,
      starts_at: formData.value.starts_at || new Date().toISOString().split('T')[0],
      duration_type: formData.value.duration_type,
      expires_at: formData.value.duration_type === 'custom' ? formData.value.expires_at : undefined,
      profile_name: formData.value.profile_name || undefined,
      profile_pin: formData.value.profile_pin || undefined,
    }
    if (showEditModal.value && selectedSubscription.value) {
      await api.put(`/subscriptions/${selectedSubscription.value.id}`, payload)
    } else {
      await api.post('/subscriptions', payload)
    }
    showCreateModal.value = false
    showEditModal.value = false
    selectedSubscription.value = null
    await loadSubscriptions()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.subscriptions.error_save'))
  } finally {
    isSaving.value = false
  }
}

async function doRenew() {
  if (!selectedSubscription.value) return
  isSaving.value = true
  try {
    const payload = {
      duration_type: renewForm.value.duration_type,
      expires_at: renewForm.value.duration_type === 'custom' ? renewForm.value.expires_at : undefined,
    }
    await api.post(`/subscriptions/${selectedSubscription.value.id}/renew`, payload)
    showRenewModal.value = false
    selectedSubscription.value = null
    await loadSubscriptions()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.subscriptions.error_renew'))
  } finally {
    isSaving.value = false
  }
}

async function doReactivate() {
  if (!selectedSubscription.value) return
  isSaving.value = true
  try {
    const payload = {
      duration_type: reactivateForm.value.duration_type,
      starts_at: reactivateForm.value.starts_at || undefined,
      expires_at: reactivateForm.value.duration_type === 'custom' ? reactivateForm.value.expires_at : undefined,
    }
    await api.post(`/subscriptions/${selectedSubscription.value.id}/reactivate`, payload)
    showReactivateModal.value = false
    selectedSubscription.value = null
    await loadSubscriptions()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.subscriptions.error_reactivate'))
  } finally {
    isSaving.value = false
  }
}

function closeModals() {
  showCreateModal.value = false
  showEditModal.value = false
  showRenewModal.value = false
  showReactivateModal.value = false
  showCancelConfirm.value = false
  showReminderSettings.value = false
  confirmCancelId.value = null
  selectedSubscription.value = null
}

// Watch service_id changes to reload plans
watch(() => formData.value.service_id, (newVal) => {
  formData.value.plan_id = ''
  if (newVal) {
    loadPlans(newVal)
  } else {
    availablePlans.value = []
  }
})

// --- Credential reveal ---
const revealedRowId = ref(null)
const revealedCredentials = ref({})
let revealTimer = null

async function revealCredentials(subId) {
  // If clicking the already-revealed row, hide it
  if (revealedRowId.value === subId) {
    hideRevealed()
    return
  }
  // Hide previous reveal
  hideRevealed()

  revealedRowId.value = subId
  try {
    const response = await api.get(`/subscriptions/${subId}/reveal`)
    revealedCredentials.value = { ...revealedCredentials.value, [subId]: response.data }

    // Auto-hide after 10 seconds
    revealTimer = setTimeout(() => {
      hideRevealed()
    }, 10000)
  } catch (error) {
    revealedRowId.value = null
    errorMessage.value = getApiError(error, i18nStore.t('frontend.subscriptions.error_reveal'))
  }
}

function hideRevealed() {
  if (revealTimer) {
    clearTimeout(revealTimer)
    revealTimer = null
  }
  if (revealedRowId.value) {
    const id = revealedRowId.value
    const copy = { ...revealedCredentials.value }
    delete copy[id]
    revealedCredentials.value = copy
    revealedRowId.value = null
  }
}



onMounted(init)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <p class="eyebrow">Trackpal</p>
        <h1>{{ i18nStore.t('frontend.subscriptions.title') }}</h1>
      </div>

      <div class="user-actions">
        <span class="username">{{ username }}</span>
        <button class="button button-primary" type="button" @click="openCreateModal">{{ i18nStore.t('frontend.subscriptions.new') }}</button>
        <button class="button button-secondary" type="button" @click="showReminderSettings = true">{{ i18nStore.t('frontend.subscriptions.reminder_settings') }}</button>
        <button class="button button-secondary" type="button" @click="goBack">{{ i18nStore.t('frontend.subscriptions.back') }}</button>
        <button class="button button-secondary" type="button" @click="authStore.logout(); router.push('/login')">{{ i18nStore.t('frontend.subscriptions.logout') }}</button>
      </div>
    </header>

    <section class="content-card filters-card">
      <div class="section-header">
        <div>
          <p class="eyebrow">{{ i18nStore.t('frontend.subscriptions.filters') }}</p>
          <h2>{{ i18nStore.t('frontend.subscriptions.search') }}</h2>
        </div>
        <button class="button button-secondary" type="button" @click="clearFilters">{{ i18nStore.t('frontend.subscriptions.clear_filters') }}</button>
      </div>

      <div class="filters-grid">
        <label>
          {{ i18nStore.t('frontend.subscriptions.status') }}
          <select v-model="filters.status">
            <option value="">{{ i18nStore.t('frontend.subscriptions.status_all_active') }}</option>
            <option value="active">{{ i18nStore.t('frontend.subscriptions.status_active') }}</option>
            <option value="expired">{{ i18nStore.t('frontend.subscriptions.status_expired') }}</option>
            <option value="cancelled">{{ i18nStore.t('frontend.subscriptions.status_cancelled') }}</option>
          </select>
        </label>

        <label>
          {{ i18nStore.t('frontend.subscriptions.client') }}
          <select v-model="filters.client_id">
            <option value="">{{ i18nStore.t('frontend.subscriptions.client') }}s</option>
            <option v-for="client in clients" :key="client.id" :value="client.id">
              {{ client.full_name }}
            </option>
          </select>
        </label>

        <label>
          {{ i18nStore.t('frontend.subscriptions.service') }}
          <select v-model="filters.service_id">
            <option value="">{{ i18nStore.t('frontend.subscriptions.service') }}s</option>
            <option v-for="service in services" :key="service.id" :value="service.id">
              {{ service.name }}
            </option>
          </select>
        </label>

        <div class="quick-filters">
          <span class="filter-label">{{ i18nStore.t('frontend.subscriptions.status') }}:</span>
          <button class="button button-sm" type="button" @click="setQuickFilter('this_week')">{{ i18nStore.t('frontend.subscriptions.quick_this_week') }}</button>
          <button class="button button-sm" type="button" @click="setQuickFilter('this_month')">{{ i18nStore.t('frontend.subscriptions.quick_this_month') }}</button>
          <button class="button button-sm" type="button" @click="setQuickFilter('expired')">{{ i18nStore.t('frontend.subscriptions.quick_expired') }}</button>
        </div>

        <label>
          {{ i18nStore.t('frontend.subscriptions.filter_from') }}
          <input v-model="filters.expires_from" type="date" />
        </label>

        <label>
          {{ i18nStore.t('frontend.subscriptions.filter_to') }}
          <input v-model="filters.expires_to" type="date" />
        </label>
      </div>

      <div class="form-actions">
        <button class="button button-primary" type="button" @click="loadSubscriptions">{{ i18nStore.t('frontend.subscriptions.apply') }}</button>
      </div>
    </section>

    <section class="content-card subscriptions-card">
      <div class="section-header">
        <div>
          <p class="eyebrow">{{ i18nStore.t('frontend.subscriptions.title') }}</p>
          <h2>{{ i18nStore.t('frontend.subscriptions.title') }} {{ subscriptions.length ? `(${subscriptions.length})` : '' }}</h2>
        </div>
      </div>

      <p v-if="errorMessage" class="alert alert-error">{{ errorMessage }}</p>

      <div v-if="isLoading" class="empty-state">
        <span class="spinner" aria-hidden="true"></span>
        <p>{{ i18nStore.t('frontend.subscriptions.loading') }}</p>
      </div>

      <div v-else-if="!subscriptions.length" class="empty-state">
        <p>{{ i18nStore.t('frontend.subscriptions.no_results') }}</p>
      </div>

      <div v-else class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>{{ i18nStore.t('frontend.subscriptions.client') }}</th>
              <th>{{ i18nStore.t('frontend.subscriptions.service') }}</th>
              <th>{{ i18nStore.t('frontend.subscriptions.plan') }}</th>
              <th>{{ i18nStore.t('frontend.subscriptions.email') }}</th>
              <th>{{ i18nStore.t('frontend.subscriptions.password') }}</th>
              <th>{{ i18nStore.t('frontend.subscriptions.pin') }}</th>
              <th>{{ i18nStore.t('frontend.subscriptions.status') }}</th>
              <th>{{ i18nStore.t('frontend.subscriptions.start') }}</th>
              <th>{{ i18nStore.t('frontend.subscriptions.end') }}</th>
              <th>{{ i18nStore.t('frontend.subscriptions.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="sub in subscriptions" :key="sub.id">
              <td>{{ getClientName(sub.client_id) }}</td>
              <td>{{ getServiceName(sub.service_id) }}</td>
              <td>{{ getPlanName(sub.plan_id) }}</td>
              <td>{{ sub.streaming_email || '—' }}</td>
              <td class="credential-cell">
                <template v-if="sub.has_password">
                  <span class="credential-value">
                    <template v-if="revealedRowId === sub.id && revealedCredentials[sub.id]">
                      {{ revealedCredentials[sub.id].streaming_password }}
                    </template>
                    <template v-else>******</template>
                  </span>
                  <button class="button button-sm reveal-btn" type="button" @click="revealCredentials(sub.id)" :title="revealedRowId === sub.id ? i18nStore.t('frontend.subscriptions.hide') : i18nStore.t('frontend.subscriptions.reveal')">
                    👁️
                  </button>
                </template>
                <span v-else class="no-credential">{{ i18nStore.t('frontend.subscriptions.no_password') }}</span>
              </td>
              <td class="credential-cell">
                <template v-if="sub.has_pin && sub.profile_name">
                  <span class="credential-value">
                    <template v-if="revealedRowId === sub.id && revealedCredentials[sub.id]">
                      {{ revealedCredentials[sub.id].profile_pin }}
                    </template>
                    <template v-else>******</template>
                  </span>
                </template>
                <span v-else>—</span>
              </td>
              <td>
                <span class="status-badge" :class="getStatusClass(sub.status)">
                  {{ getStatusLabel(sub.status) }}
                </span>
              </td>
              <td>{{ formatDate(sub.starts_at) }}</td>
              <td>{{ formatDate(sub.expires_at) }}</td>
              <td class="actions-cell">
                <button class="button button-sm" type="button" @click="openEditModal(sub)" :title="i18nStore.t('frontend.subscriptions.edit_title')">✏️</button>
                <button v-if="sub.status === 'active'" class="button button-sm" type="button" @click="openRenewModal(sub)" :title="i18nStore.t('frontend.subscriptions.renew_title')">🔄</button>
                <button v-if="sub.status === 'cancelled'" class="button button-sm" type="button" @click="openReactivateModal(sub)" :title="i18nStore.t('frontend.subscriptions.reactivate_title')">▶️</button>
                <button v-if="sub.status === 'active'" class="button button-sm button-danger" type="button" @click="confirmCancel(sub)" :title="i18nStore.t('frontend.subscriptions.cancel_title')">✕</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Create/Edit Modal -->
    <div v-if="showCreateModal || showEditModal" class="modal-overlay" @click.self="closeModals">
      <div class="modal">
        <div class="modal-header">
          <h2>{{ showEditModal ? i18nStore.t('frontend.subscriptions.edit_title') : i18nStore.t('frontend.subscriptions.new_title') }}</h2>
          <button class="modal-close" type="button" @click="closeModals">✕</button>
        </div>
        <div class="modal-body">
          <label>
            {{ i18nStore.t('frontend.subscriptions.client') }}
            <select v-model="formData.client_id" required>
              <option value="">{{ i18nStore.t('frontend.subscriptions.select_client') }}</option>
              <option v-for="client in clients" :key="client.id" :value="client.id">{{ client.full_name }}</option>
            </select>
          </label>
          <label>
            {{ i18nStore.t('frontend.subscriptions.service') }}
            <select v-model="formData.service_id" required>
              <option value="">{{ i18nStore.t('frontend.subscriptions.select_service') }}</option>
              <option v-for="service in services" :key="service.id" :value="service.id">{{ service.name }}</option>
            </select>
          </label>
          <label>
            {{ i18nStore.t('frontend.subscriptions.plan') }}
            <select v-model="formData.plan_id" required :disabled="!availablePlans.length">
              <option value="">{{ i18nStore.t('frontend.subscriptions.select_plan') }}</option>
              <option v-for="plan in availablePlans" :key="plan.id" :value="plan.id">{{ plan.name }}</option>
            </select>
          </label>
          <label>
            {{ i18nStore.t('frontend.subscriptions.email') }}
            <input v-model="formData.streaming_email" type="email" :placeholder="i18nStore.t('frontend.subscriptions.placeholder_email')" required />
          </label>
          <label>
            {{ i18nStore.t('frontend.subscriptions.streaming_password') }}
            <div class="password-wrapper">
              <input :type="showPassword ? 'text' : 'password'" v-model="formData.streaming_password" placeholder="••••••••" />
              <button class="toggle-password" type="button" @click="showPassword = !showPassword">
                {{ showPassword ? '🙈' : '👁️' }}
              </button>
            </div>
          </label>
          <label>
            {{ i18nStore.t('frontend.subscriptions.start_date') }}
            <input v-model="formData.starts_at" type="date" />
          </label>
          <label>
            {{ i18nStore.t('frontend.subscriptions.duration') }}
            <select v-model="formData.duration_type">
              <option value="">{{ i18nStore.t('frontend.subscriptions.select_duration') }}</option>
              <option v-for="opt in durationOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
          <label v-if="isCustomDuration">
            {{ i18nStore.t('frontend.subscriptions.end_date') }}
            <input v-model="formData.expires_at" type="date" />
          </label>
          <div class="profile-toggle">
            <button class="button button-sm" type="button" @click="showProfile = !showProfile">
              {{ showProfile ? '−' : '+' }} {{ i18nStore.t('frontend.subscriptions.add_profile') }}
            </button>
          </div>
          <template v-if="showProfile">
            <label>
              {{ i18nStore.t('frontend.subscriptions.profile_name') }}
              <input v-model="formData.profile_name" :placeholder="i18nStore.t('frontend.subscriptions.placeholder_profile_name')" />
            </label>
            <label>
              {{ i18nStore.t('frontend.subscriptions.pin') }}
              <input v-model="formData.profile_pin" type="text" inputmode="numeric" placeholder="1234" :disabled="!formData.profile_name" />
            </label>
          </template>
        </div>
        <div class="modal-footer">
          <button class="button button-secondary" type="button" @click="closeModals">{{ i18nStore.t('frontend.subscriptions.cancel_action') }}</button>
          <button class="button button-primary" type="button" @click="saveSubscription" :disabled="isSaving || !formData.client_id || !formData.service_id || !formData.plan_id || !formData.streaming_email || !formData.duration_type">
            {{ isSaving ? i18nStore.t('frontend.subscriptions.saving') : i18nStore.t('frontend.subscriptions.save') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Renew Modal -->
    <div v-if="showRenewModal" class="modal-overlay" @click.self="closeModals">
      <div class="modal">
        <div class="modal-header">
          <h2>{{ i18nStore.t('frontend.subscriptions.renew_title') }}</h2>
          <button class="modal-close" type="button" @click="closeModals">✕</button>
        </div>
        <div class="modal-body">
          <label>
            {{ i18nStore.t('frontend.subscriptions.duration') }}
            <select v-model="renewForm.duration_type">
              <option value="">{{ i18nStore.t('frontend.subscriptions.select_duration') }}</option>
              <option v-for="opt in durationOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
          <label v-if="isRenewCustomDuration">
            {{ i18nStore.t('frontend.subscriptions.end_date') }}
            <input v-model="renewForm.expires_at" type="date" />
          </label>
        </div>
        <div class="modal-footer">
          <button class="button button-secondary" type="button" @click="closeModals">{{ i18nStore.t('frontend.subscriptions.cancel_action') }}</button>
          <button class="button button-primary" type="button" @click="doRenew" :disabled="isSaving || !renewForm.duration_type || (isRenewCustomDuration && !renewForm.expires_at)">
            {{ isSaving ? i18nStore.t('frontend.subscriptions.renewing') : i18nStore.t('frontend.subscriptions.renew') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Reactivate Modal -->
    <div v-if="showReactivateModal" class="modal-overlay" @click.self="closeModals">
      <div class="modal">
        <div class="modal-header">
          <h2>{{ i18nStore.t('frontend.subscriptions.reactivate_title') }}</h2>
          <button class="modal-close" type="button" @click="closeModals">✕</button>
        </div>
        <div class="modal-body">
          <label>
            {{ i18nStore.t('frontend.subscriptions.duration') }}
            <select v-model="reactivateForm.duration_type">
              <option value="">{{ i18nStore.t('frontend.subscriptions.select_duration') }}</option>
              <option v-for="opt in durationOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
          <label>
            {{ i18nStore.t('frontend.subscriptions.start_date') }} {{ i18nStore.t('frontend.subscriptions.optional') }}
            <input v-model="reactivateForm.starts_at" type="date" />
          </label>
          <label v-if="isReactivateCustomDuration">
            {{ i18nStore.t('frontend.subscriptions.end_date') }}
            <input v-model="reactivateForm.expires_at" type="date" />
          </label>
        </div>
        <div class="modal-footer">
          <button class="button button-secondary" type="button" @click="closeModals">{{ i18nStore.t('frontend.subscriptions.cancel_action') }}</button>
          <button class="button button-primary" type="button" @click="doReactivate" :disabled="isSaving || !reactivateForm.duration_type || (isReactivateCustomDuration && !reactivateForm.expires_at)">
            {{ isSaving ? i18nStore.t('frontend.subscriptions.reactivating') : i18nStore.t('frontend.subscriptions.reactivate') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Cancel Confirm Dialog -->
    <div v-if="showCancelConfirm" class="modal-overlay" @click.self="closeModals">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h2>{{ i18nStore.t('frontend.subscriptions.cancel_title') }}</h2>
          <button class="modal-close" type="button" @click="closeModals">✕</button>
        </div>
        <div class="modal-body">
          <p>{{ i18nStore.t('frontend.subscriptions.cancel_confirm') }}</p>
          <label>
            {{ i18nStore.t('frontend.subscriptions.cancel_notes') }}
            <textarea v-model="cancelNotes" rows="3" :placeholder="i18nStore.t('frontend.subscriptions.placeholder_cancel_reason')"></textarea>
          </label>
        </div>
        <div class="modal-footer">
          <button class="button button-secondary" type="button" @click="closeModals">{{ i18nStore.t('frontend.subscriptions.back_btn') }}</button>
          <button class="button button-primary" type="button" style="background:var(--danger)" @click="doCancel" :disabled="isSaving">
            {{ isSaving ? i18nStore.t('frontend.subscriptions.cancelling') : i18nStore.t('frontend.subscriptions.yes_cancel') }}
          </button>
        </div>
      </div>
    </div>

    <ReminderSettingsModal
      :show="showReminderSettings"
      :initial-settings="reminderSettings"
      @close="closeModals"
      @saved="loadSubscriptions"
    />
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
.empty-state {
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

.filters-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: 18px;
}

label {
  display: grid;
  gap: 8px;
  color: var(--text-secondary);
  font-weight: 700;
}

input,
select {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 11px 12px;
  color: var(--text);
  font: inherit;
  background: var(--card-bg);
}

input:focus,
select:focus {
  border-color: var(--primary);
  outline: 3px solid rgb(79 70 229 / 15%);
}

.quick-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-label {
  color: var(--text-secondary);
  font-size: 0.85rem;
  font-weight: 700;
}

.button {
  cursor: pointer;
  border: 0;
  border-radius: 10px;
  padding: 10px 16px;
  font: inherit;
  font-weight: 700;
}

.button-sm {
  padding: 6px 12px;
  font-size: 0.85rem;
  border: 1px solid var(--border);
  background: var(--card-bg);
  color: var(--text);
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

.form-actions {
  grid-column: 1 / -1;
  justify-content: flex-end;
  margin-top: 16px;
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

.empty-state {
  justify-content: center;
  gap: 12px;
  padding: 40px 0;
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

.status-active {
  background: #dcfce7;
  color: #166534;
}

.status-expired {
  background: #fef3c7;
  color: #92400e;
}

.status-cancelled {
  background: #fee2e2;
  color: #991b1b;
}

.section-header {
  margin-bottom: 0;
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(15, 23, 42, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--card-bg);
  border-radius: 16px;
  width: 90%;
  max-width: 520px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 25px 50px rgba(15, 23, 42, 0.25);
}

.modal-sm {
  max-width: 420px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 24px 0;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
}

.modal-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.25rem;
  color: var(--text-secondary);
  padding: 4px 8px;
  border-radius: 8px;
}

.modal-close:hover {
  background: var(--border);
}

.modal-body {
  padding: 24px;
  display: grid;
  gap: 16px;
}

.modal-body textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 11px 12px;
  color: var(--text);
  font: inherit;
  background: var(--card-bg);
  resize: vertical;
}

.modal-body textarea:focus {
  border-color: var(--primary);
  outline: 3px solid rgb(79 70 229 / 15%);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 0 24px 24px;
}

.password-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.password-wrapper input {
  flex: 1;
}

.toggle-password {
  background: none;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
  cursor: pointer;
  font-size: 1rem;
}

.profile-toggle {
  padding-top: 8px;
}

.actions-cell {
  display: flex;
  gap: 6px;
  align-items: center;
}

.button-danger {
  border-color: var(--danger);
  color: var(--danger);
}

.button-danger:hover {
  background: rgb(239 68 68 / 10%);
}

/* Credential reveal */
.credential-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.credential-value {
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 0.9rem;
}

.no-credential {
  color: var(--text-secondary);
  font-style: italic;
}

.reveal-btn {
  cursor: pointer;
  font-size: 1rem;
  padding: 2px 6px;
  line-height: 1;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--card-bg);
  transition: background 0.15s;
}

.reveal-btn:hover {
  background: #f1f5f9;
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

  .filters-grid {
    grid-template-columns: 1fr;
  }

  .form-actions {
    justify-content: stretch;
  }

  .button {
    width: 100%;
  }

  .modal {
    width: 95%;
    max-width: 100%;
  }
}
</style>
