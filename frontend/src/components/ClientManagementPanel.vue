<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { useI18nStore } from '../stores/i18n'

const router = useRouter()
const i18nStore = useI18nStore()

const clients = ref([])
const clientForm = ref(getEmptyClientForm())
const clientMessage = ref('')
const clientError = ref('')
const isSavingClient = ref(false)
const isLoadingClients = ref(false)
const isEditingClient = computed(() => !!clientForm.value.id)

function getApiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  }
  return detail || error.response?.data?.message || fallback
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

async function loadClients() {
  clientError.value = ''
  isLoadingClients.value = true
  try {
    const response = await api.get('/clients')
    clients.value = response.data || []
  } catch (error) {
    clientError.value = getApiError(error, i18nStore.t('frontend.clients.error_load'))
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
    clientError.value = getApiError(error, i18nStore.t('frontend.clients.error_save'))
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
    clientMessage.value = client.is_active
      ? i18nStore.t('frontend.clients.deactivated')
      : i18nStore.t('frontend.clients.activated')
    clients.value = clients.value.map((entry) => (entry.id === client.id ? response.data : entry))
  } catch (error) {
    clientError.value = getApiError(error, i18nStore.t('frontend.clients.error_toggle_status'))
  }
}

async function deleteClient(client) {
  clientError.value = ''
  clientMessage.value = ''
  if (client.is_active) {
    clientError.value = i18nStore.t('frontend.clients.cannot_delete_active')
    return
  }
  if (!window.confirm(i18nStore.t('frontend.clients.confirm_delete', { name: client.full_name }))) return
  try {
    await api.delete(`/clients/${client.id}`)
    clientMessage.value = i18nStore.t('frontend.clients.deleted')
    await loadClients()
  } catch (error) {
    clientError.value = getApiError(error, i18nStore.t('frontend.clients.error_delete'))
  }
}

onMounted(loadClients)
</script>

<template>
  <section class="content-card profile-card">
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
            <th>{{ i18nStore.t('frontend.profile.phone') }}</th>
            <th>{{ i18nStore.t('frontend.subscriptions.status') }}</th>
            <th>{{ i18nStore.t('frontend.subscriptions.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="client in clients" :key="client.id">
            <td>{{ client.full_name }}</td>
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
</template>
