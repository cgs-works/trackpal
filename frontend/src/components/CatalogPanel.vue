<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'
import { useI18nStore } from '../stores/i18n'
import { formatCount, formatPreviewRow, isDeleteConfirmationValid } from './catalogDeletePreview'

const i18nStore = useI18nStore()

const services = ref([])
const selectedServiceId = ref('')
const plans = ref([])
const serviceName = ref('')
const planName = ref('')
const catalogMessage = ref('')
const errorMessage = ref('')

const deletePreview = ref(null)
const deleteTarget = ref(null)
const deleteConfirmText = ref('')
const deletePage = ref(1)
const isDeleteLoading = ref(false)
const isDeleting = ref(false)
const canConfirmDelete = computed(() => isDeleteConfirmationValid(deleteConfirmText.value))

function closeDeleteModal() {
  deletePreview.value = null
  deleteTarget.value = null
  deleteConfirmText.value = ''
  deletePage.value = 1
  isDeleteLoading.value = false
  isDeleting.value = false
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
  if (!deleteTarget.value) return
  isDeleteLoading.value = true
  errorMessage.value = ''
  try {
    const url = deleteTarget.value.type === 'service'
      ? `/catalog/services/${deleteTarget.value.serviceId}/delete-preview?page=${page}&page_size=10`
      : `/catalog/services/${selectedServiceId.value}/plans/${deleteTarget.value.planId}/delete-preview?page=${page}&page_size=10`
    const response = await api.get(url)
    deletePreview.value = response.data
    deletePage.value = page
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_delete_service'))
    closeDeleteModal()
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
  if (!deleteTarget.value || !canConfirmDelete.value) return
  isDeleting.value = true
  try {
    const url = deleteTarget.value.type === 'service'
      ? `/catalog/services/${deleteTarget.value.serviceId}?confirm=true`
      : `/catalog/services/${selectedServiceId.value}/plans/${deleteTarget.value.planId}?confirm=true`
    await api.delete(url)
    if (deleteTarget.value.type === 'service' && selectedServiceId.value === deleteTarget.value.serviceId) selectedServiceId.value = ''
    closeDeleteModal()
    await loadServices()
    if (selectedServiceId.value) await loadPlans()
  } catch (error) {
    errorMessage.value = getApiError(error, deleteTarget.value.type === 'service'
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
    await loadServices()
    catalogMessage.value = i18nStore.t('frontend.catalog.service_created')
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_create_service'))
  }
}

async function renameService(service) {
  catalogMessage.value = ''
  errorMessage.value = ''
  const name = window.prompt(i18nStore.t('frontend.catalog.rename_service_prompt'), service.name)
  if (!name) return
  try {
    await api.put(`/catalog/services/${service.id}`, { name })
    await loadServices()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_update_service'))
  }
}

async function createPlan() {
  catalogMessage.value = ''
  errorMessage.value = ''
  if (!selectedServiceId.value) return
  try {
    await api.post(`/catalog/services/${selectedServiceId.value}/plans`, { name: planName.value })
    planName.value = ''
    await loadPlans()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_create_plan'))
  }
}

async function renamePlan(plan) {
  catalogMessage.value = ''
  errorMessage.value = ''
  const name = window.prompt(i18nStore.t('frontend.catalog.rename_plan_prompt'), plan.name)
  if (!name) return
  try {
    await api.put(`/catalog/services/${selectedServiceId.value}/plans/${plan.id}`, { name })
    await loadPlans()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_update_plan'))
  }
}

onMounted(loadInitialServices)
</script>

<template>
  <section class="content-card profile-card">
    <div class="section-header">
      <div>
        <p class="eyebrow">{{ i18nStore.t('frontend.catalog.section_title') }}</p>
        <h2>{{ i18nStore.t('frontend.catalog.section_heading') }}</h2>
      </div>
    </div>
    <p v-if="catalogMessage" class="alert alert-success">{{ catalogMessage }}</p>
    <p v-if="errorMessage" class="alert alert-error">{{ errorMessage }}</p>

    <form class="form-grid" @submit.prevent="createService">
      <label>{{ i18nStore.t('frontend.catalog.new_service') }}<input v-model.trim="serviceName" type="text" required /></label>
      <div class="form-actions"><button class="button button-primary" type="submit">{{ i18nStore.t('frontend.catalog.create_service') }}</button></div>
    </form>

    <ul>
      <li v-for="service in services" :key="service.id">
        <button class="link-button" type="button" @click="selectedServiceId = service.id; loadPlans()">{{ service.name }}</button>
        <button class="link-button" type="button" @click="renameService(service)">{{ i18nStore.t('frontend.catalog.edit') }}</button>
        <button class="link-button danger" type="button" @click="openDeleteService(service)">{{ i18nStore.t('frontend.catalog.delete') }}</button>
      </li>
    </ul>

    <form v-if="selectedServiceId" class="form-grid" @submit.prevent="createPlan">
      <label>{{ i18nStore.t('frontend.catalog.new_plan') }}<input v-model.trim="planName" type="text" required /></label>
      <div class="form-actions"><button class="button button-primary" type="submit">{{ i18nStore.t('frontend.catalog.create_plan') }}</button></div>
    </form>

    <ul v-if="selectedServiceId">
      <li v-for="plan in plans" :key="plan.id">
        {{ plan.name }}
        <button class="link-button" type="button" @click="renamePlan(plan)">{{ i18nStore.t('frontend.catalog.edit') }}</button>
        <button class="link-button danger" type="button" @click="openDeletePlan(plan)">{{ i18nStore.t('frontend.catalog.delete') }}</button>
      </li>
    </ul>

    <!-- Delete preview modal -->
    <div v-if="deleteTarget" class="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ deletePreviewTitle() }}</h3>
          <button class="modal-close" type="button" @click="closeDeleteModal">✕</button>
        </div>
        <div class="modal-body">
          <p v-if="isDeleteLoading">{{ i18nStore.t('frontend.catalog.delete_preview_loading') }}</p>
          <template v-else-if="deletePreview">
            <p class="delete-target-name"><strong>{{ deletePreview.target_name }}</strong></p>
            <ul class="preview-counts">
              <li v-if="deletePreview.target_type === 'service'">{{ i18nStore.t('frontend.catalog.affected_plans') }}: {{ countText(deletePreview.affected_plan_count, 'frontend.catalog.plan_one', 'frontend.catalog.plan_other') }}</li>
              <li>{{ i18nStore.t('frontend.catalog.active_subscriptions') }}: {{ countText(deletePreview.active_subscription_count, 'frontend.catalog.subscription_one', 'frontend.catalog.subscription_other') }}</li>
              <li>{{ i18nStore.t('frontend.catalog.historical_subscriptions') }}: {{ countText(deletePreview.historical_subscription_count, 'frontend.catalog.subscription_one', 'frontend.catalog.subscription_other') }}</li>
              <li>{{ i18nStore.t('frontend.catalog.total_subscriptions') }}: {{ countText(deletePreview.total_subscription_count, 'frontend.catalog.subscription_one', 'frontend.catalog.subscription_other') }}</li>
            </ul>
            <p class="warning-note">{{ i18nStore.t('frontend.catalog.delete_preview_note') }}</p>
            <ul v-if="deletePreview.active_subscriptions?.length" class="preview-rows">
              <li v-for="row in deletePreview.active_subscriptions" :key="row.id">{{ formatPreviewRow(row) }}</li>
            </ul>
            <p v-else class="no-rows">{{ i18nStore.t('frontend.catalog.no_active_rows') }}</p>
            <div v-if="deletePreview.pagination?.total_pages > 1" class="pagination-actions">
              <button class="button button-secondary button-small" type="button" :disabled="deletePage <= 1 || isDeleteLoading" @click="loadDeletePreview(deletePage - 1)">{{ i18nStore.t('frontend.catalog.preview_prev') }}</button>
              <button class="button button-secondary button-small" type="button" :disabled="!deletePreview.pagination.has_next || isDeleteLoading" @click="loadDeletePreview(deletePage + 1)">{{ i18nStore.t('frontend.catalog.preview_next') }}</button>
            </div>
            <label class="confirm-field">{{ i18nStore.t('frontend.catalog.confirm_label') }}<input v-model.trim="deleteConfirmText" type="text" :placeholder="i18nStore.t('frontend.catalog.confirm_placeholder')" /></label>
          </template>
        </div>
        <div class="modal-footer">
          <button class="button button-secondary" type="button" @click="closeDeleteModal">{{ i18nStore.t('frontend.catalog.cancel_delete') }}</button>
          <button class="button button-primary danger-action" type="button" :disabled="!canConfirmDelete || isDeleting" @click="confirmDelete">{{ isDeleting ? i18nStore.t('frontend.catalog.deleting') : i18nStore.t('frontend.catalog.confirm_delete') }}</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal {
  background: var(--card-bg, #fff);
  border-radius: 16px;
  width: min(92vw, 620px);
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 25px 50px rgba(15, 23, 42, 0.25);
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 24px;
}
.modal-body {
  padding: 0 24px 20px;
  display: grid;
  gap: 14px;
}
.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid var(--border, #e2e8f0);
}
.modal-close {
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 1.25rem;
  line-height: 1;
  padding: 4px 8px;
  border-radius: 6px;
}
.modal-close:hover {
  background: var(--hover-bg, #f1f5f9);
}
.preview-counts {
  margin: 0;
  padding-left: 20px;
}
.preview-rows {
  margin: 0;
  padding-left: 20px;
  font-size: 0.875rem;
}
.preview-rows li {
  margin-bottom: 4px;
}
.warning-note {
  color: var(--danger, #ef4444);
  font-weight: 600;
  font-size: 0.875rem;
}
.no-rows {
  font-size: 0.875rem;
  color: var(--muted, #64748b);
}
.pagination-actions {
  display: flex;
  gap: 8px;
}
.confirm-field {
  display: grid;
  gap: 4px;
  font-size: 0.875rem;
}
.danger-action {
  background: var(--danger, #ef4444);
  border-color: var(--danger, #ef4444);
}
.danger-action:hover {
  background: var(--danger-hover, #dc2626);
  border-color: var(--danger-hover, #dc2626);
}
.danger-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.delete-target-name {
  font-size: 1.125rem;
}
</style>
