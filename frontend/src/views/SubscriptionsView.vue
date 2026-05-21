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
              <th>Estado</th>
              <th>Inicio</th>
              <th>Vencimiento</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="sub in subscriptions" :key="sub.id">
              <td>{{ getClientName(sub.client_id) }}</td>
              <td>{{ getServiceName(sub.service_id) }}</td>
              <td>{{ getPlanName(sub.plan_id) }}</td>
              <td>{{ sub.streaming_email || '—' }}</td>
              <td>
                <span class="status-badge" :class="getStatusClass(sub.status)">
                  {{ getStatusLabel(sub.status) }}
                </span>
              </td>
              <td>{{ formatDate(sub.starts_at) }}</td>
              <td>{{ formatDate(sub.expires_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
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
}
</style>
