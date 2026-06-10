<script setup>
import { onMounted, ref } from 'vue'
import api from '../services/api'
import { useI18nStore } from '../stores/i18n'
import InlineAlert from './InlineAlert.vue'
import StatusBadge from './StatusBadge.vue'

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
  <section class="rounded-xl border bg-card text-card-foreground shadow-sm p-6">
    <div class="mb-4">
      <h2 class="text-base font-bold text-foreground">{{ i18nStore.t('frontend.code_services.section_heading') }}</h2>
      <p class="text-sm text-muted-foreground mt-1">{{ i18nStore.t('frontend.code_services.description') }}</p>
    </div>

    <InlineAlert v-if="errorMessage" variant="error" :message="errorMessage" />
    <InlineAlert v-if="successMessage" variant="success" :message="successMessage" />

    <div v-if="isLoading" class="flex items-center justify-center py-8 text-sm text-muted-foreground">
      {{ i18nStore.t('frontend.code_services.loading') }}
    </div>

    <template v-else-if="services.length">
      <div class="flex flex-col gap-2 mb-4">
        <div
          v-for="service in services"
          :key="service.service_key"
          class="flex items-center justify-between px-4 py-3 rounded-lg border bg-card hover:bg-muted/50 transition-colors"
        >
          <label class="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              :checked="service.is_active"
              @change="toggleService(service)"
              class="w-4 h-4 rounded border-border text-indigo-600 focus:ring-indigo-500 cursor-pointer"
            />
            <span class="text-sm font-medium text-foreground">{{ service.label }}</span>
          </label>
          <StatusBadge
            :variant="service.is_active ? 'active' : 'inactive'"
            :label="service.is_active ? i18nStore.t('frontend.code_services.active') : i18nStore.t('frontend.code_services.inactive')"
          />
        </div>
      </div>

      <div class="flex justify-end">
        <button
          type="button"
          :disabled="isSaving"
          @click="saveServices"
          class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-indigo-400 text-white text-sm font-medium rounded-md shadow-sm transition-colors cursor-pointer disabled:cursor-not-allowed"
        >
          {{ isSaving ? i18nStore.t('frontend.code_services.saving') : i18nStore.t('frontend.code_services.save') }}
        </button>
      </div>
    </template>

    <div v-else class="flex items-center justify-center py-8 text-sm text-muted-foreground">
      {{ i18nStore.t('frontend.code_services.none') }}
    </div>
  </section>
</template>
