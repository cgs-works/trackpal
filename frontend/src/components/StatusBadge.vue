<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  variant: { type: String, default: 'neutral' },
  label: { type: String, required: true },
})

const classes = computed(() => {
  const map = {
    active: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    inactive: 'border-border bg-muted text-muted-foreground',
    expired: 'border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300',
    cancelled: 'border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300',
    neutral: 'border-border bg-muted text-muted-foreground',
  }

  return cn('inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium', map[props.variant] || map.neutral)
})
</script>

<template>
  <span :class="classes">{{ label }}</span>
</template>
