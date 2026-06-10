<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import { useI18nStore } from '@/stores/i18n'
import InlineAlert from '@/components/InlineAlert.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import SummaryMetric from '@/components/SummaryMetric.vue'
import EntityInspector from '@/components/EntityInspector.vue'
import ImpactConfirmDialog from '@/components/ImpactConfirmDialog.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

const router = useRouter()
const i18nStore = useI18nStore()

const clients = ref([])
const clientForm = ref(getEmptyClientForm())
const clientMessage = ref('')
const clientError = ref('')
const isSavingClient = ref(false)
const isLoadingClients = ref(false)
const selectedClient = ref(null)
const isClientDialogOpen = ref(false)
const clientDialogMode = ref('create')
const deleteDialogOpen = ref(false)
const deleteTarget = ref(null)

const isEditingClient = computed(() => clientDialogMode.value === 'edit')
const activeCount = computed(() => clients.value.filter((client) => client.is_active).length)
const inactiveCount = computed(() => clients.value.length - activeCount.value)

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

function selectClient(client) {
  selectedClient.value = client
}

function editClient(client) {
  clientError.value = ''
  clientMessage.value = ''
  clientForm.value = {
    id: client.id,
    full_name: client.full_name || '',
    local_username: client.local_username || client.username || '',
    phone: client.phone || '',
    password: '',
  }
}

function openCreateClientDialog() {
  clientDialogMode.value = 'create'
  resetClientForm()
  clientError.value = ''
  clientMessage.value = ''
  isClientDialogOpen.value = true
}

function openEditClientDialog(client) {
  clientDialogMode.value = 'edit'
  editClient(client)
  isClientDialogOpen.value = true
}

function openDeleteClientDialog(client) {
  clientError.value = ''
  clientMessage.value = ''
  deleteTarget.value = client
  deleteDialogOpen.value = true
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
    isClientDialogOpen.value = false
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

async function confirmDeleteClient() {
  const client = deleteTarget.value
  if (!client) return

  if (client.is_active) {
    clientError.value = i18nStore.t('frontend.clients.cannot_delete_active')
    deleteDialogOpen.value = false
    return
  }

  try {
    await api.delete(`/clients/${client.id}`)
    clientMessage.value = i18nStore.t('frontend.clients.deleted')
    deleteDialogOpen.value = false
    deleteTarget.value = null
    if (selectedClient.value?.id === client.id) selectedClient.value = null
    await loadClients()
  } catch (error) {
    clientError.value = getApiError(error, i18nStore.t('frontend.clients.error_delete'))
  }
}

onMounted(loadClients)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-end">
      <Button @click="openCreateClientDialog">{{ i18nStore.t('frontend.clients.create') }}</Button>
    </div>

    <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <SummaryMetric :label="i18nStore.t('frontend.clients.section_heading')" :value="clients.length" />
      <SummaryMetric :label="i18nStore.t('frontend.dashboard.client.status_active')" :value="activeCount" tone="success" />
      <SummaryMetric :label="i18nStore.t('frontend.dashboard.client.status_inactive')" :value="inactiveCount" tone="warning" />
    </div>

    <InlineAlert v-if="clientError" variant="error" :message="clientError" />
    <InlineAlert v-if="clientMessage" variant="success" :message="clientMessage" />

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <section class="rounded-xl border border-border bg-card">
        <LoadingBlock v-if="isLoadingClients" />

        <EmptyState
          v-else-if="!clients.length"
          :title="i18nStore.t('frontend.clients.no_clients')"
        />

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
            <TableRow
              v-for="client in clients"
              :key="client.id"
              :data-testid="`client-row-${client.id}`"
              :class="selectedClient?.id === client.id ? 'bg-accent border-ring' : 'hover:bg-accent'"
              class="cursor-pointer"
              @click="selectClient(client)"
            >
              <TableCell class="font-medium">{{ client.full_name }}</TableCell>
              <TableCell>{{ client.username || client.local_username }}</TableCell>
              <TableCell>{{ client.phone || '—' }}</TableCell>
              <TableCell>
                <StatusBadge
                  :variant="client.is_active ? 'active' : 'inactive'"
                  :label="client.is_active ? i18nStore.t('frontend.dashboard.client.status_active') : i18nStore.t('frontend.dashboard.client.status_inactive')"
                />
              </TableCell>
              <TableCell class="text-right">
                <div class="flex flex-wrap items-center justify-end gap-2">
                  <Button :data-testid="`client-edit-${client.id}`" variant="outline" size="sm" @click.stop="openEditClientDialog(client)">{{ i18nStore.t('frontend.clients.edit') }}</Button>
                  <Button variant="outline" size="sm" @click.stop="toggleClientStatus(client)">
                    {{ client.is_active ? i18nStore.t('frontend.clients.deactivate') : i18nStore.t('frontend.clients.activate') }}
                  </Button>
                  <Button variant="outline" size="sm" @click.stop="router.push('/admin/subscriptions?client_id=' + client.id)">{{ i18nStore.t('frontend.clients.subscriptions') }}</Button>
                  <Button variant="destructive" size="sm" @click.stop="openDeleteClientDialog(client)">{{ i18nStore.t('frontend.clients.delete') }}</Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </section>

      <EntityInspector
        v-if="selectedClient"
        data-testid="client-inspector"
        title="Client detail"
        :description="selectedClient.full_name"
        :edit-label="i18nStore.t('frontend.clients.edit')"
        :fields="[
          { label: i18nStore.t('frontend.dashboard.client.local_user'), value: selectedClient.username || selectedClient.local_username },
          { label: i18nStore.t('frontend.profile.phone'), value: selectedClient.phone },
          { label: i18nStore.t('frontend.subscriptions.status'), value: selectedClient.is_active ? i18nStore.t('frontend.dashboard.client.status_active') : i18nStore.t('frontend.dashboard.client.status_inactive') },
        ]"
        @edit="openEditClientDialog(selectedClient)"
      />
    </div>

    <Dialog :open="isClientDialogOpen" @update:open="isClientDialogOpen = $event">
      <DialogContent data-testid="client-form-dialog" class="sm:max-w-2xl">
        <form class="space-y-4" @submit.prevent="saveClient">
          <DialogHeader>
            <DialogTitle>{{ isEditingClient ? i18nStore.t('frontend.clients.edit') : i18nStore.t('frontend.clients.create') }}</DialogTitle>
            <DialogDescription>Manage client access and contact details.</DialogDescription>
          </DialogHeader>

          <div class="grid gap-4 sm:grid-cols-2">
            <div class="space-y-1.5">
              <label class="text-sm font-medium">{{ i18nStore.t('frontend.profile.full_name') }}</label>
              <Input v-model.trim="clientForm.full_name" type="text" required />
            </div>
            <div class="space-y-1.5">
              <label class="text-sm font-medium">{{ i18nStore.t('frontend.dashboard.client.local_user') }}</label>
              <Input v-model.trim="clientForm.local_username" type="text" required />
            </div>
            <div class="space-y-1.5">
              <label class="text-sm font-medium">{{ i18nStore.t('frontend.profile.phone') }}</label>
              <Input v-model.trim="clientForm.phone" type="tel" />
            </div>
            <div v-if="!isEditingClient" class="space-y-1.5">
              <label class="text-sm font-medium">{{ i18nStore.t('frontend.clients.password') }}</label>
              <Input v-model="clientForm.password" type="password" autocomplete="new-password" required />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" @click="isClientDialogOpen = false">{{ i18nStore.t('frontend.common.cancel') }}</Button>
            <Button type="submit" :disabled="isSavingClient">
              {{ isSavingClient ? i18nStore.t('frontend.clients.saving') : (isEditingClient ? i18nStore.t('frontend.clients.update') : i18nStore.t('frontend.clients.create')) }}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <ImpactConfirmDialog
      :open="deleteDialogOpen"
      :title="i18nStore.t('frontend.clients.delete')"
      :description="i18nStore.t('frontend.clients.confirm_delete', { name: deleteTarget?.full_name || '' })"
      :target-name="deleteTarget?.full_name || ''"
      :impacts="[
        { label: i18nStore.t('frontend.subscriptions.status'), value: deleteTarget?.is_active ? i18nStore.t('frontend.clients.cannot_delete_active') : i18nStore.t('frontend.clients.deleted') },
      ]"
      :confirm-label="i18nStore.t('frontend.clients.delete')"
      @update:open="deleteDialogOpen = $event"
      @confirm="confirmDeleteClient"
    />
  </div>
</template>
