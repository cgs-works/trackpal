<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'
import InlineAlert from '@/components/InlineAlert.vue'

const router = useRouter()
const authStore = useAuthStore()
const isSupportMode = computed(() => authStore.role === 'master' && !!authStore.activeTenantId)

const cards = computed(() => {
  const items = [
    { title: 'Clients', to: '/admin/clients', body: 'Create, edit, activate, and deactivate client access.' },
    { title: 'Catalog', to: '/admin/catalog', body: 'Manage services, plans, and delete-preview flows.' },
    { title: 'Subscriptions', to: '/admin/subscriptions', body: 'Create, renew, cancel, and reveal credentials.' },
    { title: 'Mailbox', to: '/admin/mailbox', body: 'Configure OAuth or IMAP mailbox access.' },
    { title: 'Code Services', to: '/admin/code-services', body: 'Choose which lookup services are active.' },
  ]

  if (!isSupportMode.value) {
    items.push({ title: 'Settings', to: '/admin/settings', body: 'Update tenant profile, locale, and password.' })
  }

  return items
})
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Overview" description="Choose the area you want to work in." />
      <InlineAlert
        v-if="isSupportMode"
        variant="info"
        message="You are browsing this tenant in support mode. Profile settings stay on the master account and are intentionally hidden here."
      />
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <button
          v-for="card in cards"
          :key="card.to"
          type="button"
          class="rounded-xl border border-border bg-card p-5 text-left shadow-sm transition-colors hover:bg-muted/40"
          @click="router.push(card.to)"
        >
          <div class="space-y-1">
            <h2 class="text-base font-medium">{{ card.title }}</h2>
            <p class="text-sm text-muted-foreground">{{ card.body }}</p>
          </div>
        </button>
      </div>
    </div>
  </DashboardLayout>
</template>
