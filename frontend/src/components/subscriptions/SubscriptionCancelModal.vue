<script setup>
import { ref, watch } from 'vue'
import api from '../../services/api'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

const props = defineProps({
  isOpen: { type: Boolean, required: true },
  sub: { type: Object, default: null },
  t: { type: Function, required: true }
})

const emit = defineEmits(['close', 'save'])

const isSaving = ref(false)
const cancelNotes = ref('')

watch(() => props.isOpen, (open) => {
  if (open) {
    cancelNotes.value = ''
  }
})

async function handleCancel() {
  if (!props.sub) return
  isSaving.value = true
  try {
    await api.post(`/subscriptions/${props.sub.id}/cancel`, {
      notes: cancelNotes.value || ''
    })
    emit('save')
  } catch (err) {
    console.error('Failed to cancel subscription', err)
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <Dialog :open="isOpen" @update:open="(v) => !v && emit('close')">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-1.5 text-red-400">
          🛑 {{ t('frontend.subscriptions.cancel_title') || 'Cancel Subscription' }}
        </DialogTitle>
      </DialogHeader>

      <form @submit.prevent="handleCancel" class="flex flex-col gap-4 text-sm">
        <p class="text-muted-foreground">
          {{ t('frontend.subscriptions.cancel_confirm_text') || 'Are you sure you want to cancel this subscription? This will immediately suspend the client\'s access.' }}
        </p>

        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-muted-foreground">{{ t('frontend.subscriptions.cancel_notes') || 'Cancellation Notes (Optional)' }}</label>
          <textarea
            v-model="cancelNotes"
            rows="3"
            :placeholder="t('frontend.subscriptions.cancel_notes_placeholder') || 'Enter the reasons for cancellation...'"
            class="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3 outline-none resize-none"
          ></textarea>
        </div>
      </form>

      <DialogFooter class="gap-2">
        <Button variant="outline" @click="emit('close')" type="button">
          {{ t('frontend.subscriptions.keep_active') || 'Keep Active' }}
        </Button>
        <Button variant="destructive" @click="handleCancel" :disabled="isSaving" type="button">
          <span v-if="isSaving" class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-1.5"></span>
          {{ t('frontend.subscriptions.confirm_cancel') || 'Confirm Cancellation' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
