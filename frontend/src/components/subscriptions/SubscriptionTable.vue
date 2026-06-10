<script setup>
import { ref } from 'vue'
import api from '../../services/api'

const props = defineProps({
  subscriptions: { type: Array, required: true },
  t: { type: Function, required: true }
})

const emit = defineEmits(['edit', 'delete'])

const revealedRowId = ref(null)
const revealedCredentials = ref({})

async function revealCredentials(subId) {
  if (revealedRowId.value === subId) {
    revealedRowId.value = null
    return
  }

  try {
    const res = await api.get(`/admin/subscriptions/${subId}/credentials`)
    revealedCredentials.value[subId] = res.data
    revealedRowId.value = subId
  } catch (error) {
    console.error('Failed to reveal credentials', error)
  }
}
</script>

<template>
  <div class="overflow-x-auto border border-stone-200 dark:border-zinc-800 rounded-md bg-white dark:bg-zinc-900 shadow-sm">
    <table class="w-full text-left text-sm border-collapse">
      <thead>
        <tr class="bg-stone-50 dark:bg-zinc-900/50 border-b border-stone-200 dark:border-zinc-800 text-stone-500 dark:text-zinc-400 font-medium">
          <th class="p-3">ID</th>
          <th class="p-3">{{ t('frontend.subscriptions.client') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.plan') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.streaming_credentials') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.status') }}</th>
          <th class="p-3 text-right">{{ t('frontend.subscriptions.actions') }}</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-stone-100 dark:divide-zinc-800/40">
        <tr v-for="sub in subscriptions" :key="sub.id" class="hover:bg-stone-50/50 dark:hover:bg-zinc-800/20 text-stone-800 dark:text-zinc-200 transition-colors">
          <td class="p-3 font-mono text-xs">{{ sub.id }}</td>
          <td class="p-3">
            <div class="font-medium text-stone-900 dark:text-zinc-100">{{ sub.client_name }}</div>
            <div class="text-xs text-stone-400 dark:text-zinc-500 font-mono">{{ sub.client_phone }}</div>
          </td>
          <td class="p-3">
            <span class="px-2 py-0.5 text-xs font-semibold rounded bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 border border-indigo-200/30 dark:border-indigo-950/40">
              {{ sub.plan_name }}
            </span>
          </td>
          <td class="p-3">
            <div v-if="sub.has_password" class="flex items-center gap-1.5">
              <span class="font-mono text-xs bg-stone-50 dark:bg-zinc-950 px-2 py-1 rounded border border-stone-200/50 dark:border-zinc-800/50">
                <template v-if="revealedRowId === sub.id">
                  {{ revealedCredentials[sub.id]?.streaming_password || '***' }}
                </template>
                <template v-else>******</template>
              </span>
              <button
                @click="revealCredentials(sub.id)"
                class="p-1 rounded hover:bg-stone-100 dark:hover:bg-zinc-800 text-stone-400 dark:text-zinc-500 transition-colors cursor-pointer"
                :title="revealedRowId === sub.id ? t('frontend.subscriptions.hide') : t('frontend.subscriptions.reveal')"
              >
                👁️
              </button>
            </div>
            <span v-else class="text-xs text-stone-400 dark:text-zinc-600">—</span>
          </td>
          <td class="p-3">
            <span :class="[
              sub.status === 'active' ? 'bg-green-50 dark:bg-green-950/30 text-green-600 dark:text-green-400 border-green-200/30 dark:border-green-950/40' : 'bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 border-red-200/30 dark:border-red-950/40',
              'px-2 py-0.5 text-xs font-semibold rounded border uppercase tracking-wider'
            ]">
              {{ sub.status }}
            </span>
          </td>
          <td class="p-3 text-right">
            <div class="flex items-center justify-end gap-1">
              <button @click="emit('edit', sub)" class="p-1.5 rounded hover:bg-stone-100 dark:hover:bg-zinc-800 text-stone-500 dark:text-zinc-400 transition-colors cursor-pointer" title="Edit">
                ✏️
              </button>
              <button @click="emit('delete', sub.id)" class="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-950/30 text-red-500 dark:text-red-400 transition-colors cursor-pointer" title="Delete">
                🗑️
              </button>
            </div>
          </td>
        </tr>
        <tr v-if="subscriptions.length === 0">
          <td colspan="6" class="p-8 text-center text-stone-400 dark:text-zinc-600 font-medium">
            No subscriptions found.
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
