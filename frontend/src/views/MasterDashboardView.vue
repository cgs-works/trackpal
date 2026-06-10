<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'
import DashboardLayout from '../components/DashboardLayout.vue'
import PageHeader from '../components/PageHeader.vue'
import InlineAlert from '../components/InlineAlert.vue'
import StatusBadge from '../components/StatusBadge.vue'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableEmpty,
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
const isModalOpen = ref(false)
const modalMode = ref('create')
const form = ref(getEmptyForm())

const isEditMode = computed(() => modalMode.value === 'edit')
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

    isModalOpen.value = false
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

async function deleteTenant(tenant) {
  clearMessages()

  if (isTenantActive(tenant)) {
    errorMessage.value = 'Cannot delete active business. Deactivate first.'
    return
  }

  if (!window.confirm(`Delete business ${tenant.full_name}? This action cannot be undone.`)) {
    return
  }

  try {
    await api.delete(`/tenants/${tenant.id}`)
    successMessage.value = 'Business deleted successfully.'
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
          <button
            @click="openCreateModal"
            type="button"
            class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-sm font-medium rounded-md shadow-sm transition-colors cursor-pointer"
          >
            Create Business
          </button>
        </template>
      </PageHeader>

      <InlineAlert v-if="errorMessage" variant="error" :message="errorMessage" />
      <InlineAlert v-if="successMessage" variant="success" :message="successMessage" />

      <!-- Summary cards -->
      <div class="grid grid-cols-3 gap-4" aria-label="Business summary">
        <div class="rounded-xl border bg-card text-card-foreground shadow-sm p-5">
          <p class="text-xs font-medium text-muted-foreground">Total Businesses</p>
          <p class="text-2xl font-bold text-foreground mt-1.5">{{ meta.total }}</p>
        </div>
        <div class="rounded-xl border bg-card text-card-foreground shadow-sm p-5">
          <p class="text-xs font-medium text-muted-foreground">Active</p>
          <p class="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1.5">{{ meta.active }}</p>
        </div>
        <div class="rounded-xl border bg-card text-card-foreground shadow-sm p-5">
          <p class="text-xs font-medium text-muted-foreground">Inactive</p>
          <p class="text-2xl font-bold text-muted-foreground mt-1.5">{{ meta.inactive }}</p>
        </div>
      </div>

      <!-- Businesses table -->
      <div v-if="isLoading" class="flex items-center justify-center py-10 text-sm text-muted-foreground">
        Loading businesses...
      </div>

      <Table v-else-if="tenants.length" class="rounded-xl border">
        <TableHeader>
          <TableRow>
            <TableHead>Full Name</TableHead>
            <TableHead>Client Prefix</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Phone</TableHead>
            <TableHead>Evolution Instance</TableHead>
            <TableHead>Status</TableHead>
            <TableHead class="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="tenant in tenants" :key="tenant.id">
            <TableCell class="font-medium">{{ tenant.full_name }}</TableCell>
            <TableCell class="text-muted-foreground">{{ tenant.client_prefix || '—' }}</TableCell>
            <TableCell class="font-mono text-xs">{{ tenant.email }}</TableCell>
            <TableCell>{{ tenant.phone }}</TableCell>
            <TableCell class="font-mono text-xs">{{ tenant.evolution_instance_name || '—' }}</TableCell>
            <TableCell>
              <StatusBadge
                :variant="isTenantActive(tenant) ? 'active' : 'inactive'"
                :label="isTenantActive(tenant) ? 'Active' : 'Inactive'"
              />
            </TableCell>
            <TableCell class="text-right">
              <div class="flex items-center justify-end gap-1">
                <button @click="openEditModal(tenant)" class="px-2 py-1 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/30 rounded transition-colors cursor-pointer">Edit</button>
                <button @click="manageCatalog(tenant)" class="px-2 py-1 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/30 rounded transition-colors cursor-pointer">Manage catalog</button>
                <button @click="toggleTenantStatus(tenant)" class="px-2 py-1 text-xs font-medium text-stone-600 dark:text-zinc-400 hover:bg-stone-50 dark:hover:bg-zinc-800/50 rounded transition-colors cursor-pointer">
                  {{ isTenantActive(tenant) ? 'Deactivate' : 'Activate' }}
                </button>
                <button @click="deleteTenant(tenant)" class="px-2 py-1 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 rounded transition-colors cursor-pointer">Delete</button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
        <TableEmpty v-if="!tenants.length && !isLoading" colspan="7">
          No businesses registered yet
        </TableEmpty>
      </Table>

      <div v-else class="flex items-center justify-center py-10 text-sm text-muted-foreground rounded-xl border">
        No businesses registered yet
      </div>

      <!-- Modal -->
      <div v-if="isModalOpen" class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4 backdrop-blur-sm" @click.self="closeModal">
        <form @submit.prevent="handleSubmit" class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md w-full max-w-lg p-6 shadow-md">
          <div class="flex items-center justify-between border-b border-stone-100 dark:border-zinc-800/60 pb-3 mb-4">
            <h3 class="text-base font-bold text-stone-900 dark:text-zinc-100">{{ modalTitle }}</h3>
            <button @click="closeModal" type="button" class="text-stone-400 hover:text-stone-600 dark:text-zinc-500 dark:hover:text-zinc-300 cursor-pointer">✕</button>
          </div>

          <InlineAlert v-if="modalError" variant="error" :message="modalError" class="mb-4" />

          <div class="flex flex-col gap-4">
            <div class="grid grid-cols-2 gap-4">
              <div class="flex flex-col gap-1">
                <label for="full_name" class="text-xs font-medium text-stone-500 dark:text-zinc-400">Full Name</label>
                <input id="full_name" v-model.trim="form.full_name" type="text" required class="px-3 py-2 text-sm bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
              </div>
              <div class="flex flex-col gap-1">
                <label for="email" class="text-xs font-medium text-stone-500 dark:text-zinc-400">Email</label>
                <input id="email" v-model.trim="form.email" type="email" required class="px-3 py-2 text-sm bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div class="flex flex-col gap-1">
                <label for="phone" class="text-xs font-medium text-stone-500 dark:text-zinc-400">Phone</label>
                <input id="phone" v-model.trim="form.phone" type="tel" required class="px-3 py-2 text-sm bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
              </div>
              <div class="flex flex-col gap-1">
                <label for="client_prefix" class="text-xs font-medium text-stone-500 dark:text-zinc-400">Client Prefix <span class="font-normal text-stone-400">(optional)</span></label>
                <input id="client_prefix" v-model.trim="form.client_prefix" type="text" maxlength="5" class="px-3 py-2 text-sm bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
              </div>
            </div>

            <p class="text-xs text-stone-400 dark:text-zinc-500 -mt-2">{{ modalPrefixHint }}</p>

            <template v-if="!isEditMode">
              <div class="grid grid-cols-2 gap-4">
                <div class="flex flex-col gap-1">
                  <label for="tenant_username" class="text-xs font-medium text-stone-500 dark:text-zinc-400">Username</label>
                  <input id="tenant_username" v-model.trim="form.username" type="text" required class="px-3 py-2 text-sm bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
                </div>
                <div class="flex flex-col gap-1">
                  <label for="password" class="text-xs font-medium text-stone-500 dark:text-zinc-400">Password <span class="font-normal text-stone-400">(optional)</span></label>
                  <input id="password" v-model="form.password" type="password" autocomplete="new-password" class="px-3 py-2 text-sm bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
                </div>
              </div>
            </template>

            <div class="flex flex-col gap-1">
              <label for="evolution_instance_name" class="text-xs font-medium text-stone-500 dark:text-zinc-400">Evolution Instance</label>
              <input id="evolution_instance_name" v-model.trim="form.evolution_instance_name" type="text" required class="px-3 py-2 text-sm bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
            </div>
          </div>

          <div class="flex justify-end gap-2 border-t border-stone-100 dark:border-zinc-800/60 pt-4 mt-4">
            <button @click="closeModal" type="button" class="px-4 py-2 text-sm text-stone-500 dark:text-zinc-400 hover:bg-stone-50 dark:hover:bg-zinc-800/50 rounded-md transition-colors cursor-pointer">Cancel</button>
            <button type="submit" :disabled="isSaving" class="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium rounded-md shadow-sm transition-colors cursor-pointer disabled:cursor-not-allowed">
              {{ isSaving ? 'Saving...' : 'Save' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </DashboardLayout>
</template>
