<script setup>
import { Button } from '@/components/ui/button'

const props = defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  fields: { type: Array, default: () => [] },
  editLabel: { type: String, default: 'Edit' },
  canEdit: { type: Boolean, default: true },
})

defineEmits(['edit'])
</script>

<template>
  <aside class="rounded-xl border border-primary bg-card p-4 shadow-2xl shadow-black/20">
    <div class="flex items-start justify-between gap-3">
      <div>
        <h2 class="text-sm font-semibold tracking-tight text-foreground">{{ title }}</h2>
        <p v-if="description" class="mt-1 text-xs text-muted-foreground">{{ description }}</p>
      </div>
      <Button v-if="canEdit" data-testid="inspector-edit" size="sm" variant="outline" @click="$emit('edit')">
        {{ editLabel }}
      </Button>
    </div>

    <dl class="mt-4 space-y-3">
      <div v-for="field in fields" :key="field.label" class="rounded-lg border border-border bg-background p-3">
        <dt class="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">{{ field.label }}</dt>
        <dd class="mt-1 text-sm text-foreground">{{ field.value || '—' }}</dd>
      </div>
    </dl>

    <slot />
  </aside>
</template>
