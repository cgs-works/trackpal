<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'
import DashboardLayout from '../components/DashboardLayout.vue'
import PageHeader from '../components/PageHeader.vue'
import InlineAlert from '../components/InlineAlert.vue'
import StatusBadge from '../components/StatusBadge.vue'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableEmpty,
} from '@/components/ui/table'

const authStore = useAuthStore()
const i18nStore = useI18nStore()

const dashboard = ref(null)
const profile = ref(null)
const passwordForm = ref({
  old_password: '',
  new_password: '',
})
const isLoading = ref(false)
const isSavingPassword = ref(false)
const errorMessage = ref('')
const passwordSuccess = ref('')

const username = computed(() => authStore.username || authStore.user?.username || 'Cliente')
const clientInfo = computed(() => dashboard.value || profile.value || {})
const displayName = computed(() => clientInfo.value.full_name || username.value)

function getApiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  }
  return detail || error.response?.data?.message || fallback
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return isNaN(d.getTime()) ? dateStr : d.toLocaleDateString()
}

async function loadDashboard() {
  errorMessage.value = ''
  isLoading.value = true

  try {
    const [dashboardResponse, profileResponse] = await Promise.all([
      api.get('/dashboard'),
      api.get('/me'),
    ])
    dashboard.value = dashboardResponse.data || null
    profile.value = profileResponse.data || null
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.dashboard.error_load'))
  } finally {
    isLoading.value = false
  }
}

async function changePassword() {
  errorMessage.value = ''
  passwordSuccess.value = ''
  isSavingPassword.value = true

  try {
    await api.put('/me/password', passwordForm.value)
    passwordForm.value = {
      old_password: '',
      new_password: '',
    }
    passwordSuccess.value = i18nStore.t('frontend.dashboard.client.password_updated')
  } catch (error) {
    errorMessage.value = getApiError(error, i18nStore.t('frontend.dashboard.client.error_password'))
  } finally {
    isSavingPassword.value = false
  }
}

onMounted(loadDashboard)
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader :title="i18nStore.t('frontend.client.title') || 'Client Dashboard'" />

      <InlineAlert v-if="errorMessage" variant="error" :message="errorMessage" />
      <InlineAlert v-if="passwordSuccess" variant="success" :message="passwordSuccess" class="mb-4" />

      <!-- Loading state -->
      <div v-if="isLoading" class="flex items-center justify-center gap-3 py-10 rounded-xl border bg-card text-card-foreground shadow-sm">
        <span class="w-5 h-5 border-2 border-border border-t-primary rounded-full animate-spin" aria-hidden="true"></span>
        <span class="text-sm font-medium text-muted-foreground">{{ i18nStore.t('frontend.dashboard.loading') }}</span>
      </div>

      <template v-else>
        <!-- Welcome card -->
        <div class="rounded-xl border bg-card text-card-foreground shadow-sm p-6">
          <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{{ i18nStore.t('frontend.dashboard.client.role_label') }}</span>
          <h2 class="text-lg font-bold tracking-tight text-foreground mt-1">{{ i18nStore.t('frontend.dashboard.client.welcome', { name: displayName }) }}</h2>
          <p class="mt-1 text-sm text-muted-foreground">{{ i18nStore.t('frontend.dashboard.client.readonly') }}</p>
        </div>

        <!-- Access Information -->
        <div class="rounded-xl border bg-card text-card-foreground shadow-sm p-6">
          <div class="border-b border-border pb-3 mb-4">
            <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{{ i18nStore.t('frontend.dashboard.client.access_info') }}</span>
            <h2 class="text-base font-bold text-foreground mt-0.5">{{ i18nStore.t('frontend.dashboard.client.access_info') }}</h2>
          </div>

          <dl class="grid grid-cols-2 gap-x-6 gap-y-3">
            <div>
              <dt class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.dashboard.client.uuid') }}</dt>
              <dd class="text-sm font-mono text-foreground mt-0.5">{{ clientInfo.id }}</dd>
            </div>
            <div>
              <dt class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.profile.full_name') }}</dt>
              <dd class="text-sm text-foreground mt-0.5">{{ clientInfo.full_name }}</dd>
            </div>
            <div>
              <dt class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.dashboard.client.login') }}</dt>
              <dd class="text-sm font-mono text-foreground mt-0.5">{{ clientInfo.username }}</dd>
            </div>
            <div>
              <dt class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.profile.phone') }}</dt>
              <dd class="text-sm text-foreground mt-0.5">{{ clientInfo.phone || '—' }}</dd>
            </div>
            <div>
              <dt class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.dashboard.client.tenant') }}</dt>
              <dd class="text-sm text-foreground mt-0.5">{{ clientInfo.tenant_name }}</dd>
            </div>
            <div>
              <dt class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.dashboard.client.prefix') }}</dt>
              <dd class="text-sm font-mono text-foreground mt-0.5">{{ clientInfo.client_prefix }}</dd>
            </div>
            <div>
              <dt class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.subscriptions.status') }}</dt>
              <dd class="text-sm mt-0.5">
                <StatusBadge
                  :variant="clientInfo.is_active ? 'active' : 'inactive'"
                  :label="clientInfo.is_active ? i18nStore.t('frontend.dashboard.client.status_active') : i18nStore.t('frontend.dashboard.client.status_inactive')"
                />
              </dd>
            </div>
          </dl>
        </div>

        <!-- Subscriptions -->
        <div class="rounded-xl border bg-card text-card-foreground shadow-sm">
          <div class="px-6 pt-5 pb-3 border-b border-border">
            <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{{ i18nStore.t('frontend.dashboard.client.subscriptions') }}</span>
            <h2 class="text-base font-bold text-foreground mt-0.5">{{ i18nStore.t('frontend.dashboard.client.subscriptions') }}</h2>
            <p class="text-xs text-muted-foreground mt-0.5">{{ i18nStore.t('frontend.dashboard.client.subscriptions_desc') }}</p>
          </div>

          <div v-if="!clientInfo.subscriptions || !clientInfo.subscriptions.length" class="flex items-center justify-center py-8 text-sm text-muted-foreground">
            {{ i18nStore.t('frontend.dashboard.client.no_subscriptions') }}
          </div>

          <Table v-else>
            <TableHeader>
              <TableRow>
                <TableHead>{{ i18nStore.t('frontend.dashboard.client.service') }}</TableHead>
                <TableHead>{{ i18nStore.t('frontend.dashboard.client.plan') }}</TableHead>
                <TableHead>{{ i18nStore.t('frontend.subscriptions.status') }}</TableHead>
                <TableHead>{{ i18nStore.t('frontend.dashboard.client.start') }}</TableHead>
                <TableHead>{{ i18nStore.t('frontend.dashboard.client.expiry') }}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="sub in clientInfo.subscriptions" :key="sub.id">
                <TableCell class="font-medium">{{ sub.service_name }}</TableCell>
                <TableCell>{{ sub.plan_name }}</TableCell>
                <TableCell>
                  <StatusBadge
                    :variant="sub.status === 'active' ? 'active' : 'inactive'"
                    :label="sub.status"
                  />
                </TableCell>
                <TableCell class="text-muted-foreground text-xs">{{ formatDate(sub.starts_at) }}</TableCell>
                <TableCell class="text-muted-foreground text-xs">{{ formatDate(sub.expires_at) }}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <!-- Security / Change Password -->
        <div class="rounded-xl border bg-card text-card-foreground shadow-sm p-6">
          <div class="border-b border-border pb-3 mb-4">
            <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{{ i18nStore.t('frontend.dashboard.client.security') }}</span>
            <h2 class="text-base font-bold text-foreground mt-0.5">{{ i18nStore.t('frontend.dashboard.client.security') }}</h2>
          </div>

          <form @submit.prevent="changePassword" class="flex flex-col gap-4 max-w-md">
            <div class="flex flex-col gap-1">
              <label for="current-password" class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.dashboard.client.current_password') }}</label>
              <input id="current-password" v-model="passwordForm.old_password" type="password" autocomplete="current-password" required class="px-3 py-2 text-sm bg-background border border-border rounded-md text-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary">
            </div>
            <div class="flex flex-col gap-1">
              <label for="new-password" class="text-xs font-medium text-muted-foreground">{{ i18nStore.t('frontend.dashboard.client.new_password') }}</label>
              <input id="new-password" v-model="passwordForm.new_password" type="password" autocomplete="new-password" required class="px-3 py-2 text-sm bg-background border border-border rounded-md text-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary">
            </div>
            <div class="flex justify-end">
              <button type="submit" :disabled="isSavingPassword" class="px-4 py-2 text-sm bg-primary hover:bg-primary/90 active:bg-primary/80 disabled:bg-primary/50 text-primary-foreground font-medium rounded-md shadow-sm transition-colors cursor-pointer disabled:cursor-not-allowed">
                {{ isSavingPassword ? i18nStore.t('frontend.dashboard.client.updating') : i18nStore.t('frontend.dashboard.client.update_password') }}
              </button>
            </div>
          </form>
        </div>
      </template>
    </div>
  </DashboardLayout>
</template>
