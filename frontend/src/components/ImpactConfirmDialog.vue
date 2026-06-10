<script setup>
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, required: true },
  description: { type: String, required: true },
  targetName: { type: String, default: '' },
  impacts: { type: Array, default: () => [] },
  confirmLabel: { type: String, default: 'Confirm' },
  cancelLabel: { type: String, default: 'Cancel' },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:open', 'confirm'])
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>{{ title }}</DialogTitle>
        <DialogDescription>{{ description }}</DialogDescription>
      </DialogHeader>

      <div class="space-y-3">
        <div v-if="targetName" class="rounded-lg border border-border bg-background p-3">
          <p class="text-xs text-muted-foreground">Target</p>
          <p class="text-sm font-medium text-foreground">{{ targetName }}</p>
        </div>

        <div v-if="impacts.length" class="rounded-lg border border-destructive/40 bg-destructive/10 p-3">
          <p class="text-xs font-medium uppercase tracking-[0.16em] text-destructive">Impact</p>
          <dl class="mt-2 space-y-2">
            <div v-for="impact in impacts" :key="impact.label" class="flex items-center justify-between gap-3 text-sm">
              <dt class="text-muted-foreground">{{ impact.label }}</dt>
              <dd class="font-medium text-foreground">{{ impact.value }}</dd>
            </div>
          </dl>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" :disabled="loading" @click="emit('update:open', false)">{{ cancelLabel }}</Button>
        <Button data-testid="impact-confirm" variant="destructive" :disabled="loading" @click="emit('confirm')">
          {{ loading ? 'Working…' : confirmLabel }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
