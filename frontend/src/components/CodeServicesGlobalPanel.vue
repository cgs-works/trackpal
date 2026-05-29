<script setup>
import { onMounted, ref } from 'vue'
import api from '../services/api'
import { useI18nStore } from '../stores/i18n'

const i18nStore = useI18nStore()

const services = ref([])
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

async function loadServices() {
  errorMessage.value = ''
  successMessage.value = ''
  isLoading.value = true
  try {
    const response = await api.get('/code-services/global')
    services.value = response.data?.services || []
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.code_services.error_load'))
  } finally {
    isLoading.value = false
  }
}

function toggleService(service) {
  service.is_active = !service.is_active
}

async function saveServices() {
  errorMessage.value = ''
  successMessage.value = ''
  isSaving.value = true
  try {
    const payload = {}
    for (const svc of services.value) {
      payload[svc.service_key] = svc.is_active
    }
    await api.put('/code-services/global', { services: payload })
    successMessage.value = i18nStore.t('frontend.code_services.saved')
    await loadServices()
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.code_services.error_save'))
  } finally {
    isSaving.value = false
  }
}

function getApiError(error, fallback) {
  return error.response?.data?.detail || fallback
}

onMounted(loadServices)
</script>

<template>
  <section class="content-card code-services-card">
    <div class="section-header">
      <div>
        <p class="eyebrow">{{ i18nStore.t('frontend.code_services.section_title') }}</p>
        <h2>{{ i18nStore.t('frontend.code_services.section_heading') }}</h2>
      </div>
    </div>
    <p class="code-services-description">{{ i18nStore.t('frontend.code_services.description') }}</p>

    <p v-if="errorMessage" class="alert alert-error">{{ errorMessage }}</p>
    <p v-if="successMessage" class="alert alert-success">{{ successMessage }}</p>

    <div v-if="isLoading" class="empty-state">{{ i18nStore.t('frontend.code_services.loading') }}</div>

    <template v-else-if="services.length">
      <div class="code-services-list">
        <div
          v-for="service in services"
          :key="service.service_key"
          class="code-service-row"
        >
          <label class="code-service-toggle">
            <input
              type="checkbox"
              :checked="service.is_active"
              @change="toggleService(service)"
            />
            <span class="code-service-label">{{ service.label }}</span>
          </label>
          <span
            class="status-badge"
            :class="service.is_active ? 'active' : 'inactive'"
          >
            {{ service.is_active ? i18nStore.t('frontend.code_services.active') : i18nStore.t('frontend.code_services.inactive') }}
          </span>
        </div>
      </div>

      <div class="code-services-actions">
        <button
          class="button button-primary"
          type="button"
          :disabled="isSaving"
          @click="saveServices"
        >
          {{ isSaving ? i18nStore.t('frontend.code_services.saving') : i18nStore.t('frontend.code_services.save') }}
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.code-services-description {
  margin-bottom: 16px;
  color: var(--text-secondary, #666);
}
.code-services-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}
.code-service-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
}
.code-service-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.code-service-toggle input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}
.code-service-label {
  font-weight: 500;
}
.code-services-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
