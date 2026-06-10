<script setup>
import { ref, watch, computed } from 'vue'
import api from '../../services/api'

const props = defineProps({
  isOpen: { type: Boolean, required: true },
  sub: { type: Object, default: null },
  t: { type: Function, required: true }
})

const emit = defineEmits(['close', 'save'])

const isSaving = ref(false)
const renewForm = ref({
  duration_type: '',
  expires_at: ''
})

const durationOptions = computed(() => [
  { value: '1_month', label: props.t('frontend.subscriptions.duration_1_month') || '1 Month' },
  { value: '3_months', label: props.t('frontend.subscriptions.duration_3_months') || '3 Months' },
  { value: '6_months', label: props.t('frontend.subscriptions.duration_6_months') || '6 Months' },
  { value: '9_months', label: props.t('frontend.subscriptions.duration_9_months') || '9 Months' },
  { value: '1_year', label: props.t('frontend.subscriptions.duration_1_year') || '1 Year' },
  { value: 'custom', label: props.t('frontend.subscriptions.duration_custom') || 'Custom' }
])

const isCustomDuration = computed(() => renewForm.value.duration_type === 'custom')

watch(() => props.isOpen, (open) => {
  if (open) {
    renewForm.value = {
      duration_type: '',
      expires_at: ''
    }
  }
})

async function handleRenew() {
  if (!props.sub) return
  isSaving.value = true
  try {
    const payload = {
      duration_type: renewForm.value.duration_type,
      expires_at: renewForm.value.duration_type === 'custom' ? renewForm.value.expires_at : undefined
    }
    await api.post(`/subscriptions/${props.sub.id}/renew`, payload)
    emit('save')
  } catch (err) {
    console.error('Failed to renew subscription', err)
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
    <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md w-full max-w-md p-6 shadow-md transition-all">
      <div class="flex items-center justify-between border-b border-stone-100 dark:border-zinc-800/60 pb-3 mb-4">
        <h3 class="text-sm font-bold text-stone-900 dark:text-zinc-100">
          🔄 Renovar Suscripción
        </h3>
        <button @click="emit('close')" type="button" class="text-stone-400 hover:text-stone-600 dark:text-zinc-500 dark:hover:text-zinc-300">✕</button>
      </div>

      <form @submit.prevent="handleRenew" class="flex flex-col gap-4 text-xs">
        <div class="flex flex-col gap-1.5">
          <label class="font-semibold text-stone-500 dark:text-zinc-400">Duración de la Renovación</label>
          <select v-model="renewForm.duration_type" required class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
            <option value="" disabled>Seleccionar duración</option>
            <option v-for="opt in durationOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>

        <div v-if="isCustomDuration" class="flex flex-col gap-1.5">
          <label class="font-semibold text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.end') }}</label>
          <input v-model="renewForm.expires_at" type="date" required class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
        </div>

        <div class="flex justify-end gap-2 border-t border-stone-100 dark:border-zinc-800/60 pt-4 mt-2">
          <button @click="emit('close')" type="button" class="px-4 py-2 text-stone-500 dark:text-zinc-400 hover:bg-stone-50 dark:hover:bg-zinc-800/50 rounded-md transition-colors cursor-pointer">Cancelar</button>
          <button :disabled="isSaving" type="submit" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold rounded-md transition-colors cursor-pointer flex items-center gap-1.5">
            <span v-if="isSaving" class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            Renovar
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
