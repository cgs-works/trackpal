<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { useI18nStore } from '../stores/i18n'
import InlineAlert from './InlineAlert.vue'
import StatusBadge from './StatusBadge.vue'
import EmptyState from './EmptyState.vue'
import LoadingBlock from './LoadingBlock.vue'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from './ui/table'
import { Button } from './ui/button'
import { Input } from './ui/input'

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
  <div class="rounded-xl border border-border bg-card shadow-sm">
    <!-- Section header -->
    <div class="border-b border-border px-6 py-4">
      <h2 class="text-sm font-semibold text-foreground">{{ i18nStore.t('frontend.clients.section_heading') }}</h2>
    </div>

    <!-- Alerts -->
    <div class="px-6 pt-4 space-y-2">
      <InlineAlert v-if="clientError" variant="error" :message="clientError" />
      <InlineAlert v-if="clientMessage" variant="success" :message="clientMessage" />
    </div>

    <!-- Form -->
    <div class="px-6 py-4 border-b border-border">
      <form @submit.prevent="saveClient" class="flex flex-wrap items-end gap-3">
        <div class="flex flex-col gap-1.5 min-w-[160px]">
          <label class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.profile.full_name') }}</label>
          <Input v-model.trim="clientForm.full_name" type="text" required />
        </div>
        <div class="flex flex-col gap-1.5 min-w-[140px]">
          <label class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.dashboard.client.local_user') }}</label>
          <Input v-model.trim="clientForm.local_username" type="text" required />
        </div>
        <div class="flex flex-col gap-1.5 min-w-[130px]">
          <label class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.profile.phone') }}</label>
          <Input v-model.trim="clientForm.phone" type="tel" />
        </div>
        <div v-if="!isEditingClient" class="flex flex-col gap-1.5 min-w-[150px]">
          <label class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.clients.password') }}</label>
          <Input v-model="clientForm.password" type="password" autocomplete="new-password" required />
        </div>
        <div class="flex items-center gap-2 pt-1">
          <Button type="submit" :disabled="isSavingClient" variant="default" size="sm">
            {{ isSavingClient ? i18nStore.t('frontend.clients.saving') : (isEditingClient ? i18nStore.t('frontend.clients.update') : i18nStore.t('frontend.clients.create')) }}
          </Button>
          <Button v-if="isEditingClient" type="button" variant="ghost" size="sm" @click="cancelClientEdit">
            {{ i18nStore.t('frontend.clients.clear') }}
          </Button>
        </div>
      </form>
    </div>

    <!-- Loading -->
    <LoadingBlock v-if="isLoadingClients" />

    <!-- Empty -->
    <EmptyState
      v-else-if="!clients.length"
      :title="i18nStore.t('frontend.clients.no_clients')"
    />

    <!-- Table -->
    <Table v-else>
      <TableHeader>
        <TableRow>
          <TableHead>{{ i18nStore.t('frontend.profile.full_name') }}</TableHead>
          <TableHead>{{ i18nStore.t('frontend.dashboard.client.local_user') }}</TableHead>
          <TableHead>{{ i18nStore.t('frontend.profile.phone') }}</TableHead>
          <TableHead>{{ i18nStore.t('frontend.subscriptions.status') }}</TableHead>
          <TableHead class="text-right">{{ i18nStore.t('frontend.subscriptions.actions') }}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="client in clients" :key="client.id">
          <TableCell class="font-medium">{{ client.full_name }}</TableCell>
          <TableCell>{{ client.username }}</TableCell>
          <TableCell>{{ client.phone || '—' }}</TableCell>
          <TableCell>
            <StatusBadge
              :variant="client.is_active ? 'active' : 'inactive'"
              :label="client.is_active ? i18nStore.t('frontend.dashboard.client.status_active') : i18nStore.t('frontend.dashboard.client.status_inactive')"
            />
          </TableCell>
          <TableCell class="text-right">
            <div class="flex items-center justify-end gap-1">
              <Button variant="ghost" size="sm" @click="editClient(client)">{{ i18nStore.t('frontend.clients.edit') }}</Button>
              <Button variant="ghost" size="sm" @click="toggleClientStatus(client)">
                {{ client.is_active ? i18nStore.t('frontend.clients.deactivate') : i18nStore.t('frontend.clients.activate') }}
              </Button>
              <Button variant="ghost" size="sm" @click="router.push('/admin/subscriptions?client_id=' + client.id)">{{ i18nStore.t('frontend.clients.subscriptions') }}</Button>
              <Button variant="ghost" size="sm" class="text-destructive hover:text-destructive" @click="deleteClient(client)">{{ i18nStore.t('frontend.clients.delete') }}</Button>
            </div>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </div>
</template>
