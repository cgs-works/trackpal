<script setup>
import { computed, ref, watch } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useI18nStore } from '../../stores/i18n'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

const emit = defineEmits(['close', 'saved'])
const props = defineProps({
  isOpen: { type: Boolean, default: false },
})

const authStore = useAuthStore()
const i18nStore = useI18nStore()

const isSaving = ref(false)
const isLoading = ref(false)
const errorMessage = ref('')
const loadError = ref('')
const customDay = ref('')

const settings = ref({
  reminders_enabled: false,
  timezone: 'UTC',
  warning_days: [7, 3, 1],
  reminder_time: '09:00',
  recipient_mode: 'tenant_only',
})

const timezoneOptions = computed(() => authStore.timezoneOptions || [])
const tzLoadingError = computed(() => !authStore.timezonesLoaded && !!authStore.settingsLoadError)

const recipientModeOptions = computed(() => [
  { value: 'tenant_only', label: i18nStore.t('frontend.subscriptions.recipient_mode_tenant_only') },
  { value: 'client_only', label: i18nStore.t('frontend.subscriptions.recipient_mode_client_only') },
  { value: 'both', label: i18nStore.t('frontend.subscriptions.recipient_mode_both') },
])

async function saveSettings() {
  isSaving.value = true
  errorMessage.value = ''
  try {
    await authStore.updateReminderSettings(settings.value)
    emit('saved')
    emit('close')
  } catch (error) {
    const detail = error.response?.data?.detail
    if (Array.isArray(detail)) {
      errorMessage.value = detail.map((item) => item.msg || item.message || String(item)).join(', ')
    } else {
      errorMessage.value = detail || error.response?.data?.message || i18nStore.t('frontend.subscriptions.error_reminder_settings')
    }
  } finally {
    isSaving.value = false
  }
}

function toggleWarningDay(day) {
  const idx = settings.value.warning_days.indexOf(day)
  if (idx >= 0) {
    settings.value.warning_days.splice(idx, 1)
  } else {
    settings.value.warning_days.push(day)
    settings.value.warning_days.sort((a, b) => a - b)
  }
}

function addCustomWarningDay() {
  const day = parseInt(customDay.value, 10)
  if (!isNaN(day) && day > 0 && !settings.value.warning_days.includes(day)) {
    settings.value.warning_days.push(day)
    settings.value.warning_days.sort((a, b) => a - b)
    customDay.value = ''
  }
}

function removeWarningDay(day) {
  const idx = settings.value.warning_days.indexOf(day)
  if (idx >= 0) {
    settings.value.warning_days.splice(idx, 1)
  }
}

function close() {
  emit('close')
}

watch(
  () => props.isOpen,
  async (newVal) => {
    if (newVal) {
      errorMessage.value = ''
      loadError.value = ''
      customDay.value = ''

      // Only show inline loading if cache is not already warm
      const needsLoad = !authStore.settingsLoaded || !authStore.timezonesLoaded
      if (needsLoad) {
        isLoading.value = true
      }

      try {
        // Reuses any in-flight promise from the silent preload (dedup)
        await authStore.loadTenantSettings()
      } catch (e) {
        loadError.value = authStore.settingsLoadError || i18nStore.t('frontend.subscriptions.error_load_settings')
        isLoading.value = false
        return
      }

      // Deep-clone cached settings into local draft (never mutate store directly)
      const cached = authStore.reminderSettings
      settings.value = {
        reminders_enabled: cached?.reminders_enabled ?? false,
        timezone: cached?.timezone || 'UTC',
        warning_days: [...(cached?.warning_days || [7, 3, 1])],
        reminder_time: cached?.reminder_time || '09:00',
        recipient_mode: cached?.recipient_mode || 'tenant_only',
      }
      isLoading.value = false
    }
  }
)
</script>

<template>
  <Dialog :open="isOpen" @update:open="(v) => !v && close()">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>{{ i18nStore.t('frontend.subscriptions.reminder_settings_title') }}</DialogTitle>
      </DialogHeader>

      <p v-if="errorMessage" class="text-sm text-red-400 bg-red-950/20 border border-red-900/40 rounded px-3 py-2">{{ errorMessage }}</p>

      <!-- Inline loading: shown when modal opens before cache is ready -->
      <div v-if="isLoading" class="flex flex-col items-center justify-center py-10">
        <span class="w-8 h-8 border-4 border-primary/30 border-t-primary rounded-full animate-spin"></span>
        <p class="text-sm text-muted-foreground mt-3">{{ i18nStore.t('frontend.subscriptions.loading_settings') }}</p>
      </div>

      <!-- Load failure blocks save -->
      <p v-else-if="loadError" class="text-sm text-red-400 bg-red-950/20 border border-red-900/40 rounded px-3 py-2">{{ loadError }}</p>

      <!-- Settings form (shown only when not loading and no error) -->
      <div v-if="!isLoading && !loadError" class="flex flex-col gap-4">
        <div class="flex items-center justify-between gap-3">
          <span class="text-sm font-semibold text-foreground">{{ i18nStore.t('frontend.subscriptions.reminders_enabled') }}</span>
          <label class="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" v-model="settings.reminders_enabled" class="sr-only peer" />
            <div class="w-11 h-6 bg-muted-foreground/30 rounded-full peer peer-checked:bg-primary peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:start-[2px] after:bg-foreground after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
          </label>
        </div>

        <template v-if="settings.reminders_enabled">
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-muted-foreground">{{ i18nStore.t('frontend.subscriptions.timezone') }}</label>
            <select v-model="settings.timezone" class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3 outline-none">
              <option v-if="tzLoadingError" value="" disabled>{{ i18nStore.t('frontend.subscriptions.timezone_loading_error') }}</option>
              <option v-else-if="!timezoneOptions.length" value="UTC">UTC</option>
              <option v-for="tz in timezoneOptions" :key="tz.value" :value="tz.value">{{ tz.label }}</option>
            </select>
          </div>

          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-muted-foreground">{{ i18nStore.t('frontend.subscriptions.warning_days') }}</label>
            <div class="flex flex-wrap gap-3 items-center">
              <label class="inline-flex items-center gap-1.5 text-sm" v-for="day in [7, 3, 1]" :key="day">
                <input type="checkbox" :checked="settings.warning_days.includes(day)" @change="toggleWarningDay(day)" class="accent-primary" />
                {{ day }} {{ day === 1 ? i18nStore.t('frontend.subscriptions.day') : i18nStore.t('frontend.subscriptions.day') + 's' }}
              </label>
              <div class="flex gap-1 items-center">
                <input v-model="customDay" type="number" min="1" :placeholder="i18nStore.t('frontend.subscriptions.placeholder_custom_day')" class="h-8 w-20 rounded-md border border-input bg-transparent px-2 text-sm" @keyup.enter="addCustomWarningDay" />
                <Button variant="outline" size="sm" type="button" @click="addCustomWarningDay" :disabled="!customDay">+</Button>
              </div>
            </div>
            <div v-if="settings.warning_days.length" class="flex flex-wrap gap-1.5 mt-1">
              <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-semibold" v-for="day in settings.warning_days" :key="day">
                {{ day }} {{ day === 1 ? i18nStore.t('frontend.subscriptions.day') : i18nStore.t('frontend.subscriptions.day') + 's' }}
                <button type="button" @click="removeWarningDay(day)" class="hover:text-red-500 transition-colors">✕</button>
              </span>
            </div>
          </div>

          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-muted-foreground">{{ i18nStore.t('frontend.subscriptions.reminder_time') }}</label>
            <input v-model="settings.reminder_time" type="time" class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3 outline-none" />
          </div>

          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-muted-foreground">{{ i18nStore.t('frontend.subscriptions.recipient') }}</label>
            <select v-model="settings.recipient_mode" class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3 outline-none">
              <option v-for="opt in recipientModeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
        </template>
      </div>

      <DialogFooter class="gap-2">
        <Button variant="outline" type="button" @click="close">{{ i18nStore.t('frontend.subscriptions.cancel_action') }}</Button>
        <Button type="button" @click="saveSettings" :disabled="isSaving || isLoading || !!loadError">
          {{ isSaving ? i18nStore.t('frontend.subscriptions.saving') : i18nStore.t('frontend.subscriptions.save') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
