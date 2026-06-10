<script setup>
import { ref, watch, computed } from 'vue'
import api from '../../services/api'

/**
 * @typedef {Object} SubscriptionModalProps
 * @property {boolean} isOpen - Whether the modal is open or closed
 * @property {Object} [sub] - Subscription object if in edit mode
 * @property {Array<Object>} clients - Clients list
 * @property {Array<Object>} services - Services list
 * @property {Function} t - Translation dictionary method
 */

const props = defineProps({
  isOpen: { type: Boolean, required: true },
  sub: { type: Object, default: null },
  clients: { type: Array, required: true },
  services: { type: Array, required: true },
  t: { type: Function, required: true }
})

const emit = defineEmits(['close', 'save'])

const availablePlans = ref([])
const showPassword = ref(false)
const showProfile = ref(false)
const isSaving = ref(false)

const formData = ref({
  client_id: '',
  service_id: '',
  plan_id: '',
  streaming_email: '',
  streaming_password: '',
  starts_at: '',
  duration_type: '',
  expires_at: '',
  profile_name: '',
  profile_pin: ''
})

const durationOptions = computed(() => [
  { value: '1_month', label: props.t('frontend.subscriptions.duration_1_month') || '1 Month' },
  { value: '3_months', label: props.t('frontend.subscriptions.duration_3_months') || '3 Months' },
  { value: '6_months', label: props.t('frontend.subscriptions.duration_6_months') || '6 Months' },
  { value: '9_months', label: props.t('frontend.subscriptions.duration_9_months') || '9 Months' },
  { value: '1_year', label: props.t('frontend.subscriptions.duration_1_year') || '1 Year' },
  { value: 'custom', label: props.t('frontend.subscriptions.duration_custom') || 'Custom' }
])

const isCustomDuration = computed(() => formData.value.duration_type === 'custom')

// Watch open state to populate values
watch(() => props.isOpen, (open) => {
  if (open) {
    if (props.sub) {
      formData.value = {
        client_id: props.sub.client_id || '',
        service_id: props.sub.service_id || '',
        plan_id: props.sub.plan_id || '',
        streaming_email: props.sub.streaming_email || '',
        streaming_password: props.sub.streaming_password || '',
        starts_at: props.sub.starts_at ? props.sub.starts_at.split('T')[0] : '',
        duration_type: props.sub.duration_type || '',
        expires_at: props.sub.expires_at ? props.sub.expires_at.split('T')[0] : '',
        profile_name: props.sub.profile_name || '',
        profile_pin: props.sub.profile_pin || ''
      }
      showPassword.value = false
      showProfile.value = !!(props.sub.profile_name || props.sub.profile_pin)
      if (props.sub.service_id) {
        loadPlans(props.sub.service_id)
      }
    } else {
      formData.value = {
        client_id: '',
        service_id: '',
        plan_id: '',
        streaming_email: '',
        streaming_password: '',
        starts_at: new Date().toISOString().split('T')[0],
        duration_type: '',
        expires_at: '',
        profile_name: '',
        profile_pin: ''
      }
      availablePlans.value = []
      showPassword.value = false
      showProfile.value = false
    }
  }
})

// Watch service_id to fetch plans dynamically
watch(() => formData.value.service_id, (newVal) => {
  if (!props.sub || (props.sub && newVal !== props.sub.service_id)) {
    formData.value.plan_id = ''
  }
  if (newVal) {
    loadPlans(newVal)
  } else {
    availablePlans.value = []
  }
})

async function loadPlans(serviceId) {
  try {
    const res = await api.get(`/catalog/services/${serviceId}/plans`)
    availablePlans.value = res.data || []
  } catch (err) {
    console.error('Failed to load plans', err)
    availablePlans.value = []
  }
}

async function handleSave() {
  isSaving.value = true
  try {
    const payload = {
      client_id: formData.value.client_id,
      service_id: formData.value.service_id,
      plan_id: formData.value.plan_id,
      streaming_email: formData.value.streaming_email,
      streaming_password: formData.value.streaming_password || undefined,
      starts_at: formData.value.starts_at || new Date().toISOString().split('T')[0],
      duration_type: formData.value.duration_type,
      expires_at: formData.value.duration_type === 'custom' ? formData.value.expires_at : undefined,
      profile_name: formData.value.profile_name || undefined,
      profile_pin: formData.value.profile_pin || undefined
    }

    if (props.sub) {
      await api.put(`/subscriptions/${props.sub.id}`, payload)
    } else {
      await api.post('/subscriptions', payload)
    }
    emit('save')
  } catch (err) {
    console.error('Failed to save subscription', err)
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
    <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md w-full max-w-lg p-6 shadow-md transition-all">
      <div class="flex items-center justify-between border-b border-stone-100 dark:border-zinc-800/60 pb-3 mb-4">
        <h3 class="text-sm font-bold text-stone-900 dark:text-zinc-100">
          {{ props.sub ? t('frontend.subscriptions.edit_title') || 'Editar Suscripción' : t('frontend.subscriptions.new_title') || 'Nueva Suscripción' }}
        </h3>
        <button @click="emit('close')" type="button" class="text-stone-400 hover:text-stone-600 dark:text-zinc-500 dark:hover:text-zinc-300">✕</button>
      </div>

      <form @submit.prevent="handleSave" class="flex flex-col gap-4 text-xs">
        <div class="grid grid-cols-2 gap-4">
          <!-- Client select -->
          <div class="flex flex-col gap-1.5">
            <label class="font-semibold text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.client') }}</label>
            <select v-model="formData.client_id" required class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
              <option value="" disabled>Select Client</option>
              <option v-for="c in clients" :key="c.id" :value="c.id">{{ c.full_name }} ({{ c.phone }})</option>
            </select>
          </div>

          <!-- Service select -->
          <div class="flex flex-col gap-1.5">
            <label class="font-semibold text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.service') }}</label>
            <select v-model="formData.service_id" required class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
              <option value="" disabled>Select Service</option>
              <option v-for="s in services" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <!-- Plan select -->
          <div class="flex flex-col gap-1.5">
            <label class="font-semibold text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.plan') }}</label>
            <select v-model="formData.plan_id" required class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
              <option value="" disabled>Select Plan</option>
              <option v-for="p in availablePlans" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>

          <!-- Email -->
          <div class="flex flex-col gap-1.5">
            <label class="font-semibold text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.email') }}</label>
            <input v-model="formData.streaming_email" type="email" required class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <!-- Password toggle trigger -->
          <div class="flex flex-col gap-1.5 justify-end">
            <button
              v-if="!showPassword"
              @click="showPassword = true"
              type="button"
              class="px-3 py-2 text-center bg-stone-100 hover:bg-stone-200 dark:bg-zinc-800 dark:hover:bg-zinc-750 text-stone-700 dark:text-zinc-200 rounded-md transition-colors cursor-pointer"
            >
              🔑 {{ props.sub ? 'Actualizar Contraseña' : 'Establecer Contraseña' }}
            </button>
            <div v-else class="flex flex-col gap-1.5 w-full">
              <label class="font-semibold text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.password') }}</label>
              <input v-model="formData.streaming_password" type="text" class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
            </div>
          </div>

          <!-- Start Date -->
          <div class="flex flex-col gap-1.5">
            <label class="font-semibold text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.start') }}</label>
            <input v-model="formData.starts_at" type="date" required class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <!-- Duration Select -->
          <div class="flex flex-col gap-1.5">
            <label class="font-semibold text-stone-500 dark:text-zinc-400">Duración</label>
            <select v-model="formData.duration_type" required class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
              <option value="" disabled>Seleccionar duración</option>
              <option v-for="opt in durationOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>

          <!-- Custom expiration -->
          <div v-if="isCustomDuration" class="flex flex-col gap-1.5">
            <label class="font-semibold text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.end') }}</label>
            <input v-model="formData.expires_at" type="date" required class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
          </div>
        </div>

        <!-- Profile details toggle -->
        <div class="border-t border-stone-100 dark:border-zinc-800/60 pt-4 mt-2">
          <button
            v-if="!showProfile"
            @click="showProfile = true"
            type="button"
            class="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
          >
            + Añadir detalles de Perfil (Pantallas / PIN)
          </button>
          <div v-else class="grid grid-cols-2 gap-4">
            <div class="flex flex-col gap-1.5">
              <label class="font-semibold text-stone-500 dark:text-zinc-400">Nombre de Perfil</label>
              <input v-model="formData.profile_name" type="text" placeholder="Ej. Perfil 1" class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="font-semibold text-stone-500 dark:text-zinc-400">PIN de Perfil</label>
              <input v-model="formData.profile_pin" type="text" placeholder="Ej. 1234" class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none">
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-2 border-t border-stone-100 dark:border-zinc-800/60 pt-4 mt-2">
          <button @click="emit('close')" type="button" class="px-4 py-2 text-stone-500 dark:text-zinc-400 hover:bg-stone-50 dark:hover:bg-zinc-800/50 rounded-md transition-colors cursor-pointer">Cancelar</button>
          <button :disabled="isSaving" type="submit" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold rounded-md transition-colors cursor-pointer flex items-center gap-1.5 disabled:opacity-55">
            <span v-if="isSaving" class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            {{ props.sub ? 'Guardar Cambios' : 'Crear Suscripción' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
