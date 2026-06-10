<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  clients: { type: Array, required: true },
  services: { type: Array, required: true },
  t: { type: Function, required: true },
  initialFilters: {
    type: Object,
    default: () => ({ status: '', client_id: '', service_id: '', expires_from: '', expires_to: '' }),
  },
})

const emit = defineEmits(['apply', 'clear'])

const filters = ref({
  status: '',
  client_id: '',
  service_id: '',
  expires_from: '',
  expires_to: ''
})

watch(
  () => props.initialFilters,
  (value) => {
    filters.value = {
      status: value?.status || '',
      client_id: value?.client_id || '',
      service_id: value?.service_id || '',
      expires_from: value?.expires_from || '',
      expires_to: value?.expires_to || '',
    }
  },
  { deep: true, immediate: true },
)

function applyFilters() {
  emit('apply', { ...filters.value })
}

function clearFilters() {
  filters.value = {
    status: '',
    client_id: '',
    service_id: '',
    expires_from: '',
    expires_to: ''
  }
  emit('clear')
}

function setQuickFilter(key) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  if (key === 'this_week') {
    const end = new Date(today)
    end.setDate(end.getDate() + 7)
    filters.value.expires_from = today.toISOString().split('T')[0]
    filters.value.expires_to = end.toISOString().split('T')[0]
  } else if (key === 'this_month') {
    const end = new Date(today)
    end.setMonth(end.getMonth() + 1)
    filters.value.expires_from = today.toISOString().split('T')[0]
    filters.value.expires_to = end.toISOString().split('T')[0]
  } else if (key === 'expired') {
    filters.value.expires_to = today.toISOString().split('T')[0]
    filters.value.expires_from = ''
  }
  applyFilters()
}
</script>

<template>
  <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md p-5 mb-6 shadow-sm">
    <div class="flex items-center justify-between border-b border-stone-100 dark:border-zinc-800/60 pb-3 mb-4">
      <div>
        <span class="text-xs font-semibold text-stone-400 dark:text-zinc-500 uppercase tracking-wider">{{ t('frontend.subscriptions.filters') }}</span>
        <h2 class="text-sm font-bold text-stone-900 dark:text-zinc-100 mt-0.5">{{ t('frontend.subscriptions.search') }}</h2>
      </div>
      <button
        @click="clearFilters"
        type="button"
        class="text-xs font-medium text-stone-500 hover:text-indigo-600 dark:text-zinc-400 dark:hover:text-indigo-400 transition-colors cursor-pointer"
      >
        {{ t('frontend.subscriptions.clear_filters') }}
      </button>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- Status Filter -->
      <div class="flex flex-col gap-1.5">
        <label class="text-xs font-semibold text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.status') }}</label>
        <select
          v-model="filters.status"
          class="px-3 py-2 text-xs bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none focus:border-indigo-500 transition-all cursor-pointer"
        >
          <option value="">{{ t('frontend.subscriptions.status_all_active') }}</option>
          <option value="active">{{ t('frontend.subscriptions.status_active') }}</option>
          <option value="expired">{{ t('frontend.subscriptions.status_expired') }}</option>
          <option value="cancelled">{{ t('frontend.subscriptions.status_cancelled') }}</option>
        </select>
      </div>

      <!-- Client Filter -->
      <div class="flex flex-col gap-1.5">
        <label class="text-xs font-semibold text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.client') }}</label>
        <select
          data-testid="filter-client"
          v-model="filters.client_id"
          class="px-3 py-2 text-xs bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none focus:border-indigo-500 transition-all cursor-pointer"
        >
          <option value="">{{ t('frontend.subscriptions.client') }}s</option>
          <option v-for="c in clients" :key="c.id" :value="c.id">{{ c.full_name }}</option>
        </select>
      </div>

      <!-- Service Filter -->
      <div class="flex flex-col gap-1.5">
        <label class="text-xs font-semibold text-stone-500 dark:text-zinc-400">{{ t('frontend.subscriptions.service') }}</label>
        <select
          v-model="filters.service_id"
          class="px-3 py-2 text-xs bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-800 dark:text-zinc-200 focus:outline-none focus:border-indigo-500 transition-all cursor-pointer"
        >
          <option value="">{{ t('frontend.subscriptions.service') }}s</option>
          <option v-for="s in services" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>
    </div>

    <!-- Quick Filters and Dates -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 border-t border-stone-100 dark:border-zinc-800/60 pt-4">
      <div class="flex flex-wrap gap-2 items-center">
        <span class="text-xs font-semibold text-stone-500 dark:text-zinc-400 mr-2">{{ t('frontend.subscriptions.status') }}:</span>
        <button
          @click="setQuickFilter('this_week')"
          type="button"
          class="px-2.5 py-1 text-xs bg-stone-100 hover:bg-stone-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-stone-700 dark:text-zinc-200 rounded font-medium transition-all cursor-pointer"
        >
          {{ t('frontend.subscriptions.quick_this_week') }}
        </button>
        <button
          @click="setQuickFilter('this_month')"
          type="button"
          class="px-2.5 py-1 text-xs bg-stone-100 hover:bg-stone-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-stone-700 dark:text-zinc-200 rounded font-medium transition-all cursor-pointer"
        >
          {{ t('frontend.subscriptions.quick_this_month') }}
        </button>
        <button
          @click="setQuickFilter('expired')"
          type="button"
          class="px-2.5 py-1 text-xs bg-stone-100 hover:bg-stone-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-stone-700 dark:text-zinc-200 rounded font-medium transition-all cursor-pointer"
        >
          {{ t('frontend.subscriptions.quick_expired') }}
        </button>
      </div>

      <div class="flex items-center gap-2 md:justify-end">
        <div class="flex items-center gap-1.5">
          <label class="text-[10px] font-bold text-stone-400 dark:text-zinc-500 uppercase">{{ t('frontend.subscriptions.filter_from') }}</label>
          <input
            v-model="filters.expires_from"
            type="date"
            class="px-2 py-1 text-xs bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded text-stone-800 dark:text-zinc-200 focus:outline-none"
          />
        </div>
        <span class="text-stone-400">—</span>
        <div class="flex items-center gap-1.5">
          <label class="text-[10px] font-bold text-stone-400 dark:text-zinc-500 uppercase">{{ t('frontend.subscriptions.filter_to') }}</label>
          <input
            v-model="filters.expires_to"
            type="date"
            class="px-2 py-1 text-xs bg-stone-50 dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded text-stone-800 dark:text-zinc-200 focus:outline-none"
          />
        </div>
        <button
          @click="applyFilters"
          type="button"
          class="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold cursor-pointer transition-colors ml-2"
        >
          {{ t('frontend.subscriptions.apply') }}
        </button>
      </div>
    </div>
  </div>
</template>
