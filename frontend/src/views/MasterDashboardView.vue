<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'
import InlineAlert from '@/components/InlineAlert.vue'
import StatusBadge from '@/components/StatusBadge.vue'
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
const authStore = useAuthStore()
const i18nStore = useI18nStore()

const tenants = ref([])
const meta = ref({ total: 0, active: 0, inactive: 0 })
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const modalError = ref('')
const isTenantDialogOpen = ref(false)
const tenantDialogMode = ref('create')
const selectedTenant = ref(null)
const deleteDialogOpen = ref(false)
const deleteTarget = ref(null)
const form = ref(getEmptyForm())

const isEditMode = computed(() => tenantDialogMode.value === 'edit')
const modalTitle = computed(() => (isEditMode.value ? 'Edit Business' : 'Create Business'))
const modalPrefixHint = computed(() => (
  isEditMode.value
    ? 'Changing this prefix will update all client login usernames for this business.'
    : 'Leave blank to auto-generate a unique prefix.'
))

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
    errorMessage.value = getApiError(error, 'Unable to load businesses')
  } finally {
    isLoading.value = false
  }
}

function clearMessages() {
  errorMessage.value = ''
  successMessage.value = ''
  modalError.value = ''
}

function selectTenant(tenant) {
  selectedTenant.value = tenant
}

function openCreateTenantDialog() {
  clearMessages()
  tenantDialogMode.value = 'create'
  form.value = getEmptyForm()
  isTenantDialogOpen.value = true
}

function openEditTenantDialog(tenant) {
  clearMessages()
  tenantDialogMode.value = 'edit'
  form.value = {
    ...getEmptyForm(),
    id: tenant.id,
    full_name: tenant.full_name || '',
    email: tenant.email || '',
    phone: tenant.phone || '',
    client_prefix: tenant.client_prefix || '',
    evolution_instance_name: tenant.evolution_instance_name || '',
  }
  isTenantDialogOpen.value = true
}

function closeModal() {
  if (isSaving.value) return
  isTenantDialogOpen.value = false
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
      successMessage.value = 'Business updated successfully.'
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
        ? `Business created successfully. Generated password: ${generatedPassword}`
        : 'Business created successfully.'
    }

    isTenantDialogOpen.value = false
    await loadTenants()
  } catch (error) {
    modalError.value = getApiError(error, 'Unable to save business')
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
    successMessage.value = active ? 'Business deactivated successfully.' : 'Business activated successfully.'
    await loadTenants()
  } catch (error) {
    errorMessage.value = getApiError(error, 'Unable to update business status')
  }
}

function openDeleteTenantDialog(tenant) {
  clearMessages()
  deleteTarget.value = tenant
  deleteDialogOpen.value = true
}

async function confirmTenantDelete() {
  const tenant = deleteTarget.value
  if (!tenant) return

  if (isTenantActive(tenant)) {
    errorMessage.value = 'Cannot delete active business. Deactivate first.'
    deleteDialogOpen.value = false
    return
  }

  try {
    await api.delete(`/tenants/${tenant.id}`)
    successMessage.value = 'Business deleted successfully.'
    deleteDialogOpen.value = false
    deleteTarget.value = null
    if (selectedTenant.value?.id === tenant.id) selectedTenant.value = null
    await loadTenants()
  } catch (error) {
    errorMessage.value = getApiError(error, 'Unable to delete business')
  }
}

async function manageCatalog(tenant) {
  clearMessages()
  try {
    await authStore.switchTenant(tenant.id)
    await router.push('/admin/overview')
  } catch (error) {
    errorMessage.value = getApiError(error, 'Unable to switch business context')
  }
}

onMounted(loadTenants)
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Overview">
        <template #actions>
          <Button @click="openCreateTenantDialog">Create Business</Button>
        </template>
      </PageHeader>

      <InlineAlert v-if="errorMessage" variant="error" :message="errorMessage" />
      <InlineAlert v-if="successMessage" variant="success" :message="successMessage" />

      <div class="grid grid-cols-1 gap-3 sm:grid-cols-3" aria-label="Business summary">
        <SummaryMetric label="Total Businesses" :value="meta.total" />
        <SummaryMetric label="Active" :value="meta.active" tone="success" />
        <SummaryMetric label="Inactive" :value="meta.inactive" tone="warning" />
      </div>

      <div class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <section class="rounded-xl border border-border bg-card">
          <div v-if="isLoading" class="flex items-center justify-center py-10 text-sm text-muted-foreground">
            Loading businesses...
          </div>

          <Table v-else-if="tenants.length">
            <TableHeader>
              <TableRow>
                <TableHead>Full Name</TableHead>
                <TableHead>Client Prefix</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead>Status</TableHead>
                <TableHead class="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="tenant in tenants"
                :key="tenant.id"
                :data-testid="`tenant-row-${tenant.id}`"
                :class="selectedTenant?.id === tenant.id ? 'bg-accent border-ring' : 'hover:bg-accent'"
                class="cursor-pointer"
                @click="selectTenant(tenant)"
              >
                <TableCell class="font-medium">{{ tenant.full_name }}</TableCell>
                <TableCell class="text-muted-foreground">{{ tenant.client_prefix || '—' }}</TableCell>
                <TableCell class="font-mono text-xs">{{ tenant.email }}</TableCell>
                <TableCell>{{ tenant.phone }}</TableCell>
                <TableCell>
                  <StatusBadge
                    :variant="isTenantActive(tenant) ? 'active' : 'inactive'"
                    :label="isTenantActive(tenant) ? 'Active' : 'Inactive'"
                  />
                </TableCell>
                <TableCell class="text-right">
                  <div class="flex flex-wrap items-center justify-end gap-2">
                    <Button :data-testid="`tenant-edit-${tenant.id}`" size="sm" variant="outline" @click.stop="openEditTenantDialog(tenant)">Edit</Button>
                    <Button size="sm" variant="outline" @click.stop="manageCatalog(tenant)">Catalog</Button>
                    <Button size="sm" variant="outline" @click.stop="toggleTenantStatus(tenant)">{{ isTenantActive(tenant) ? 'Deactivate' : 'Activate' }}</Button>
                    <Button size="sm" variant="destructive" @click.stop="openDeleteTenantDialog(tenant)">Delete</Button>
                  </div>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>

          <div v-else class="flex items-center justify-center py-10 text-sm text-muted-foreground">
            No businesses registered yet
          </div>
        </section>

        <EntityInspector
          v-if="selectedTenant"
          data-testid="tenant-inspector"
          title="Tenant detail"
          :description="selectedTenant.full_name"
          :fields="[
            { label: 'Email', value: selectedTenant.email },
            { label: 'Phone', value: selectedTenant.phone },
            { label: 'Client prefix', value: selectedTenant.client_prefix },
            { label: 'Status', value: isTenantActive(selectedTenant) ? 'Active' : 'Inactive' },
          ]"
          @edit="openEditTenantDialog(selectedTenant)"
        />
      </div>

      <Dialog :open="isTenantDialogOpen" @update:open="isTenantDialogOpen = $event">
        <DialogContent data-testid="tenant-form-dialog" class="sm:max-w-2xl">
          <form class="space-y-4" @submit.prevent="handleSubmit">
            <DialogHeader>
              <DialogTitle>{{ modalTitle }}</DialogTitle>
              <DialogDescription>{{ modalPrefixHint }}</DialogDescription>
            </DialogHeader>

            <InlineAlert v-if="modalError" variant="error" :message="modalError" />

            <div class="grid gap-4 sm:grid-cols-2">
              <div class="space-y-1.5">
                <label for="full_name" class="text-sm font-medium">Full Name</label>
                <Input id="full_name" v-model.trim="form.full_name" type="text" required />
              </div>
              <div class="space-y-1.5">
                <label for="email" class="text-sm font-medium">Email</label>
                <Input id="email" v-model.trim="form.email" type="email" required />
              </div>
              <div class="space-y-1.5">
                <label for="phone" class="text-sm font-medium">Phone</label>
                <Input id="phone" v-model.trim="form.phone" type="tel" required />
              </div>
              <div class="space-y-1.5">
                <label for="client_prefix" class="text-sm font-medium">Client Prefix</label>
                <Input id="client_prefix" v-model.trim="form.client_prefix" type="text" maxlength="5" />
              </div>
              <template v-if="!isEditMode">
                <div class="space-y-1.5">
                  <label for="tenant_username" class="text-sm font-medium">Username</label>
                  <Input id="tenant_username" v-model.trim="form.username" type="text" required />
                </div>
                <div class="space-y-1.5">
                  <label for="password" class="text-sm font-medium">Password</label>
                  <Input id="password" v-model="form.password" type="password" autocomplete="new-password" />
                </div>
              </template>
              <div class="space-y-1.5 sm:col-span-2">
                <label for="evolution_instance_name" class="text-sm font-medium">Evolution Instance</label>
                <Input id="evolution_instance_name" v-model.trim="form.evolution_instance_name" type="text" required />
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" :disabled="isSaving" @click="closeModal">Cancel</Button>
              <Button type="submit" :disabled="isSaving">{{ isSaving ? 'Saving...' : 'Save' }}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ImpactConfirmDialog
        :open="deleteDialogOpen"
        title="Delete business"
        description="This action cannot be undone. Active businesses must be deactivated first."
        :target-name="deleteTarget?.full_name || ''"
        :impacts="[
          { label: 'Tenant account', value: 'Will be permanently removed' },
          { label: 'Status', value: deleteTarget && isTenantActive(deleteTarget) ? 'Deactivate first' : 'Ready to delete' },
        ]"
        confirm-label="Delete"
        @update:open="deleteDialogOpen = $event"
        @confirm="confirmTenantDelete"
      />
    </div>
  </DashboardLayout>
</template>
