<script setup>
import { ref, watch } from 'vue'
import api from '../../services/api'

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
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
    <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md w-full max-w-md p-6 shadow-md transition-all">
      <div class="flex items-center justify-between border-b border-stone-100 dark:border-zinc-800/60 pb-3 mb-4">
        <h3 class="text-sm font-bold text-red-600 dark:text-red-400 flex items-center gap-1.5">
          🛑 Cancelar Suscripción
        </h3>
        <button @click="emit('close')" type="button" class="text-stone-400 hover:text-stone-600 dark:text-zinc-500 dark:hover:text-zinc-300">✕</button>
      </div>

      <form @submit.prevent="handleCancel" class="flex flex-col gap-4 text-xs">
        <p class="text-stone-600 dark:text-zinc-400">
          ¿Estás seguro de que deseas cancelar esta suscripción? Esta acción suspenderá el acceso del cliente de forma inmediata.
        </p>

        <div class="flex flex-col gap-1.5">
          <label class="font-semibold text-stone-500 dark:text-zinc-400">Notas de Cancelación (Opcional)</label>
          <textarea
            v-model="cancelNotes"
            rows="3"
            placeholder="Introduce los motivos de la cancelación..."
            class="px-3 py-2 bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none focus:border-red-500 resize-none"
          ></textarea>
        </div>

        <div class="flex justify-end gap-2 border-t border-stone-100 dark:border-zinc-800/60 pt-4 mt-2">
          <button @click="emit('close')" type="button" class="px-4 py-2 text-stone-500 dark:text-zinc-400 hover:bg-stone-50 dark:hover:bg-zinc-800/50 rounded-md transition-colors cursor-pointer">Mantener Activa</button>
          <button :disabled="isSaving" type="submit" class="px-4 py-2 bg-red-600 hover:bg-red-500 active:bg-red-700 text-white font-semibold rounded-md transition-colors cursor-pointer flex items-center gap-1.5 disabled:opacity-55">
            <span v-if="isSaving" class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            Confirmar Cancelación
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
