<script setup>
import { onMounted, ref, computed } from 'vue'
import api from '../services/api'
import { useI18nStore } from '../stores/i18n'

const i18nStore = useI18nStore()

const services = ref([])
const selectedKeys = ref(new Set())
const isLoading = ref(false)
const isSaving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

async function loadServices() {
  errorMessage.value = ''
  isLoading.value = true
  try {
    const response = await api.get('/code-services/tenants/current')
    const items = response.data?.services || []
    services.value = items
    selectedKeys.value = new Set(
      items.filter(service => service.is_selected).map(service => service.service_key),
    )
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.code_services.tenant_error_load'))
  } finally {
    isLoading.value = false
  }
}

function toggleService(serviceKey) {
  if (selectedKeys.value.has(serviceKey)) {
    selectedKeys.value.delete(serviceKey)
  } else {
    selectedKeys.value.add(serviceKey)
  }
  // Force reactivity
  selectedKeys.value = new Set(selectedKeys.value)
}

function selectAll() {
  const activeKeys = services.value
    .filter(s => s.is_globally_active)
    .map(s => s.service_key)
  selectedKeys.value = new Set(activeKeys)
}

function deselectAll() {
  selectedKeys.value = new Set()
}

async function saveSelection() {
  errorMessage.value = ''
  successMessage.value = ''
  isSaving.value = true
  try {
    await api.put('/code-services/tenants/current', {
      service_keys: Array.from(selectedKeys.value),
    })
    await loadServices()
    successMessage.value = i18nStore.t('frontend.code_services.tenant_saved')
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.code_services.tenant_error_save'))
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
        <p class="eyebrow">{{ i18nStore.t('frontend.code_services.tenant_section_title') }}</p>
        <h2>{{ i18nStore.t('frontend.code_services.tenant_section_heading') }}</h2>
      </div>
    </div>
    <p class="code-services-description">{{ i18nStore.t('frontend.code_services.tenant_description') }}</p>

    <p v-if="errorMessage" class="alert alert-error">{{ errorMessage }}</p>
    <p v-if="successMessage" class="alert alert-success">{{ successMessage }}</p>

    <div v-if="isLoading" class="empty-state">{{ i18nStore.t('frontend.code_services.loading') }}</div>

    <template v-else-if="services.length">
      <div class="code-services-actions-inline">
        <button class="link-button" type="button" @click="selectAll">
          {{ i18nStore.t('frontend.code_services.tenant_select_all') }}
        </button>
        <button class="link-button" type="button" @click="deselectAll">
          {{ i18nStore.t('frontend.code_services.tenant_deselect_all') }}
        </button>
      </div>

      <div class="code-services-list">
        <div
          v-for="service in services"
          :key="service.service_key"
          class="code-service-row"
          :class="{ disabled: !service.is_globally_active }"
        >
          <label class="code-service-toggle">
            <input
              type="checkbox"
              :checked="selectedKeys.has(service.service_key)"
              :disabled="!service.is_globally_active"
              @change="toggleService(service.service_key)"
            />
            <span class="code-service-label">{{ service.label }}</span>
          </label>
          <span
            v-if="!service.is_globally_active"
            class="globally-inactive-badge"
          >
            {{ i18nStore.t('frontend.code_services.tenant_globally_inactive') }}
          </span>
        </div>
      </div>

      <div class="code-services-actions">
        <button
          class="button button-primary"
          type="button"
          :disabled="isSaving"
          @click="saveSelection"
        >
          {{ isSaving ? i18nStore.t('frontend.code_services.tenant_saving') : i18nStore.t('frontend.code_services.tenant_save') }}
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
.code-services-actions-inline {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
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
.code-service-row.disabled {
  opacity: 0.6;
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
.code-service-toggle input[type="checkbox"]:disabled {
  cursor: not-allowed;
}
.code-service-label {
  font-weight: 500;
}
.globally-inactive-badge {
  font-size: 0.8em;
  color: var(--text-muted, #999);
  font-style: italic;
}
.code-services-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
