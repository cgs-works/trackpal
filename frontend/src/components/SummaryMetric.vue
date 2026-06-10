<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  hint: { type: String, default: '' },
  tone: { type: String, default: 'neutral' },
})

const toneClasses = computed(() => ({
  neutral: 'text-foreground',
  success: 'text-success',
  warning: 'text-warning',
  destructive: 'text-destructive',
  accent: 'text-primary',
}[props.tone] || 'text-foreground'))
</script>

<template>
  <section class="rounded-xl border border-border bg-card p-4">
    <p class="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">{{ label }}</p>
    <p :class="cn('mt-2 text-2xl font-semibold tracking-tight', toneClasses)">{{ value }}</p>
    <p v-if="hint" class="mt-1 text-xs text-muted-foreground">{{ hint }}</p>
  </section>
</template>
