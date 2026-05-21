<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

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
const availablePlans = ref([])

// Form data
const formData = ref({
  client_id: '',
  service_id: '',
  plan_id: '',
  streaming_email: '',
  streaming_password: '',
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

const durationOptions = [
  { value: '1_month', label: '1 mes' },
  { value: '3_months', label: '3 meses' },
  { value: '6_months', label: '6 meses' },
  { value: '9_months', label: '9 meses' },
  { value: '1_year', label: '1 año' },
  { value: 'custom', label: 'Personalizado' },
]

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
    case 'active': return 'Activa'
    case 'expired': return 'Expirada'
    case 'cancelled': return 'Cancelada'
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
    errorMessage.value = getApiError(error, 'No se pudieron cargar las suscripciones.')
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
    errorMessage.value = getApiError(error, 'No se pudo cancelar la suscripción.')
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
    errorMessage.value = getApiError(error, 'No se pudo guardar la suscripción.')
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
    errorMessage.value = getApiError(error, 'No se pudo renovar la suscripción.')
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
    errorMessage.value = getApiError(error, 'No se pudo reactivar la suscripción.')
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
    errorMessage.value = getApiError(error, 'No se pudieron revelar las credenciales.')
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

// --- Reminder settings ---
const showReminderSettings = ref(false)
const reminderSettings = ref({
  timezone: 'UTC',
  warning_days: [7, 3, 1],
  reminder_time: '09:00',
  recipient_mode: 'tenant_only',
})
const reminderCustomDay = ref('')

const recipientModeOptions = [
  { value: 'tenant_only', label: 'Solo el tenant' },
  { value: 'client_only', label: 'Solo el cliente' },
  { value: 'both', label: 'Tenant y cliente' },
]

const timezoneOptions = [
  { value: 'UTC', label: 'UTC' },
  { value: 'America/Mexico_City', label: 'America/Mexico_City' },
  { value: 'America/Argentina/Buenos_Aires', label: 'America/Argentina/Buenos_Aires' },
  { value: 'America/Santiago', label: 'America/Santiago' },
  { value: 'America/Bogota', label: 'America/Bogota' },
  { value: 'America/Lima', label: 'America/Lima' },
  { value: 'America/Sao_Paulo', label: 'America/Sao_Paulo' },
  { value: 'America/New_York', label: 'America/New_York' },
  { value: 'America/Chicago', label: 'America/Chicago' },
  { value: 'America/Denver', label: 'America/Denver' },
  { value: 'America/Los_Angeles', label: 'America/Los_Angeles' },
  { value: 'Europe/Madrid', label: 'Europe/Madrid' },
  { value: 'Europe/London', label: 'Europe/London' },
  { value: 'Europe/Paris', label: 'Europe/Paris' },
  { value: 'Europe/Berlin', label: 'Europe/Berlin' },
]

async function loadReminderSettings() {
  try {
    const response = await api.get('/subscription-settings')
    if (response.data) {
      reminderSettings.value = {
        timezone: response.data.timezone || 'UTC',
        warning_days: response.data.warning_days || [7, 3, 1],
        reminder_time: response.data.reminder_time || '09:00',
        recipient_mode: response.data.recipient_mode || 'tenant_only',
      }
    }
  } catch (error) {
    // Use defaults
  }
}

async function saveReminderSettings() {
  isSaving.value = true
  try {
    await api.put('/subscription-settings', reminderSettings.value)
    showReminderSettings.value = false
  } catch (error) {
    errorMessage.value = getApiError(error, 'No se pudieron guardar los ajustes de recordatorios.')
  } finally {
    isSaving.value = false
  }
}

function openReminderSettings() {
  loadReminderSettings()
  showReminderSettings.value = true
}

function toggleWarningDay(day) {
  const idx = reminderSettings.value.warning_days.indexOf(day)
  if (idx >= 0) {
    reminderSettings.value.warning_days.splice(idx, 1)
  } else {
    reminderSettings.value.warning_days.push(day)
    reminderSettings.value.warning_days.sort((a, b) => a - b)
  }
}

function addCustomWarningDay() {
  const day = parseInt(reminderCustomDay.value, 10)
  if (!isNaN(day) && day > 0 && !reminderSettings.value.warning_days.includes(day)) {
    reminderSettings.value.warning_days.push(day)
    reminderSettings.value.warning_days.sort((a, b) => a - b)
    reminderCustomDay.value = ''
  }
}

function removeWarningDay(day) {
  const idx = reminderSettings.value.warning_days.indexOf(day)
  if (idx >= 0) {
    reminderSettings.value.warning_days.splice(idx, 1)
  }
}

onMounted(init)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <p class="eyebrow">Trackpal</p>
        <h1>Suscripciones</h1>
      </div>

      <div class="user-actions">
        <span class="username">{{ username }}</span>
        <button class="button button-primary" type="button" @click="openCreateModal">Nueva suscripción</button>
        <button class="button button-secondary" type="button" @click="openReminderSettings">Configurar recordatorios</button>
        <button class="button button-secondary" type="button" @click="goBack">Volver al dashboard</button>
        <button class="button button-secondary" type="button" @click="authStore.logout(); router.push('/login')">Cerrar sesión</button>
      </div>
    </header>

    <section class="content-card filters-card">
      <div class="section-header">
        <div>
          <p class="eyebrow">Filtros</p>
          <h2>Buscar suscripciones</h2>
        </div>
        <button class="button button-secondary" type="button" @click="clearFilters">Limpiar filtros</button>
      </div>

      <div class="filters-grid">
        <label>
          Estado
          <select v-model="filters.status">
            <option value="">Todos los activos</option>
            <option value="active">Activa</option>
            <option value="expired">Expirada</option>
            <option value="cancelled">Cancelada</option>
          </select>
        </label>

        <label>
          Cliente
          <select v-model="filters.client_id">
            <option value="">Todos los clientes</option>
            <option v-for="client in clients" :key="client.id" :value="client.id">
              {{ client.full_name }}
            </option>
          </select>
        </label>

        <label>
          Servicio
          <select v-model="filters.service_id">
            <option value="">Todos los servicios</option>
            <option v-for="service in services" :key="service.id" :value="service.id">
              {{ service.name }}
            </option>
          </select>
        </label>

        <div class="quick-filters">
          <span class="filter-label">Vencimiento rápido:</span>
          <button class="button button-sm" type="button" @click="setQuickFilter('this_week')">Esta semana</button>
          <button class="button button-sm" type="button" @click="setQuickFilter('this_month')">Este mes</button>
          <button class="button button-sm" type="button" @click="setQuickFilter('expired')">Vencidas</button>
        </div>

        <label>
          Desde
          <input v-model="filters.expires_from" type="date" />
        </label>

        <label>
          Hasta
          <input v-model="filters.expires_to" type="date" />
        </label>
      </div>

      <div class="form-actions">
        <button class="button button-primary" type="button" @click="loadSubscriptions">Aplicar filtros</button>
      </div>
    </section>

    <section class="content-card subscriptions-card">
      <div class="section-header">
        <div>
          <p class="eyebrow">Resultados</p>
          <h2>Suscripciones {{ subscriptions.length ? `(${subscriptions.length})` : '' }}</h2>
        </div>
      </div>

      <p v-if="errorMessage" class="alert alert-error">{{ errorMessage }}</p>

      <div v-if="isLoading" class="empty-state">
        <span class="spinner" aria-hidden="true"></span>
        <p>Cargando suscripciones...</p>
      </div>

      <div v-else-if="!subscriptions.length" class="empty-state">
        <p>No hay suscripciones que coincidan con los filtros.</p>
      </div>

      <div v-else class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Cliente</th>
              <th>Servicio</th>
              <th>Plan</th>
              <th>Email streaming</th>
              <th>Contraseña</th>
              <th>PIN</th>
              <th>Estado</th>
              <th>Inicio</th>
              <th>Vencimiento</th>
              <th>Acciones</th>
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
                  <button class="button button-sm reveal-btn" type="button" @click="revealCredentials(sub.id)" :title="revealedRowId === sub.id ? 'Ocultar' : 'Revelar'">
                    👁️
                  </button>
                </template>
                <span v-else class="no-credential">Sin contraseña</span>
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
                <button class="button button-sm" type="button" @click="openEditModal(sub)" title="Editar">✏️</button>
                <button v-if="sub.status === 'active'" class="button button-sm" type="button" @click="openRenewModal(sub)" title="Renovar">🔄</button>
                <button v-if="sub.status === 'cancelled'" class="button button-sm" type="button" @click="openReactivateModal(sub)" title="Reactivar">▶️</button>
                <button v-if="sub.status === 'active'" class="button button-sm button-danger" type="button" @click="confirmCancel(sub)" title="Cancelar">✕</button>
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
          <h2>{{ showEditModal ? 'Editar suscripción' : 'Nueva suscripción' }}</h2>
          <button class="modal-close" type="button" @click="closeModals">✕</button>
        </div>
        <div class="modal-body">
          <label>
            Cliente
            <select v-model="formData.client_id" required>
              <option value="">Seleccionar cliente</option>
              <option v-for="client in clients" :key="client.id" :value="client.id">{{ client.full_name }}</option>
            </select>
          </label>
          <label>
            Servicio
            <select v-model="formData.service_id" required>
              <option value="">Seleccionar servicio</option>
              <option v-for="service in services" :key="service.id" :value="service.id">{{ service.name }}</option>
            </select>
          </label>
          <label>
            Plan
            <select v-model="formData.plan_id" required :disabled="!availablePlans.length">
              <option value="">Seleccionar plan</option>
              <option v-for="plan in availablePlans" :key="plan.id" :value="plan.id">{{ plan.name }}</option>
            </select>
          </label>
          <label>
            Email streaming
            <input v-model="formData.streaming_email" type="email" placeholder="email@ejemplo.com" required />
          </label>
          <label>
            Contraseña streaming
            <div class="password-wrapper">
              <input :type="showPassword ? 'text' : 'password'" v-model="formData.streaming_password" placeholder="••••••••" />
              <button class="toggle-password" type="button" @click="showPassword = !showPassword">
                {{ showPassword ? '🙈' : '👁️' }}
              </button>
            </div>
          </label>
          <label>
            Duración
            <select v-model="formData.duration_type">
              <option value="">Seleccionar duración</option>
              <option v-for="opt in durationOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
          <label v-if="isCustomDuration">
            Fecha de vencimiento
            <input v-model="formData.expires_at" type="date" />
          </label>
          <div class="profile-toggle">
            <button class="button button-sm" type="button" @click="showProfile = !showProfile">
              {{ showProfile ? '−' : '+' }} Añadir perfil y PIN
            </button>
          </div>
          <template v-if="showProfile">
            <label>
              Nombre de perfil
              <input v-model="formData.profile_name" placeholder="Ej: Perfil 1" />
            </label>
            <label>
              PIN
              <input v-model="formData.profile_pin" type="text" inputmode="numeric" placeholder="1234" :disabled="!formData.profile_name" />
            </label>
          </template>
        </div>
        <div class="modal-footer">
          <button class="button button-secondary" type="button" @click="closeModals">Cancelar</button>
          <button class="button button-primary" type="button" @click="saveSubscription" :disabled="isSaving || !formData.client_id || !formData.service_id || !formData.plan_id || !formData.streaming_email || !formData.duration_type">
            {{ isSaving ? 'Guardando...' : 'Guardar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Renew Modal -->
    <div v-if="showRenewModal" class="modal-overlay" @click.self="closeModals">
      <div class="modal">
        <div class="modal-header">
          <h2>Renovar suscripción</h2>
          <button class="modal-close" type="button" @click="closeModals">✕</button>
        </div>
        <div class="modal-body">
          <label>
            Duración
            <select v-model="renewForm.duration_type">
              <option value="">Seleccionar duración</option>
              <option v-for="opt in durationOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
          <label v-if="isRenewCustomDuration">
            Fecha de vencimiento
            <input v-model="renewForm.expires_at" type="date" />
          </label>
        </div>
        <div class="modal-footer">
          <button class="button button-secondary" type="button" @click="closeModals">Cancelar</button>
          <button class="button button-primary" type="button" @click="doRenew" :disabled="isSaving || !renewForm.duration_type || (isRenewCustomDuration && !renewForm.expires_at)">
            {{ isSaving ? 'Renovando...' : 'Renovar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Reactivate Modal -->
    <div v-if="showReactivateModal" class="modal-overlay" @click.self="closeModals">
      <div class="modal">
        <div class="modal-header">
          <h2>Reactivar suscripción</h2>
          <button class="modal-close" type="button" @click="closeModals">✕</button>
        </div>
        <div class="modal-body">
          <label>
            Duración
            <select v-model="reactivateForm.duration_type">
              <option value="">Seleccionar duración</option>
              <option v-for="opt in durationOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
          <label>
            Fecha de inicio (opcional)
            <input v-model="reactivateForm.starts_at" type="date" />
          </label>
          <label v-if="isReactivateCustomDuration">
            Fecha de vencimiento
            <input v-model="reactivateForm.expires_at" type="date" />
          </label>
        </div>
        <div class="modal-footer">
          <button class="button button-secondary" type="button" @click="closeModals">Cancelar</button>
          <button class="button button-primary" type="button" @click="doReactivate" :disabled="isSaving || !reactivateForm.duration_type || (isReactivateCustomDuration && !reactivateForm.expires_at)">
            {{ isSaving ? 'Reactivando...' : 'Reactivar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Cancel Confirm Dialog -->
    <div v-if="showCancelConfirm" class="modal-overlay" @click.self="closeModals">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h2>Cancelar suscripción</h2>
          <button class="modal-close" type="button" @click="closeModals">✕</button>
        </div>
        <div class="modal-body">
          <p>¿Estás seguro de que deseas cancelar esta suscripción?</p>
          <label>
            Notas (opcional)
            <textarea v-model="cancelNotes" rows="3" placeholder="Motivo de la cancelación..."></textarea>
          </label>
        </div>
        <div class="modal-footer">
          <button class="button button-secondary" type="button" @click="closeModals">Volver</button>
          <button class="button button-primary" type="button" style="background:var(--danger)" @click="doCancel" :disabled="isSaving">
            {{ isSaving ? 'Cancelando...' : 'Sí, cancelar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Reminder Settings Modal -->
    <div v-if="showReminderSettings" class="modal-overlay" @click.self="closeModals">
      <div class="modal">
        <div class="modal-header">
          <h2>Configurar recordatorios</h2>
          <button class="modal-close" type="button" @click="closeModals">✕</button>
        </div>
        <div class="modal-body">
          <label>
            Zona horaria
            <select v-model="reminderSettings.timezone">
              <option v-for="tz in timezoneOptions" :key="tz.value" :value="tz.value">{{ tz.label }}</option>
            </select>
          </label>

          <label>
            Días de aviso
            <div class="warning-days-container">
              <label class="day-check" v-for="day in [7, 3, 1]" :key="day">
                <input type="checkbox" :checked="reminderSettings.warning_days.includes(day)" @change="toggleWarningDay(day)" />
                {{ day }} día{{ day > 1 ? 's' : '' }}
              </label>
              <div class="custom-day-input">
                <input v-model="reminderCustomDay" type="number" min="1" placeholder="Personalizado" @keyup.enter="addCustomWarningDay" />
                <button class="button button-sm" type="button" @click="addCustomWarningDay" :disabled="!reminderCustomDay">+</button>
              </div>
            </div>
            <div v-if="reminderSettings.warning_days.length" class="warning-days-tags">
              <span class="tag" v-for="day in reminderSettings.warning_days" :key="day">
                {{ day }} día{{ day > 1 ? 's' : '' }}
                <button class="tag-remove" type="button" @click="removeWarningDay(day)">✕</button>
              </span>
            </div>
          </label>

          <label>
            Hora de recordatorio
            <input v-model="reminderSettings.reminder_time" type="time" />
          </label>

          <label>
            Destinatario
            <select v-model="reminderSettings.recipient_mode">
              <option v-for="opt in recipientModeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
        </div>
        <div class="modal-footer">
          <button class="button button-secondary" type="button" @click="closeModals">Cancelar</button>
          <button class="button button-primary" type="button" @click="saveReminderSettings" :disabled="isSaving">
            {{ isSaving ? 'Guardando...' : 'Guardar' }}
          </button>
        </div>
      </div>
    </div>
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

/* Reminder settings – warning days */
.warning-days-container {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.day-check {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 400;
  color: var(--text);
  cursor: pointer;
}

.day-check input[type="checkbox"] {
  width: auto;
  cursor: pointer;
}

.custom-day-input {
  display: flex;
  gap: 4px;
  align-items: center;
}

.custom-day-input input {
  width: 120px;
  padding: 6px 8px;
}

.custom-day-input .button-sm {
  padding: 6px 10px;
}

.warning-days-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: var(--primary);
  font-size: 0.85rem;
  font-weight: 600;
}

.tag-remove {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.75rem;
  color: var(--primary);
  padding: 0 2px;
  line-height: 1;
}

.tag-remove:hover {
  color: var(--danger);
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
