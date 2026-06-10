<script setup>
import { ref } from 'vue'
import api from '../../services/api'

/**
 * @typedef {Object} Subscription
 * @property {string} id - The UUID of the subscription
 * @property {string} client_id - Client UUID
 * @property {string} client_name - Pre-fetched client full name or phone
 * @property {string} client_phone - Client phone number
 * @property {string} service_id - Service UUID
 * @property {string} plan_id - Plan UUID
 * @property {string} plan_name - Pre-fetched plan name
 * @property {string} starts_at - Subscription start ISO date string
 * @property {string} expires_at - Subscription expiration ISO date string
 * @property {string} status - Subscription status (active/expired/cancelled)
 * @property {string} streaming_email - Login email for streaming account
 * @property {boolean} has_password - If the streaming account has a password
 * @property {string} [profile_name] - Optional Netflix/HBO profile name
 * @property {string} [profile_pin] - Optional profile PIN
 */

const props = defineProps({
  subscriptions: { type: Array, required: true },
  clients: { type: Array, required: true },
  services: { type: Array, required: true },
  planMap: { type: Object, required: true },
  t: { type: Function, required: true },
  selectedId: { type: [Number, String, null], default: null },
})

const emit = defineEmits(['select', 'edit', 'renew', 'reactivate', 'cancel'])

const revealedRowId = ref(null)
const revealedCredentials = ref({})
let revealTimer = null

/**
 * Reveal streaming credentials from the backend secure store
 * @param {string} subId - The ID of the subscription
 */
async function revealCredentials(subId) {
  if (revealedRowId.value === subId) {
    hideRevealed()
    return
  }
  hideRevealed()

  revealedRowId.value = subId
  try {
    const res = await api.get(`/subscriptions/${subId}/reveal`)
    revealedCredentials.value = { ...revealedCredentials.value, [subId]: res.data }

    // Auto-hide credentials after 10 seconds to keep secure
    revealTimer = setTimeout(() => {
      hideRevealed()
    }, 10000)
  } catch (error) {
    revealedRowId.value = null
    console.error('Failed to reveal credentials', error)
  }
}

function hideRevealed() {
  if (revealTimer) {
    clearTimeout(revealTimer)
    revealTimer = null
  }
  if (revealedRowId.value) {
    const id = revealedRowId.value
    const copy = { ...revealedCredentials.value }
    delete copy[id]
    revealedCredentials.value = copy
    revealedRowId.value = null
  }
}

/**
 * Format ISO date string into standard dd/mm/yyyy localized form
 * @param {string} dateStr - ISO date string
 * @returns {string} Standard localized date format
 */
function formatDate(dateStr) {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  return date.toLocaleDateString('es-ES', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

function getClientName(clientId) {
  const client = props.clients.find((c) => c.id === clientId)
  return client ? client.full_name : clientId
}

function getServiceName(serviceId) {
  const service = props.services.find((s) => s.id === serviceId)
  return service ? service.name : serviceId
}

function getPlanName(planId) {
  return props.planMap[planId] || planId
}
</script>

<template>
  <div class="overflow-x-auto border border-border rounded-md bg-card shadow-sm">
    <table class="w-full text-left text-sm border-collapse">
      <thead>
        <tr class="bg-secondary border-b border-border text-muted-foreground font-medium text-xs">
          <th class="p-3">{{ t('frontend.subscriptions.client') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.service') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.plan') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.email') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.password') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.pin') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.status') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.start') }}</th>
          <th class="p-3">{{ t('frontend.subscriptions.end') }}</th>
          <th class="p-3 text-right">{{ t('frontend.subscriptions.actions') }}</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border text-xs">
        <tr
          v-for="sub in subscriptions"
          :key="sub.id"
          :data-testid="`subscription-row-${sub.id}`"
          :class="selectedId === sub.id ? 'bg-accent border-ring' : 'hover:hover:bg-accent'"
          class="cursor-pointer text-foreground transition-colors"
          @click="emit('select', sub)"
        >
          <td class="p-3 font-medium text-foreground">
            {{ getClientName(sub.client_id) }}
          </td>
          <td class="p-3">
            {{ getServiceName(sub.service_id) }}
          </td>
          <td class="p-3">
            <span class="px-2 py-0.5 font-semibold rounded bg-primary/10 text-primary border border-primary/20">
              {{ getPlanName(sub.plan_id) }}
            </span>
          </td>
          <td class="p-3 font-mono text-muted-foreground">
            {{ sub.streaming_email || '—' }}
          </td>
          <td class="p-3">
            <div v-if="sub.has_password" class="flex items-center gap-1.5">
              <span class="font-mono bg-background px-2 py-1 rounded border border-border">
                <template v-if="revealedRowId === sub.id && revealedCredentials[sub.id]">
                  {{ revealedCredentials[sub.id].streaming_password }}
                </template>
                <template v-else>******</template>
              </span>
              <button
                @click="revealCredentials(sub.id)"
                type="button"
                class="p-1 rounded hover:hover:bg-accent text-muted-foreground transition-colors cursor-pointer"
                :title="revealedRowId === sub.id ? t('frontend.subscriptions.hide') : t('frontend.subscriptions.reveal')"
              >
                👁️
              </button>
            </div>
            <span v-else class="text-muted-foreground">—</span>
          </td>
          <td class="p-3 font-mono">
            <span v-if="sub.profile_name" class="font-medium text-foreground">
              {{ sub.profile_name }} <span v-if="sub.profile_pin" class="text-muted-foreground">({{ sub.profile_pin }})</span>
            </span>
            <span v-else class="text-muted-foreground">—</span>
          </td>
          <td class="p-3">
            <span :class="[
              sub.status === 'active' ? 'bg-green-950/20 text-green-400 border-green-900/40' : 
              sub.status === 'expired' ? 'bg-amber-950/20 text-amber-400 border-amber-900/40' :
              'bg-red-950/20 text-red-400 border-red-900/40',
              'px-2 py-0.5 font-semibold rounded border uppercase text-[10px] tracking-wider'
            ]">
              {{ sub.status }}
            </span>
          </td>
          <td class="p-3 text-muted-foreground font-mono">{{ formatDate(sub.starts_at) }}</td>
          <td class="p-3 text-muted-foreground font-mono">{{ formatDate(sub.expires_at) }}</td>
          <td class="p-3 text-right">
            <div class="flex items-center justify-end gap-1">
              <button
                v-if="sub.status === 'active'"
                :data-testid="`subscription-edit-${sub.id}`"
                @click.stop="emit('edit', sub)"
                type="button"
                class="p-1.5 rounded hover:hover:bg-accent text-muted-foreground transition-colors cursor-pointer"
                :title="t('frontend.subscriptions.edit')"
              >
                ✏️
              </button>
              <button
                v-if="sub.status === 'active'"
                @click.stop="emit('renew', sub)"
                type="button"
                class="px-2 py-1 text-[10px] font-bold bg-primary/10 text-primary rounded hover:bg-primary/20 transition-colors cursor-pointer"
                :title="t('frontend.subscriptions.renew')"
              >
                🔄 {{ t('frontend.subscriptions.renew') }}
              </button>
              <button
                v-if="sub.status !== 'active'"
                @click.stop="emit('reactivate', sub)"
                type="button"
                class="px-2 py-1 text-[10px] font-bold bg-green-950/30 text-green-400 rounded hover:bg-green-900/30 transition-colors cursor-pointer"
                :title="t('frontend.subscriptions.reactivate')"
              >
                ⚡ {{ t('frontend.subscriptions.reactivate') }}
              </button>
              <button
                v-if="sub.status === 'active'"
                @click.stop="emit('cancel', sub)"
                type="button"
                class="p-1.5 rounded hover:bg-red-950/30 text-red-400 transition-colors cursor-pointer"
                :title="t('frontend.subscriptions.cancel')"
              >
                🛑
              </button>
            </div>
          </td>
        </tr>
        <tr v-if="subscriptions.length === 0">
          <td colspan="10" class="p-8 text-center text-muted-foreground font-medium">
            {{ t('frontend.subscriptions.no_subscriptions') || 'No subscriptions found.' }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
