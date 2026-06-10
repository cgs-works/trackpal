<script setup>
import { ref, watch, computed } from 'vue'
import api from '../../services/api'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

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
  <Dialog :open="isOpen" @update:open="(v) => !v && emit('close')">
    <DialogContent data-testid="subscription-form-dialog" class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>
          {{ props.sub ? t('frontend.subscriptions.edit_title') || 'Edit Subscription' : t('frontend.subscriptions.new_title') || 'New Subscription' }}
        </DialogTitle>
      </DialogHeader>

      <form @submit.prevent="handleSave" class="flex flex-col gap-4 text-sm">
        <div class="grid grid-cols-2 gap-4">
          <!-- Client select -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.client') }}</label>
            <select v-model="formData.client_id" required class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3 outline-none">
              <option value="" disabled>{{ t('frontend.subscriptions.select_client') || 'Select Client' }}</option>
              <option v-for="c in clients" :key="c.id" :value="c.id">{{ c.full_name }} ({{ c.phone }})</option>
            </select>
          </div>

          <!-- Service select -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.service') }}</label>
            <select v-model="formData.service_id" required class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3 outline-none">
              <option value="" disabled>{{ t('frontend.subscriptions.select_service') || 'Select Service' }}</option>
              <option v-for="s in services" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <!-- Plan select -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.plan') }}</label>
            <select v-model="formData.plan_id" required class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3 outline-none">
              <option value="" disabled>{{ t('frontend.subscriptions.select_plan') || 'Select Plan' }}</option>
              <option v-for="p in availablePlans" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>

          <!-- Email -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.email') }}</label>
            <Input v-model="formData.streaming_email" type="email" required />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <!-- Password toggle trigger -->
          <div class="flex flex-col gap-1.5 justify-end">
            <button
              v-if="!showPassword"
              @click="showPassword = true"
              type="button"
              class="inline-flex h-9 items-center justify-center rounded-md border border-border bg-card px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground transition-colors cursor-pointer"
            >
              🔑 {{ props.sub ? (t('frontend.subscriptions.update_password') || 'Update Password') : (t('frontend.subscriptions.set_password') || 'Set Password') }}
            </button>
            <div v-else class="flex flex-col gap-1.5 w-full">
              <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.password') }}</label>
              <Input v-model="formData.streaming_password" type="text" />
            </div>
          </div>

          <!-- Start Date -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.start') }}</label>
            <Input v-model="formData.starts_at" type="date" required />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <!-- Duration Select -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.duration') || 'Duration' }}</label>
            <select v-model="formData.duration_type" required class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3 outline-none">
              <option value="" disabled>{{ t('frontend.subscriptions.select_duration') || 'Select Duration' }}</option>
              <option v-for="opt in durationOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>

          <!-- Custom expiration -->
          <div v-if="isCustomDuration" class="flex flex-col gap-1.5">
            <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.end') }}</label>
            <Input v-model="formData.expires_at" type="date" required />
          </div>
        </div>

        <!-- Profile details toggle -->
        <div class="border-t border-border pt-4 mt-2">
          <button
            v-if="!showProfile"
            @click="showProfile = true"
            type="button"
            class="text-sm font-semibold text-primary hover:underline cursor-pointer"
          >
            + {{ t('frontend.subscriptions.add_profile') || 'Add Profile Details (Screens / PIN)' }}
          </button>
          <div v-else class="grid grid-cols-2 gap-4">
            <div class="flex flex-col gap-1.5">
              <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.profile_name') || 'Profile Name' }}</label>
              <Input v-model="formData.profile_name" type="text" :placeholder="t('frontend.subscriptions.profile_name_placeholder') || 'e.g. Profile 1'" />
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.profile_pin') || 'Profile PIN' }}</label>
              <Input v-model="formData.profile_pin" type="text" :placeholder="t('frontend.subscriptions.profile_pin_placeholder') || 'e.g. 1234'" />
            </div>
          </div>
        </div>
      </form>

      <DialogFooter class="gap-2">
        <Button variant="outline" @click="emit('close')" type="button">
          {{ t('frontend.subscriptions.cancel_action') || 'Cancel' }}
        </Button>
        <Button @click="handleSave" :disabled="isSaving" type="button">
          <span v-if="isSaving" class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-1.5"></span>
          {{ props.sub ? (t('frontend.subscriptions.save_changes') || 'Save Changes') : (t('frontend.subscriptions.create') || 'Create Subscription') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
