<script setup>
import { onMounted, ref, computed } from 'vue'
import api from '../services/api'
import { useI18nStore } from '../stores/i18n'
import InlineAlert from './InlineAlert.vue'
import LoadingBlock from './LoadingBlock.vue'
import { Button } from './ui/button'
import { Checkbox } from './ui/checkbox'

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
  <div class="rounded-xl border border-border bg-card shadow-sm">
    <!-- Section header -->
    <div class="border-b border-border px-6 py-4">
      <h2 class="text-sm font-semibold text-foreground">{{ i18nStore.t('frontend.code_services.tenant_section_heading') }}</h2>
      <p class="mt-1 text-xs text-muted-foreground">{{ i18nStore.t('frontend.code_services.tenant_description') }}</p>
    </div>

    <!-- Alerts -->
    <div class="px-6 pt-4 space-y-2">
      <InlineAlert v-if="errorMessage" variant="error" :message="errorMessage" />
      <InlineAlert v-if="successMessage" variant="success" :message="successMessage" />
    </div>

    <!-- Loading -->
    <LoadingBlock v-if="isLoading" />

    <template v-else-if="services.length">
      <!-- Select All / Deselect All -->
      <div class="px-6 pt-4 flex gap-2">
        <Button variant="ghost" size="sm" @click="selectAll">{{ i18nStore.t('frontend.code_services.tenant_select_all') }}</Button>
        <Button variant="ghost" size="sm" @click="deselectAll">{{ i18nStore.t('frontend.code_services.tenant_deselect_all') }}</Button>
      </div>

      <!-- Services list -->
      <div class="px-6 py-4 space-y-2">
        <div
          v-for="service in services"
          :key="service.service_key"
          class="flex items-center justify-between rounded-md border border-border px-3 py-2.5 transition-colors"
          :class="service.is_globally_active ? 'hover:bg-muted/30' : 'opacity-60'"
        >
          <label class="flex items-center gap-3 cursor-pointer">
            <Checkbox
              :checked="selectedKeys.has(service.service_key)"
              :disabled="!service.is_globally_active"
              @update:checked="toggleService(service.service_key)"
            />
            <span class="text-sm font-medium text-foreground">{{ service.label }}</span>
          </label>
          <span
            v-if="!service.is_globally_active"
            class="text-xs italic text-muted-foreground"
          >
            {{ i18nStore.t('frontend.code_services.tenant_globally_inactive') }}
          </span>
        </div>
      </div>

      <!-- Save -->
      <div class="border-t border-border px-6 py-4 flex justify-end">
        <Button variant="default" :disabled="isSaving" @click="saveSelection">
          {{ isSaving ? i18nStore.t('frontend.code_services.tenant_saving') : i18nStore.t('frontend.code_services.tenant_save') }}
        </Button>
      </div>
    </template>

    <div v-else class="px-6 py-8 text-center text-sm text-muted-foreground">
      {{ i18nStore.t('frontend.code_services.no_services') }}
    </div>
  </div>
</template>
