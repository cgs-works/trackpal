<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'
import { useI18nStore } from '../stores/i18n'
import { formatCount, formatPreviewRow, isDeleteConfirmationValid } from './catalogDeletePreview'
import InlineAlert from './InlineAlert.vue'
import LoadingBlock from './LoadingBlock.vue'
import { Button } from './ui/button'
import { Input } from './ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog'

const i18nStore = useI18nStore()

const services = ref([])
const selectedServiceId = ref('')
const plans = ref([])
const serviceName = ref('')
const planName = ref('')
const serviceDialogOpen = ref(false)
const planDialogOpen = ref(false)
const catalogMessage = ref('')
const errorMessage = ref('')

const deletePreview = ref(null)
const deleteTarget = ref(null)
const deleteConfirmText = ref('')
const deletePage = ref(1)
const isDeleteLoading = ref(false)
const isDeleting = ref(false)
const deleteError = ref('')
const canConfirmDelete = computed(() => isDeleteConfirmationValid(deleteConfirmText.value))

// Rename dialog state
const showRenameDialog = ref(false)
const renameTarget = ref(null) // { type: 'service'|'plan', item: {...} }
const renameValue = ref('')

function closeDeleteModal() {
  deletePreview.value = null
  deleteTarget.value = null
  deleteConfirmText.value = ''
  deletePage.value = 1
  isDeleteLoading.value = false
  isDeleting.value = false
  deleteError.value = ''
}

function deletePreviewTitle() {
  if (!deleteTarget.value) return ''
  return i18nStore.t(deleteTarget.value.type === 'service'
    ? 'frontend.catalog.delete_preview_title_service'
    : 'frontend.catalog.delete_preview_title_plan')
}

function countText(count, oneKey, otherKey) {
  return formatCount(i18nStore.t, count, oneKey, otherKey)
}

async function loadDeletePreview(page = 1) {
  const target = deleteTarget.value
  if (!target) return
  isDeleteLoading.value = true
  deleteError.value = ''
  errorMessage.value = ''
  try {
    const url = target.type === 'service'
      ? `/catalog/services/${target.serviceId}/delete-preview?page=${page}&page_size=10`
      : `/catalog/services/${selectedServiceId.value}/plans/${target.planId}/delete-preview?page=${page}&page_size=10`
    const response = await api.get(url)
    deletePreview.value = response.data
    deletePage.value = page
  } catch (error) {
    deleteError.value = getApiError(error, target.type === 'service'
      ? i18nStore.t('frontend.catalog.error_delete_service')
      : i18nStore.t('frontend.catalog.error_delete_plan'))
  } finally {
    isDeleteLoading.value = false
  }
}

async function openDeleteService(service) {
  catalogMessage.value = ''
  errorMessage.value = ''
  deleteTarget.value = { type: 'service', serviceId: service.id, name: service.name }
  await loadDeletePreview(1)
}

async function openDeletePlan(plan) {
  catalogMessage.value = ''
  errorMessage.value = ''
  deleteTarget.value = { type: 'plan', planId: plan.id, name: plan.name }
  await loadDeletePreview(1)
}

async function confirmDelete() {
  const target = deleteTarget.value
  if (!target || !canConfirmDelete.value) return
  isDeleting.value = true
  try {
    const url = target.type === 'service'
      ? `/catalog/services/${target.serviceId}?confirm=true`
      : `/catalog/services/${selectedServiceId.value}/plans/${target.planId}?confirm=true`
    await api.delete(url)
    if (target.type === 'service' && selectedServiceId.value === target.serviceId) selectedServiceId.value = ''
    closeDeleteModal()
    await loadServices()
    if (selectedServiceId.value) await loadPlans()
  } catch (error) {
    deleteError.value = getApiError(error, target.type === 'service'
      ? i18nStore.t('frontend.catalog.error_delete_service')
      : i18nStore.t('frontend.catalog.error_delete_plan'))
  } finally {
    isDeleting.value = false
  }
}

function getApiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  }
  return detail || error.response?.data?.message || fallback
}

async function loadServices() {
  const response = await api.get('/catalog/services')
  services.value = response.data || []
  if (!selectedServiceId.value && services.value.length) selectedServiceId.value = services.value[0].id
  if (selectedServiceId.value) await loadPlans()
}

async function loadInitialServices() {
  try {
    await loadServices()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_load_services'))
  }
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
    serviceDialogOpen.value = false
    await loadServices()
    catalogMessage.value = i18nStore.t('frontend.catalog.service_created')
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_create_service'))
  }
}

// Rename dialog handlers
function openRenameService(service) {
  catalogMessage.value = ''
  errorMessage.value = ''
  renameTarget.value = { type: 'service', item: { id: service.id, name: service.name } }
  renameValue.value = service.name
  showRenameDialog.value = true
}

function openRenamePlan(plan) {
  catalogMessage.value = ''
  errorMessage.value = ''
  renameTarget.value = { type: 'plan', item: { id: plan.id, name: plan.name } }
  renameValue.value = plan.name
  showRenameDialog.value = true
}

function closeRenameDialog() {
  showRenameDialog.value = false
  renameTarget.value = null
  renameValue.value = ''
}

async function submitRename() {
  if (!renameTarget.value || !renameValue.value.trim()) return
  const target = renameTarget.value
  const name = renameValue.value.trim()
  catalogMessage.value = ''
  errorMessage.value = ''
  try {
    if (target.type === 'service') {
      await api.put(`/catalog/services/${target.item.id}`, { name })
      await loadServices()
    } else {
      await api.put(`/catalog/services/${selectedServiceId.value}/plans/${target.item.id}`, { name })
      await loadPlans()
    }
    closeRenameDialog()
  } catch (error) {
    errorMessage.value = getApiError(error, target.type === 'service'
      ? i18nStore.t('frontend.catalog.error_update_service')
      : i18nStore.t('frontend.catalog.error_update_plan'))
    closeRenameDialog()
  }
}

async function createPlan() {
  catalogMessage.value = ''
  errorMessage.value = ''
  if (!selectedServiceId.value) return
  try {
    await api.post(`/catalog/services/${selectedServiceId.value}/plans`, { name: planName.value })
    planName.value = ''
    planDialogOpen.value = false
    await loadPlans()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_create_plan'))
  }
}

onMounted(loadInitialServices)
</script>

<template>
  <div class="rounded-xl border border-border bg-card shadow-sm">
    <!-- Section header -->
    <div class="border-b border-border px-6 py-4">
      <h2 class="text-sm font-semibold text-foreground">{{ i18nStore.t('frontend.catalog.section_heading') }}</h2>
    </div>

    <!-- Alerts -->
    <div class="px-6 pt-4 space-y-2">
      <InlineAlert v-if="catalogMessage" variant="success" :message="catalogMessage" />
      <InlineAlert v-if="errorMessage" variant="error" :message="errorMessage" />
    </div>

    <!-- Create Service -->
    <div class="px-6 py-4 border-b border-border">
      <Button size="sm" @click="serviceDialogOpen = true">{{ i18nStore.t('frontend.catalog.create_service') }}</Button>
    </div>

    <!-- Services list -->
    <div class="px-6 py-4 border-b border-border">
      <h3 class="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">{{ i18nStore.t('frontend.catalog.services') }}</h3>
      <div v-if="!services.length" class="text-sm text-muted-foreground py-2">{{ i18nStore.t('frontend.catalog.no_services') }}</div>
      <div v-else class="flex flex-col gap-1.5">
        <div
          v-for="service in services"
          :key="service.id"
          class="flex items-center justify-between rounded-md border border-border px-3 py-2 hover:bg-muted/30 transition-colors"
          :class="{ 'border-ring bg-accent': selectedServiceId === service.id }"
        >
          <button
            type="button"
            class="text-sm font-medium text-foreground hover:text-primary transition-colors"
            @click="selectedServiceId = service.id; loadPlans()"
          >
            {{ service.name }}
          </button>
          <div class="flex items-center gap-1">
            <Button :data-testid="`service-edit-${service.id}`" variant="outline" size="sm" @click="openRenameService(service)">{{ i18nStore.t('frontend.catalog.edit') }}</Button>
            <Button :data-testid="`service-delete-${service.id}`" variant="destructive" size="sm" @click="openDeleteService(service)">{{ i18nStore.t('frontend.catalog.delete') }}</Button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Plan -->
    <div v-if="selectedServiceId" class="px-6 py-4 border-b border-border">
      <Button size="sm" @click="planDialogOpen = true">{{ i18nStore.t('frontend.catalog.create_plan') }}</Button>
    </div>

    <!-- Plans list -->
    <div v-if="selectedServiceId" class="px-6 py-4">
      <h3 class="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">{{ i18nStore.t('frontend.catalog.plans') }}</h3>
      <div v-if="!plans.length" class="text-sm text-muted-foreground py-2">{{ i18nStore.t('frontend.catalog.no_plans') }}</div>
      <div v-else class="flex flex-col gap-1.5">
        <div
          v-for="plan in plans"
          :key="plan.id"
          class="flex items-center justify-between rounded-md border border-border px-3 py-2 hover:bg-muted/30 transition-colors"
        >
          <span class="text-sm text-foreground">{{ plan.name }}</span>
          <div class="flex items-center gap-1">
            <Button :data-testid="`plan-edit-${plan.id}`" variant="outline" size="sm" @click="openRenamePlan(plan)">{{ i18nStore.t('frontend.catalog.edit') }}</Button>
            <Button :data-testid="`plan-delete-${plan.id}`" variant="destructive" size="sm" @click="openDeletePlan(plan)">{{ i18nStore.t('frontend.catalog.delete') }}</Button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Service Dialog -->
    <Dialog v-model:open="serviceDialogOpen">
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{{ i18nStore.t('frontend.catalog.create_service') }}</DialogTitle>
          <DialogDescription>{{ i18nStore.t('frontend.catalog.new_service') }}</DialogDescription>
        </DialogHeader>
        <form @submit.prevent="createService" class="space-y-4">
          <div class="space-y-1.5">
            <label class="text-sm font-medium">{{ i18nStore.t('frontend.catalog.new_service') }}</label>
            <Input v-model.trim="serviceName" type="text" required />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" @click="serviceDialogOpen = false">{{ i18nStore.t('frontend.catalog.cancel') }}</Button>
            <Button type="submit">{{ i18nStore.t('frontend.catalog.create_service') }}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- Create Plan Dialog -->
    <Dialog v-model:open="planDialogOpen">
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{{ i18nStore.t('frontend.catalog.create_plan') }}</DialogTitle>
          <DialogDescription>{{ i18nStore.t('frontend.catalog.new_plan') }}</DialogDescription>
        </DialogHeader>
        <form @submit.prevent="createPlan" class="space-y-4">
          <div class="space-y-1.5">
            <label class="text-sm font-medium">{{ i18nStore.t('frontend.catalog.new_plan') }}</label>
            <Input v-model.trim="planName" type="text" required />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" @click="planDialogOpen = false">{{ i18nStore.t('frontend.catalog.cancel') }}</Button>
            <Button type="submit">{{ i18nStore.t('frontend.catalog.create_plan') }}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- Rename Dialog -->
    <Dialog v-model:open="showRenameDialog">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{{ renameTarget?.type === 'plan' ? i18nStore.t('frontend.catalog.rename_plan') : i18nStore.t('frontend.catalog.rename_service') }}</DialogTitle>
          <DialogDescription>{{ i18nStore.t('frontend.catalog.rename_description') }}</DialogDescription>
        </DialogHeader>
        <form @submit.prevent="submitRename" class="flex flex-col gap-4">
          <Input v-model.trim="renameValue" type="text" required autofocus />
          <DialogFooter>
            <Button type="button" variant="outline" @click="closeRenameDialog">{{ i18nStore.t('frontend.catalog.cancel') }}</Button>
            <Button type="submit" variant="default">{{ i18nStore.t('frontend.catalog.rename') }}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- Delete Preview Dialog -->
    <Dialog :open="!!deleteTarget" @update:open="(val) => { if (!val) closeDeleteModal() }">
      <DialogContent class="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{{ deletePreviewTitle() }}</DialogTitle>
        </DialogHeader>

        <div class="space-y-3">
          <InlineAlert v-if="deleteError" variant="error" :message="deleteError" />

          <LoadingBlock v-if="isDeleteLoading" />

          <template v-else-if="deletePreview">
            <p class="font-medium text-foreground">{{ deletePreview.target_name }}</p>

            <ul class="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
              <li v-if="deletePreview.target_type === 'service'">{{ i18nStore.t('frontend.catalog.affected_plans') }}: {{ countText(deletePreview.affected_plan_count, 'frontend.catalog.plan_one', 'frontend.catalog.plan_other') }}</li>
              <li>{{ i18nStore.t('frontend.catalog.active_subscriptions') }}: {{ countText(deletePreview.active_subscription_count, 'frontend.catalog.subscription_one', 'frontend.catalog.subscription_other') }}</li>
              <li>{{ i18nStore.t('frontend.catalog.historical_subscriptions') }}: {{ countText(deletePreview.historical_subscription_count, 'frontend.catalog.subscription_one', 'frontend.catalog.subscription_other') }}</li>
              <li>{{ i18nStore.t('frontend.catalog.total_subscriptions') }}: {{ countText(deletePreview.total_subscription_count, 'frontend.catalog.subscription_one', 'frontend.catalog.subscription_other') }}</li>
            </ul>

            <p class="text-sm font-semibold text-destructive">{{ i18nStore.t('frontend.catalog.delete_preview_note') }}</p>

            <ul v-if="deletePreview.active_subscriptions?.length" class="space-y-1 text-xs text-muted-foreground">
              <li v-for="row in deletePreview.active_subscriptions" :key="row.id" class="font-mono">{{ formatPreviewRow(row) }}</li>
            </ul>
            <p v-else class="text-sm text-muted-foreground">{{ i18nStore.t('frontend.catalog.no_active_rows') }}</p>

            <div v-if="deletePreview.pagination?.total_pages > 1" class="flex gap-2">
              <Button variant="outline" size="sm" :disabled="deletePage <= 1 || isDeleteLoading" @click="loadDeletePreview(deletePage - 1)">{{ i18nStore.t('frontend.catalog.preview_prev') }}</Button>
              <Button variant="outline" size="sm" :disabled="!deletePreview.pagination.has_next || isDeleteLoading" @click="loadDeletePreview(deletePage + 1)">{{ i18nStore.t('frontend.catalog.preview_next') }}</Button>
            </div>

            <div class="flex flex-col gap-1.5">
              <label class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.catalog.confirm_label') }}</label>
              <Input data-testid="catalog-delete-confirm-input" v-model.trim="deleteConfirmText" type="text" :placeholder="i18nStore.t('frontend.catalog.confirm_placeholder')" />
            </div>
          </template>
        </div>

        <DialogFooter>
          <Button variant="outline" @click="closeDeleteModal">{{ i18nStore.t('frontend.catalog.cancel_delete') }}</Button>
          <Button variant="destructive" :disabled="!canConfirmDelete || isDeleting" @click="confirmDelete">
            {{ isDeleting ? i18nStore.t('frontend.catalog.deleting') : i18nStore.t('frontend.catalog.confirm_delete') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
