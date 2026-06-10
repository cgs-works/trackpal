<script setup>
import { onMounted, ref } from 'vue'
import { useI18nStore } from '../stores/i18n'
import api from '../services/api'
import DashboardLayout from '../components/DashboardLayout.vue'
import SubscriptionTable from '../components/subscriptions/SubscriptionTable.vue'
import SubscriptionModal from '../components/subscriptions/SubscriptionModal.vue'

const i18nStore = useI18nStore()
const subscriptions = ref([])
const isModalOpen = ref(false)
const selectedSub = ref(null)

async function fetchSubscriptions() {
  try {
    const res = await api.get('/admin/subscriptions')
    subscriptions.value = res.data
  } catch (err) {
    console.error('Failed to fetch subscriptions', err)
  }
}

function openNewModal() {
  selectedSub.value = null
  isModalOpen.value = true
}

function openEditModal(sub) {
  selectedSub.value = sub
  isModalOpen.value = true
}

async function handleDelete(subId) {
  if (confirm(i18nStore.t('frontend.subscriptions.delete_confirm') || 'Are you sure you want to delete this subscription?')) {
    try {
      await api.delete(`/admin/subscriptions/${subId}`)
      await fetchSubscriptions()
    } catch (err) {
      console.error('Failed to delete subscription', err)
    }
  }
}

function handleSave() {
  isModalOpen.value = false
  fetchSubscriptions()
}

onMounted(() => {
  fetchSubscriptions()
})
</script>

<template>
  <DashboardLayout>
    <div class="flex items-center justify-between mb-6">
      <div>
        <span class="text-xs font-semibold text-stone-400 dark:text-zinc-500 uppercase tracking-wider">Trackpal Console</span>
        <h1 class="text-xl font-bold tracking-tight text-stone-900 dark:text-zinc-100 mt-0.5">
          {{ i18nStore.t('frontend.subscriptions.title') }}
        </h1>
      </div>
      <button
        @click="openNewModal"
        class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-sm font-medium rounded-md shadow-sm transition-colors cursor-pointer"
      >
        {{ i18nStore.t('frontend.subscriptions.new') || '+ New Subscription' }}
      </button>
    </div>

    <SubscriptionTable
      :subscriptions="subscriptions"
      :t="i18nStore.t"
      @edit="openEditModal"
      @delete="handleDelete"
    />

    <SubscriptionModal
      :isOpen="isModalOpen"
      :sub="selectedSub"
      :t="i18nStore.t"
      @close="isModalOpen = false"
      @save="handleSave"
    />
  </DashboardLayout>
</template>
