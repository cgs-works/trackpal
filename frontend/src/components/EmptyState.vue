<script setup>
defineProps({
  title: { type: String, default: 'No data' },
  description: { type: String, default: '' },
})
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-2 rounded-xl border border-border bg-card px-6 py-12 text-center shadow-sm">
    <h2 class="text-base font-medium text-foreground">{{ title }}</h2>
    <p v-if="description" class="max-w-sm text-sm text-muted-foreground">{{ description }}</p>
    <div v-if="$slots.actions" class="mt-2">
      <slot name="actions" />
    </div>
  </div>
</template>
