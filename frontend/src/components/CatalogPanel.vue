<script setup>
import { onMounted, ref } from 'vue'
import api from '../services/api'
import { useI18nStore } from '../stores/i18n'

const i18nStore = useI18nStore()

const services = ref([])
const selectedServiceId = ref('')
const plans = ref([])
const serviceName = ref('')
const planName = ref('')
const catalogMessage = ref('')
const errorMessage = ref('')

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
  const name = window.prompt(i18nStore.t('frontend.catalog.rename_service_prompt'), service.name)
  if (!name) return
  try {
    await api.put(`/catalog/services/${service.id}`, { name })
    await loadServices()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_update_service'))
  }
}

async function deleteService(service) {
  if (!window.confirm(i18nStore.t('frontend.catalog.delete_service_confirm', { name: service.name }))) return
  try {
    await api.delete(`/catalog/services/${service.id}`)
    if (selectedServiceId.value === service.id) selectedServiceId.value = ''
    await loadServices()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_delete_service'))
  }
}

async function createPlan() {
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
  const name = window.prompt(i18nStore.t('frontend.catalog.rename_plan_prompt'), plan.name)
  if (!name) return
  try {
    await api.put(`/catalog/services/${selectedServiceId.value}/plans/${plan.id}`, { name })
    await loadPlans()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_update_plan'))
  }
}

async function deletePlan(plan) {
  if (!window.confirm(i18nStore.t('frontend.catalog.delete_plan_confirm', { name: plan.name }))) return
  try {
    await api.delete(`/catalog/services/${selectedServiceId.value}/plans/${plan.id}`)
    await loadPlans()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.catalog.error_delete_plan'))
  }
}

onMounted(loadServices)
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
        <button class="link-button danger" type="button" @click="deleteService(service)">{{ i18nStore.t('frontend.catalog.delete') }}</button>
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
        <button class="link-button danger" type="button" @click="deletePlan(plan)">{{ i18nStore.t('frontend.catalog.delete') }}</button>
      </li>
    </ul>
  </section>
</template>
