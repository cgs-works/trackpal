<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'
import DashboardLayout from '../components/DashboardLayout.vue'
import SubscriptionFilters from '../components/subscriptions/SubscriptionFilters.vue'
import SubscriptionTable from '../components/subscriptions/SubscriptionTable.vue'
import SubscriptionModal from '../components/subscriptions/SubscriptionModal.vue'
import SubscriptionRenewModal from '../components/subscriptions/SubscriptionRenewModal.vue'
import SubscriptionReactivateModal from '../components/subscriptions/SubscriptionReactivateModal.vue'
import SubscriptionCancelModal from '../components/subscriptions/SubscriptionCancelModal.vue'
import ReminderSettingsModal from '../components/subscriptions/ReminderSettingsModal.vue'
import EntityInspector from '@/components/EntityInspector.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const i18nStore = useI18nStore()

const subscriptions = ref([])
const clients = ref([])
const services = ref([])
const planMap = ref({})
const isLoading = ref(false)
const errorMessage = ref('')

// Filter state
const activeFilters = ref({
  status: '',
  client_id: '',
  service_id: '',
  expires_from: '',
  expires_to: ''
})

// Modal visibility state
const isCreateEditOpen = ref(false)
const isRenewOpen = ref(false)
const isReactivateOpen = ref(false)
const isCancelOpen = ref(false)
const isReminderSettingsOpen = ref(false)

const selectedSub = ref(null)
const selectedSubscription = ref(null)

async function loadClients() {
  try {
    const res = await api.get('/clients')
    clients.value = res.data || []
  } catch (err) {
    console.error('Failed to load clients', err)
  }
}

async function loadServices() {
  try {
    const res = await api.get('/catalog/services')
    services.value = res.data || []
  } catch (err) {
    console.error('Failed to load services', err)
  }
}

async function buildPlanMap() {
  const map = {}
  for (const service of services.value) {
    try {
      const res = await api.get(`/catalog/services/${service.id}/plans`)
      const plans = res.data || []
      for (const p of plans) {
        map[p.id] = p.name
      }
    } catch (err) {
      console.error(`Failed to load plans for service ${service.id}`, err)
    }
  }
  planMap.value = map
}

async function fetchSubscriptions() {
  errorMessage.value = ''
  isLoading.value = true
  try {
    const params = {}
    if (activeFilters.value.status) params.status = activeFilters.value.status
    if (activeFilters.value.client_id) params.client_id = activeFilters.value.client_id
    if (activeFilters.value.service_id) params.service_id = activeFilters.value.service_id
    if (activeFilters.value.expires_from) params.expires_from = activeFilters.value.expires_from
    if (activeFilters.value.expires_to) params.expires_to = activeFilters.value.expires_to

    const res = await api.get('/subscriptions', { params })
    subscriptions.value = res.data || []
  } catch (err) {
    console.error('Failed to fetch subscriptions', err)
    errorMessage.value = i18nStore.t('frontend.subscriptions.error_load') || 'Error loading subscriptions.'
  } finally {
    isLoading.value = false
  }
}

function handleApplyFilters(filters) {
  activeFilters.value = filters
  fetchSubscriptions()
}

function handleClearFilters() {
  activeFilters.value = {
    status: '',
    client_id: '',
    service_id: '',
    expires_from: '',
    expires_to: ''
  }
  fetchSubscriptions()
}

function selectSubscription(subscription) {
  selectedSubscription.value = subscription
}

function openCreateModal() {
  selectedSub.value = null
  isCreateEditOpen.value = true
}

function openEditModal(sub) {
  selectedSub.value = sub
  isCreateEditOpen.value = true
}

function openRenewModal(sub) {
  selectedSub.value = sub
  isRenewOpen.value = true
}

function openReactivateModal(sub) {
  selectedSub.value = sub
  isReactivateOpen.value = true
}

function openCancelModal(sub) {
  selectedSub.value = sub
  isCancelOpen.value = true
}

function openEditFromInspector() {
  if (!selectedSubscription.value) return
  openEditModal(selectedSubscription.value)
}

function handleSave() {
  isCreateEditOpen.value = false
  isRenewOpen.value = false
  isReactivateOpen.value = false
  isCancelOpen.value = false
  fetchSubscriptions()
}

onMounted(async () => {
  authStore.loadTenantSettings().catch(() => {})
  await Promise.all([loadClients(), loadServices()])
  await buildPlanMap()

  if (route.query.client_id) {
    activeFilters.value.client_id = route.query.client_id
  }
  await fetchSubscriptions()
})
</script>

<template>
  <DashboardLayout>
    <div class="flex items-center justify-between mb-6">
      <div>
        <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Trackpal Console</span>
        <h1 class="text-xl font-bold tracking-tight text-foreground mt-0.5">
          {{ i18nStore.t('frontend.subscriptions.title') }} {{ subscriptions.length ? `(${subscriptions.length})` : '' }}
        </h1>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="openCreateModal"
          type="button"
          class="px-4 py-2 bg-primary hover:bg-primary/90 active:bg-primary/80 text-primary-foreground text-xs font-semibold rounded-md shadow-sm transition-colors cursor-pointer"
        >
          {{ i18nStore.t('frontend.subscriptions.new') || '+ New Subscription' }}
        </button>
        <button
          data-testid="reminder-settings-open"
          @click="isReminderSettingsOpen = true"
          type="button"
          class="px-3 py-2 bg-card hover:bg-accent border border-border text-foreground text-xs font-semibold rounded-md shadow-sm transition-colors cursor-pointer"
        >
          ⚙️ {{ i18nStore.t('frontend.subscriptions.reminder_settings') || 'Reminders' }}
        </button>
      </div>
    </div>

    <!-- Collapsible/Restructured Filters Component -->
    <SubscriptionFilters
      :clients="clients"
      :services="services"
      :t="i18nStore.t"
      :initial-filters="activeFilters"
      @apply="handleApplyFilters"
      @clear="handleClearFilters"
    />

    <!-- Error Banner -->
    <p v-if="errorMessage" class="mb-4 text-xs font-medium text-red-400 bg-red-950/20 border border-red-900/40 rounded px-3 py-2" role="alert">
      {{ errorMessage }}
    </p>

    <!-- Table or Loading state -->
    <div v-if="isLoading" class="flex flex-col items-center justify-center p-12 border border-border rounded-md bg-card">
      <span class="w-8 h-8 border-4 border-primary/30 border-t-primary rounded-full animate-spin"></span>
      <p class="text-xs text-muted-foreground mt-3 font-semibold">{{ i18nStore.t('frontend.subscriptions.loading') || 'Loading subscriptions...' }}</p>
    </div>

    <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <SubscriptionTable
        :subscriptions="subscriptions"
        :clients="clients"
        :services="services"
        :planMap="planMap"
        :t="i18nStore.t"
        :selected-id="selectedSubscription?.id"
        @select="selectSubscription"
        @edit="openEditModal"
        @renew="openRenewModal"
        @reactivate="openReactivateModal"
        @cancel="openCancelModal"
      />

      <EntityInspector
        v-if="selectedSubscription"
        data-testid="subscription-inspector"
        title="Subscription detail"
        :description="selectedSubscription.streaming_email"
        :fields="[
          { label: i18nStore.t('frontend.subscriptions.client'), value: selectedSubscription.client_name || selectedSubscription.client_id },
          { label: i18nStore.t('frontend.subscriptions.service'), value: selectedSubscription.service_name || selectedSubscription.service_id },
          { label: i18nStore.t('frontend.subscriptions.status'), value: selectedSubscription.status },
        ]"
        @edit="openEditFromInspector"
      />
    </div>

    <!-- Restructured Form Modal Component (Create/Edit) -->
    <SubscriptionModal
      :isOpen="isCreateEditOpen"
      :sub="selectedSub"
      :clients="clients"
      :services="services"
      :t="i18nStore.t"
      @close="isCreateEditOpen = false"
      @save="handleSave"
    />

    <!-- Renew Modal -->
    <SubscriptionRenewModal
      :isOpen="isRenewOpen"
      :sub="selectedSub"
      :t="i18nStore.t"
      @close="isRenewOpen = false"
      @save="handleSave"
    />

    <!-- Reactivate Modal -->
    <SubscriptionReactivateModal
      :isOpen="isReactivateOpen"
      :sub="selectedSub"
      :t="i18nStore.t"
      @close="isReactivateOpen = false"
      @save="handleSave"
    />

    <!-- Cancel Confirmation Modal -->
    <SubscriptionCancelModal
      :isOpen="isCancelOpen"
      :sub="selectedSub"
      :t="i18nStore.t"
      @close="isCancelOpen = false"
      @save="handleSave"
    />

    <!-- Automated Reminder Settings Modal -->
    <ReminderSettingsModal
      :isOpen="isReminderSettingsOpen"
      @close="isReminderSettingsOpen = false"
      @saved="handleSave"
    />
  </DashboardLayout>
</template>
