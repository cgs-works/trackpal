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
  <Dialog :open="isOpen" @update:open="(v) => !v && emit('close')">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>
          🔄 {{ t('frontend.subscriptions.renew_title') || 'Renew Subscription' }}
        </DialogTitle>
      </DialogHeader>

      <form @submit.prevent="handleRenew" class="flex flex-col gap-4 text-sm">
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.renew_duration') || 'Renewal Duration' }}</label>
          <select v-model="renewForm.duration_type" required class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3 outline-none">
            <option value="" disabled>{{ t('frontend.subscriptions.select_duration') || 'Select Duration' }}</option>
            <option v-for="opt in durationOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>

        <div v-if="isCustomDuration" class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.end') }}</label>
          <Input v-model="renewForm.expires_at" type="date" required />
        </div>
      </form>

      <DialogFooter class="gap-2">
        <Button variant="outline" @click="emit('close')" type="button">
          {{ t('frontend.subscriptions.cancel_action') || 'Cancel' }}
        </Button>
        <Button @click="handleRenew" :disabled="isSaving" type="button">
          <span v-if="isSaving" class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-1.5"></span>
          {{ t('frontend.subscriptions.renew') || 'Renew' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
