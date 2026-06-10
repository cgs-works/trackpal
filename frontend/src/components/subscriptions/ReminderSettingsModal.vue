<script setup>
import { computed, ref, watch } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useI18nStore } from '../../stores/i18n'

const emit = defineEmits(['close', 'saved'])
const props = defineProps({
  show: { type: Boolean, default: false },
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
  () => props.show,
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
  <div v-if="show" class="modal-overlay" @click.self="close">
    <div class="modal">
      <div class="modal-header">
        <h2>{{ i18nStore.t('frontend.subscriptions.reminder_settings_title') }}</h2>
        <button class="modal-close" type="button" @click="close">✕</button>
      </div>

      <div class="modal-body">
        <p v-if="errorMessage" class="alert alert-error">{{ errorMessage }}</p>

        <!-- Inline loading: shown when modal opens before cache is ready -->
        <div v-if="isLoading" class="empty-state">
          <span class="spinner" aria-hidden="true"></span>
          <p>{{ i18nStore.t('frontend.subscriptions.loading_settings') }}</p>
        </div>

        <!-- Load failure blocks save -->
        <p v-else-if="loadError" class="alert alert-error">{{ loadError }}</p>

        <!-- Settings form (shown only when not loading and no error) -->
        <template v-if="!isLoading && !loadError">
          <div class="toggle-wrapper">
            <span class="toggle-label-text">{{ i18nStore.t('frontend.subscriptions.reminders_enabled') }}</span>
            <label class="switch">
              <input type="checkbox" v-model="settings.reminders_enabled" />
              <span class="slider"></span>
            </label>
          </div>

          <template v-if="settings.reminders_enabled">
            <label>
              {{ i18nStore.t('frontend.subscriptions.timezone') }}
              <select v-model="settings.timezone">
                <option v-if="tzLoadingError" value="" disabled>{{ i18nStore.t('frontend.subscriptions.timezone_loading_error') }}</option>
                <option v-else-if="!timezoneOptions.length" value="UTC">UTC</option>
                <option v-for="tz in timezoneOptions" :key="tz.value" :value="tz.value">{{ tz.label }}</option>
              </select>
            </label>

            <label>
              {{ i18nStore.t('frontend.subscriptions.warning_days') }}
              <div class="warning-days-container">
                <label class="day-check" v-for="day in [7, 3, 1]" :key="day">
                  <input type="checkbox" :checked="settings.warning_days.includes(day)" @change="toggleWarningDay(day)" />
                  {{ day }} {{ day === 1 ? i18nStore.t('frontend.subscriptions.day') : i18nStore.t('frontend.subscriptions.day') + 's' }}
                </label>
                <div class="custom-day-input">
                  <input v-model="customDay" type="number" min="1" :placeholder="i18nStore.t('frontend.subscriptions.placeholder_custom_day')" @keyup.enter="addCustomWarningDay" />
                  <button class="button button-sm" type="button" @click="addCustomWarningDay" :disabled="!customDay">+</button>
                </div>
              </div>
              <div v-if="settings.warning_days.length" class="warning-days-tags">
                <span class="tag" v-for="day in settings.warning_days" :key="day">
                  {{ day }} {{ day === 1 ? i18nStore.t('frontend.subscriptions.day') : i18nStore.t('frontend.subscriptions.day') + 's' }}
                  <button class="tag-remove" type="button" @click="removeWarningDay(day)">✕</button>
                </span>
              </div>
            </label>

            <label>
              {{ i18nStore.t('frontend.subscriptions.reminder_time') }}
              <input v-model="settings.reminder_time" type="time" />
              <span class="field-help">{{ i18nStore.t('frontend.subscriptions.reminder_time_help') }}</span>
            </label>

            <label>
              {{ i18nStore.t('frontend.subscriptions.recipient') }}
              <select v-model="settings.recipient_mode">
                <option v-for="opt in recipientModeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </label>
          </template>
        </template>
      </div>

      <div class="modal-footer">
        <button class="button button-secondary" type="button" @click="close">{{ i18nStore.t('frontend.subscriptions.cancel_action') }}</button>
        <button class="button button-primary" type="button" @click="saveSettings" :disabled="isSaving || isLoading || !!loadError">
          {{ isSaving ? i18nStore.t('frontend.subscriptions.saving') : i18nStore.t('frontend.subscriptions.save') }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(15, 23, 42, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--card-bg, #ffffff);
  border-radius: 16px;
  width: 90%;
  max-width: 520px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 25px 50px rgba(15, 23, 42, 0.25);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 24px 0;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: var(--text, #1e293b);
}

.modal-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.25rem;
  color: var(--text-secondary, #64748b);
  padding: 4px 8px;
  border-radius: 8px;
}

.modal-close:hover {
  background: var(--border, #e2e8f0);
}

.modal-body {
  padding: 24px;
  display: grid;
  gap: 16px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 0 24px 24px;
}

/* Toggle switch wrapper (replaces nested label) */
.toggle-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text, #1e293b);
  font-weight: 700;
}

.toggle-label-text {
  flex: 1;
}

.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--border, #e2e8f0);
  transition: 0.3s;
  border-radius: 24px;
}

.slider::before {
  position: absolute;
  content: '';
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background: #ffffff;
  transition: 0.3s;
  border-radius: 50%;
}

.switch input:checked + .slider {
  background: var(--primary, #4f46e5);
}

.switch input:checked + .slider::before {
  transform: translateX(20px);
}

/* Inline loading state */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 0;
  color: var(--text-secondary, #64748b);
}

.spinner {
  width: 22px;
  height: 22px;
  border: 3px solid var(--border, #e2e8f0);
  border-top-color: var(--primary, #4f46e5);
  border-radius: 999px;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Existing field styles */
label {
  display: grid;
  gap: 8px;
  color: var(--text-secondary, #64748b);
  font-weight: 700;
}

input,
select {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 10px;
  padding: 11px 12px;
  color: var(--text, #1e293b);
  font: inherit;
  background: var(--card-bg, #ffffff);
}

input:focus,
select:focus {
  border-color: var(--primary, #4f46e5);
  outline: 3px solid rgb(79 70 229 / 15%);
}

.field-help {
  font-size: 0.8rem;
  font-weight: 400;
  color: var(--text-secondary, #64748b);
  margin-top: -4px;
}

/* Warning days */
.warning-days-container {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.day-check {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 400;
  color: var(--text, #1e293b);
  cursor: pointer;
}

.day-check input[type="checkbox"] {
  width: auto;
  cursor: pointer;
}

.custom-day-input {
  display: flex;
  gap: 4px;
  align-items: center;
}

.custom-day-input input {
  width: 120px;
  padding: 6px 8px;
}

.custom-day-input .button-sm {
  padding: 6px 10px;
}

.warning-days-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: var(--primary, #4f46e5);
  font-size: 0.85rem;
  font-weight: 600;
}

.tag-remove {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.75rem;
  color: var(--primary, #4f46e5);
  padding: 0 2px;
  line-height: 1;
}

.tag-remove:hover {
  color: var(--danger, #ef4444);
}

/* Alert */
.alert {
  border-radius: 12px;
  padding: 12px 14px;
  font-weight: 700;
}

.alert-error {
  border: 1px solid rgb(239 68 68 / 30%);
  background: rgb(239 68 68 / 10%);
  color: #b91c1c;
}

/* Button styles */
.button {
  cursor: pointer;
  border: 0;
  border-radius: 10px;
  padding: 10px 16px;
  font: inherit;
  font-weight: 700;
}

.button-sm {
  padding: 6px 12px;
  font-size: 0.85rem;
  border: 1px solid var(--border, #e2e8f0);
  background: var(--card-bg, #ffffff);
  color: var(--text, #1e293b);
}

.button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.button-primary {
  background: var(--primary, #4f46e5);
  color: #ffffff;
}

.button-secondary {
  border: 1px solid var(--border, #e2e8f0);
  background: var(--card-bg, #ffffff);
  color: var(--text, #1e293b);
}

@media (max-width: 720px) {
  .modal {
    width: 95%;
    max-width: 100%;
  }

  .modal-footer .button {
    width: 100%;
  }
}
</style>
