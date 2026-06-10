<script setup>
import { ref, watch } from 'vue'
import api from '../../services/api'

const props = defineProps({
  isOpen: { type: Boolean, required: true },
  sub: { type: Object, default: null },
  t: { type: Function, required: true }
})

const emit = defineEmits(['close', 'save'])

const clients = ref([])
const plans = ref([])
const formData = ref({
  client_id: '',
  plan_id: '',
  status: 'active',
  profile_name: '',
  profile_pin: '',
  streaming_password: '',
  expiration_override: ''
})

watch(() => props.isOpen, async (open) => {
  if (open) {
    try {
      const [clientsRes, plansRes] = await Promise.all([
        api.get('/admin/clients'),
        api.get('/admin/plans')
      ])
      clients.value = clientsRes.data
      plans.value = plansRes.data
    } catch (err) {
      console.error('Failed to load modal options', err)
    }

    if (props.sub) {
      formData.value = { ...props.sub }
    } else {
      formData.value = {
        client_id: '',
        plan_id: '',
        status: 'active',
        profile_name: '',
        profile_pin: '',
        streaming_password: '',
        expiration_override: ''
      }
    }
  }
})

async function handleSave() {
  try {
    if (props.sub) {
      await api.put(`/admin/subscriptions/${props.sub.id}`, formData.value)
    } else {
      await api.post('/admin/subscriptions', formData.value)
    }
    emit('save')
  } catch (err) {
    console.error('Failed to save subscription', err)
  }
}
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
    <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md w-full max-w-lg p-6 shadow-md transition-all">
      <div class="flex items-center justify-between border-b border-stone-100 dark:border-zinc-800/60 pb-3 mb-4">
        <h3 class="text-base font-bold text-stone-900 dark:text-zinc-100">
          {{ props.sub ? t('frontend.subscriptions.edit_title') : t('frontend.subscriptions.new_title') }}
        </h3>
        <button @click="emit('close')" class="text-stone-400 hover:text-stone-600 dark:text-zinc-500 dark:hover:text-zinc-300">✕</button>
      </div>

      <form @submit.prevent="handleSave" class="flex flex-col gap-4">
        <div class="grid grid-cols-2 gap-4">
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.client') }}</label>
            <select v-model="formData.client_id" required class="px-3 py-2 text-sm bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md">
              <option value="" disabled>Select Client</option>
              <option v-for="c in clients" :key="c.id" :value="c.id">{{ c.name }} ({{ c.phone }})</option>
            </select>
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.plan') }}</label>
            <select v-model="formData.plan_id" required class="px-3 py-2 text-sm bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md">
              <option value="" disabled>Select Plan</option>
              <option v-for="p in plans" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium text-stone-500 dark:text-zinc-400">Password</label>
            <input v-model="formData.streaming_password" type="text" class="px-3 py-2 text-sm bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md">
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs font-medium text-stone-500 dark:text-zinc-400">Status</label>
            <select v-model="formData.status" required class="px-3 py-2 text-sm bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md">
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
            </select>
          </div>
        </div>

        <div class="flex justify-end gap-2 border-t border-stone-100 dark:border-zinc-800/60 pt-4 mt-2">
          <button @click="emit('close')" type="button" class="px-4 py-2 text-sm text-stone-500 dark:text-zinc-400 hover:bg-stone-50 dark:hover:bg-zinc-800/50 rounded-md transition-colors cursor-pointer">Cancel</button>
          <button type="submit" class="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-medium rounded-md transition-colors cursor-pointer">Save</button>
        </div>
      </form>
    </div>
  </div>
</template>
