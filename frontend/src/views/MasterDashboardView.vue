<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const tenants = ref([])
const meta = ref({ total: 0, active: 0, inactive: 0 })
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const modalError = ref('')
const isModalOpen = ref(false)
const modalMode = ref('create')
const form = ref(getEmptyForm())

const isEditMode = computed(() => modalMode.value === 'edit')
const modalTitle = computed(() => (isEditMode.value ? 'Edit Tenant' : 'Create Tenant'))
const modalPrefixHint = computed(() => (
  isEditMode.value
    ? 'Changing this prefix will update all client login usernames for the tenant.'
    : 'Leave blank to auto-generate a unique prefix.'
))
const username = computed(() => authStore.username || authStore.user?.username || 'Master')

function getEmptyForm() {
  return {
    id: null,
    full_name: '',
    email: '',
    phone: '',
    client_prefix: '',
    username: '',
    password: '',
    evolution_instance_name: '',
  }
}

function getApiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  }
  return detail || error.response?.data?.message || fallback
}

function isTenantActive(tenant) {
  if (typeof tenant.is_active === 'boolean') return tenant.is_active
  if (typeof tenant.active === 'boolean') return tenant.active
  return tenant.status === 'active' || tenant.status === 'Active'
}

function getGeneratedPassword(data) {
  return data?.generated_password || data?.password || data?.temporary_password || data?.plain_password || ''
}

async function loadTenants() {
  errorMessage.value = ''
  isLoading.value = true

  try {
    const response = await api.get('/tenants')
    tenants.value = response.data?.data || []
    meta.value = response.data?.meta || {
      total: tenants.value.length,
      active: tenants.value.filter((tenant) => isTenantActive(tenant)).length,
      inactive: tenants.value.filter((tenant) => !isTenantActive(tenant)).length,
    }
  } catch (error) {
    errorMessage.value = getApiError(error, 'Unable to load tenants')
  } finally {
    isLoading.value = false
  }
}

function openCreateModal() {
  clearMessages()
  modalMode.value = 'create'
  form.value = getEmptyForm()
  isModalOpen.value = true
}

function openEditModal(tenant) {
  clearMessages()
  modalMode.value = 'edit'
  form.value = {
    ...getEmptyForm(),
    id: tenant.id,
    full_name: tenant.full_name || '',
    email: tenant.email || '',
    phone: tenant.phone || '',
    client_prefix: tenant.client_prefix || '',
    evolution_instance_name: tenant.evolution_instance_name || '',
  }
  isModalOpen.value = true
}

function closeModal() {
  if (isSaving.value) return
  isModalOpen.value = false
  modalError.value = ''
}

function clearMessages() {
  errorMessage.value = ''
  successMessage.value = ''
  modalError.value = ''
}

function validateForm() {
  if (!form.value.full_name || !form.value.email || !form.value.phone) {
    modalError.value = 'Full name, email, and phone are required.'
    return false
  }

  if (!isEditMode.value && !form.value.username) {
    modalError.value = 'Username is required.'
    return false
  }

  if (!form.value.evolution_instance_name) {
    modalError.value = 'Evolution instance name is required.'
    return false
  }

  return true
}

async function handleSubmit() {
  modalError.value = ''
  successMessage.value = ''

  if (!validateForm()) return

  isSaving.value = true

  try {
    if (isEditMode.value) {
      const payload = {
        full_name: form.value.full_name,
        email: form.value.email,
        phone: form.value.phone,
        evolution_instance_name: form.value.evolution_instance_name,
      }
      if (form.value.client_prefix?.trim()) {
        payload.client_prefix = form.value.client_prefix
      }
      await api.put(`/tenants/${form.value.id}`, payload)
      successMessage.value = 'Tenant updated successfully.'
    } else {
      const payload = {
        full_name: form.value.full_name,
        email: form.value.email,
        phone: form.value.phone,
        username: form.value.username,
        evolution_instance_name: form.value.evolution_instance_name,
      }

      if (form.value.client_prefix?.trim()) {
        payload.client_prefix = form.value.client_prefix
      }

      if (form.value.password) {
        payload.password = form.value.password
      }

      const response = await api.post('/tenants', payload)
      const generatedPassword = getGeneratedPassword(response.data)
      successMessage.value = generatedPassword
        ? `Tenant created successfully. Generated password: ${generatedPassword}`
        : 'Tenant created successfully.'
    }

    isModalOpen.value = false
    await loadTenants()
  } catch (error) {
    modalError.value = getApiError(error, 'Unable to save tenant')
  } finally {
    isSaving.value = false
  }
}

async function toggleTenantStatus(tenant) {
  clearMessages()
  const active = isTenantActive(tenant)
  const endpoint = active ? `/tenants/${tenant.id}/deactivate` : `/tenants/${tenant.id}/activate`

  try {
    await api.patch(endpoint)
    successMessage.value = active ? 'Tenant deactivated successfully.' : 'Tenant activated successfully.'
    await loadTenants()
  } catch (error) {
    errorMessage.value = getApiError(error, 'Unable to update tenant status')
  }
}

async function deleteTenant(tenant) {
  clearMessages()

  if (isTenantActive(tenant)) {
    errorMessage.value = 'Cannot delete active tenant. Deactivate first.'
    return
  }

  if (!window.confirm(`Delete tenant ${tenant.full_name}? This action cannot be undone.`)) {
    return
  }

  try {
    await api.delete(`/tenants/${tenant.id}`)
    successMessage.value = 'Tenant deleted successfully.'
    await loadTenants()
  } catch (error) {
    errorMessage.value = getApiError(error, 'Unable to delete tenant')
  }
}

async function manageCatalog(tenant) {
  clearMessages()
  try {
    await authStore.switchTenant(tenant.id)
    await router.push('/admin/dashboard')
  } catch (error) {
    errorMessage.value = getApiError(error, 'Unable to switch tenant context')
  }
}

async function handleLogout() {
  await authStore.logout()
  await router.push('/login')
}

onMounted(loadTenants)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <p class="eyebrow">Master Dashboard</p>
        <h1>Trackpal</h1>
      </div>

      <div class="user-actions">
        <span class="username">{{ username }}</span>
        <button class="button button-secondary" type="button" @click="handleLogout">Logout</button>
      </div>
    </header>

    <section class="summary-grid" aria-label="Tenant summary">
      <article class="summary-card">
        <span>Total Tenants</span>
        <strong>{{ meta.total }}</strong>
      </article>
      <article class="summary-card">
        <span>Active</span>
        <strong>{{ meta.active }}</strong>
      </article>
      <article class="summary-card">
        <span>Inactive</span>
        <strong>{{ meta.inactive }}</strong>
      </article>
    </section>

    <section class="content-card">
      <div class="section-header">
        <div>
          <h2>Tenants</h2>
          <p>Manage tenant accounts and Evolution instances.</p>
        </div>
        <button class="button button-primary" type="button" @click="openCreateModal">Create Tenant</button>
      </div>

      <p v-if="errorMessage" class="alert alert-error">{{ errorMessage }}</p>
      <p v-if="successMessage" class="alert alert-success">{{ successMessage }}</p>

      <div v-if="isLoading" class="empty-state">Loading tenants...</div>
      <div v-else-if="!tenants.length" class="empty-state">No tenants registered yet</div>
      <div v-else class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Full Name</th>
              <th>Client Prefix</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Evolution Instance</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tenant in tenants" :key="tenant.id">
              <td>{{ tenant.full_name }}</td>
              <td>{{ tenant.client_prefix || '—' }}</td>
              <td>{{ tenant.email }}</td>
              <td>{{ tenant.phone }}</td>
              <td>{{ tenant.evolution_instance_name || '—' }}</td>
              <td>
                <span class="status-badge" :class="isTenantActive(tenant) ? 'active' : 'inactive'">
                  {{ isTenantActive(tenant) ? 'Active' : 'Inactive' }}
                </span>
              </td>
              <td>
                <div class="row-actions">
                  <button class="link-button" type="button" @click="openEditModal(tenant)">Edit</button>
                  <button class="link-button" type="button" @click="manageCatalog(tenant)">Manage catalog</button>
                  <button class="link-button" type="button" @click="toggleTenantStatus(tenant)">
                    {{ isTenantActive(tenant) ? 'Deactivate' : 'Activate' }}
                  </button>
                  <button class="link-button danger" type="button" @click="deleteTenant(tenant)">Delete</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="isModalOpen" class="modal-backdrop" @click.self="closeModal">
      <form class="modal" @submit.prevent="handleSubmit">
        <div class="modal-header">
          <h2>{{ modalTitle }}</h2>
          <button class="icon-button" type="button" aria-label="Close modal" @click="closeModal">×</button>
        </div>

        <p v-if="modalError" class="alert alert-error">{{ modalError }}</p>

        <label for="full_name">Full Name</label>
        <input id="full_name" v-model.trim="form.full_name" type="text" required>

        <label for="email">Email</label>
        <input id="email" v-model.trim="form.email" type="email" required>

        <label for="phone">Phone</label>
        <input id="phone" v-model.trim="form.phone" type="tel" required>

        <label for="client_prefix">Client Prefix <span>(optional)</span></label>
        <input id="client_prefix" v-model.trim="form.client_prefix" type="text" maxlength="5">
        <p class="modal-hint">{{ modalPrefixHint }}</p>

        <template v-if="!isEditMode">
          <label for="tenant_username">Username</label>
          <input id="tenant_username" v-model.trim="form.username" type="text" required>

          <label for="password">Password <span>(optional)</span></label>
          <input id="password" v-model="form.password" type="password" autocomplete="new-password">
        </template>

        <label for="evolution_instance_name">Evolution Instance</label>
        <input
          id="evolution_instance_name"
          v-model.trim="form.evolution_instance_name"
          type="text"
          required
        >

        <div class="modal-actions">
          <button class="button button-secondary" type="button" @click="closeModal">Cancel</button>
          <button class="button button-primary" type="submit" :disabled="isSaving">
            {{ isSaving ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </form>
    </div>
  </main>
</template>

<style scoped>
:global(:root) {
  --primary: #4f46e5;
  --danger: #ef4444;
  --success: #22c55e;
  --warning: #f59e0b;
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
.row-actions,
.modal-header,
.modal-actions {
  display: flex;
  align-items: center;
}

.dashboard-header,
.section-header,
.modal-header {
  justify-content: space-between;
  gap: 16px;
}

.dashboard-header {
  margin-bottom: 24px;
}

.eyebrow,
.section-header p,
.summary-card span {
  color: var(--text-secondary);
}

.eyebrow {
  margin: 0 0 4px;
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
  margin-bottom: 6px;
}

.user-actions {
  gap: 12px;
}

.username {
  color: var(--text-secondary);
  font-weight: 600;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.summary-card,
.content-card,
.modal {
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--card-bg);
  box-shadow: 0 10px 25px rgb(15 23 42 / 8%);
}

.summary-card {
  padding: 22px;
}

.summary-card strong {
  display: block;
  margin-top: 10px;
  font-size: 2rem;
}

.content-card {
  padding: 24px;
}

.button,
.link-button,
.icon-button {
  cursor: pointer;
  border: 0;
  font: inherit;
}

.button {
  border-radius: 10px;
  padding: 10px 16px;
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
  background: #ffffff;
  color: var(--text);
}

.alert {
  border-radius: 10px;
  padding: 12px 14px;
  font-weight: 600;
}

.alert-error {
  background: #fee2e2;
  color: #991b1b;
}

.alert-success {
  background: #dcfce7;
  color: #166534;
}

.empty-state {
  padding: 42px 16px;
  color: var(--text-secondary);
  text-align: center;
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
  gap: 10px;
}

.link-button {
  background: transparent;
  color: var(--primary);
  font-weight: 700;
}

.link-button.danger {
  color: var(--danger);
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 10;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(15 23 42 / 55%);
}

.modal {
  width: min(520px, 100%);
  padding: 24px;
}

.icon-button {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  background: #f1f5f9;
  color: var(--text-secondary);
  font-size: 1.5rem;
  line-height: 1;
}

label {
  display: block;
  margin: 14px 0 6px;
  color: var(--text-secondary);
  font-weight: 700;
}

label span {
  font-weight: 500;
}

.modal-hint {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
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

.modal-actions {
  justify-content: flex-end;
  gap: 12px;
  margin-top: 22px;
}

@media (max-width: 760px) {
  .dashboard-page {
    padding: 20px;
  }

  .dashboard-header,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
