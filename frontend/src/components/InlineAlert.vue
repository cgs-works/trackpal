<script setup>
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  variant: { type: String, default: 'info' },
  message: { type: String, required: true },
})

const classes = computed(() => {
  const map = {
    info: 'border-border bg-muted text-foreground',
    success: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
    error: 'border-red-500/20 bg-red-500/10 text-red-800 dark:text-red-200',
  }
  return cn('rounded-md border px-3 py-2 text-sm', map[props.variant] || map.info)
})
</script>

<template>
  <p :class="classes">{{ message }}</p>
</template>
