<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useI18nStore } from '../stores/i18n'
import DashboardLayout from '../components/DashboardLayout.vue'

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
    <!-- Premium header -->
    <div class="mb-6">
      <span class="text-xs font-semibold text-stone-400 dark:text-zinc-500 uppercase tracking-wider">
        {{ i18nStore.t('frontend.client.title') || 'Client Portal' }}
      </span>
      <h1 class="text-xl font-bold tracking-tight text-stone-900 dark:text-zinc-100 mt-0.5">
        {{ i18nStore.t('frontend.client.title') || 'Client Dashboard' }}
      </h1>
    </div>

    <!-- Loading state -->
    <div v-if="isLoading" class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md p-10 shadow-sm flex items-center justify-center gap-3 text-stone-500 dark:text-zinc-400">
      <span class="w-5 h-5 border-2 border-stone-200 dark:border-zinc-700 border-t-indigo-500 rounded-full animate-spin" aria-hidden="true"></span>
      <span class="text-sm font-medium">{{ i18nStore.t('frontend.dashboard.loading') }}</span>
    </div>

    <template v-else>
      <!-- Error alert -->
      <div v-if="errorMessage" class="mb-4 text-xs font-medium text-red-500 bg-red-50 dark:bg-red-950/20 border border-red-200/30 dark:border-red-950/40 rounded px-3 py-2">{{ errorMessage }}</div>

      <!-- Welcome card -->
      <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md p-6 shadow-sm mb-4">
        <span class="text-xs font-semibold text-stone-400 dark:text-zinc-500 uppercase tracking-wider">{{ i18nStore.t('frontend.dashboard.client.role_label') }}</span>
        <h2 class="text-lg font-bold tracking-tight text-stone-900 dark:text-zinc-100 mt-1">{{ i18nStore.t('frontend.dashboard.client.welcome', { name: displayName }) }}</h2>
        <p class="mt-1 text-sm text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.dashboard.client.readonly') }}</p>
      </div>

      <!-- Access Information -->
      <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md p-6 shadow-sm mb-4">
        <div class="border-b border-stone-100 dark:border-zinc-800/60 pb-3 mb-4">
          <span class="text-xs font-semibold text-stone-400 dark:text-zinc-500 uppercase tracking-wider">{{ i18nStore.t('frontend.dashboard.client.access_info') }}</span>
          <h2 class="text-base font-bold text-stone-900 dark:text-zinc-100 mt-0.5">{{ i18nStore.t('frontend.dashboard.client.access_info') }}</h2>
        </div>

        <dl class="grid grid-cols-2 gap-x-6 gap-y-3">
          <div>
            <dt class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.dashboard.client.uuid') }}</dt>
            <dd class="text-sm font-mono text-stone-900 dark:text-zinc-100 mt-0.5">{{ clientInfo.id }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.profile.full_name') }}</dt>
            <dd class="text-sm text-stone-900 dark:text-zinc-100 mt-0.5">{{ clientInfo.full_name }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.dashboard.client.login') }}</dt>
            <dd class="text-sm font-mono text-stone-900 dark:text-zinc-100 mt-0.5">{{ clientInfo.username }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.profile.phone') }}</dt>
            <dd class="text-sm text-stone-900 dark:text-zinc-100 mt-0.5">{{ clientInfo.phone || '—' }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.dashboard.client.tenant') }}</dt>
            <dd class="text-sm text-stone-900 dark:text-zinc-100 mt-0.5">{{ clientInfo.tenant_name }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.dashboard.client.prefix') }}</dt>
            <dd class="text-sm font-mono text-stone-900 dark:text-zinc-100 mt-0.5">{{ clientInfo.client_prefix }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.subscriptions.status') }}</dt>
            <dd class="text-sm mt-0.5">
              <span :class="[
                clientInfo.is_active
                  ? 'bg-green-50 dark:bg-green-950/30 text-green-600 dark:text-green-400 border-green-200/30 dark:border-green-950/40'
                  : 'bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 border-red-200/30 dark:border-red-950/40',
                'px-2 py-0.5 text-xs font-semibold rounded border'
              ]">
                {{ clientInfo.is_active ? i18nStore.t('frontend.dashboard.client.status_active') : i18nStore.t('frontend.dashboard.client.status_inactive') }}
              </span>
            </dd>
          </div>
        </dl>
      </div>

      <!-- Subscriptions -->
      <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md shadow-sm mb-4">
        <div class="px-6 pt-5 pb-3 border-b border-stone-100 dark:border-zinc-800/60">
          <span class="text-xs font-semibold text-stone-400 dark:text-zinc-500 uppercase tracking-wider">{{ i18nStore.t('frontend.dashboard.client.subscriptions') }}</span>
          <h2 class="text-base font-bold text-stone-900 dark:text-zinc-100 mt-0.5">{{ i18nStore.t('frontend.dashboard.client.subscriptions') }}</h2>
          <p class="text-xs text-stone-500 dark:text-zinc-400 mt-0.5">{{ i18nStore.t('frontend.dashboard.client.subscriptions_desc') }}</p>
        </div>

        <div v-if="!clientInfo.subscriptions || !clientInfo.subscriptions.length" class="px-6 py-8 text-center text-sm text-stone-400 dark:text-zinc-500">
          {{ i18nStore.t('frontend.dashboard.client.no_subscriptions') }}
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-sm border-collapse">
            <thead>
              <tr class="bg-stone-50 dark:bg-zinc-900/50 border-b border-stone-200 dark:border-zinc-800 text-stone-500 dark:text-zinc-400 font-medium">
                <th class="p-3">{{ i18nStore.t('frontend.dashboard.client.service') }}</th>
                <th class="p-3">{{ i18nStore.t('frontend.dashboard.client.plan') }}</th>
                <th class="p-3">{{ i18nStore.t('frontend.subscriptions.status') }}</th>
                <th class="p-3">{{ i18nStore.t('frontend.dashboard.client.start') }}</th>
                <th class="p-3">{{ i18nStore.t('frontend.dashboard.client.expiry') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-stone-100 dark:divide-zinc-800/40">
              <tr v-for="sub in clientInfo.subscriptions" :key="sub.id" class="hover:bg-stone-50/50 dark:hover:bg-zinc-800/20 text-stone-800 dark:text-zinc-200 transition-colors">
                <td class="p-3 font-medium text-stone-900 dark:text-zinc-100">{{ sub.service_name }}</td>
                <td class="p-3">{{ sub.plan_name }}</td>
                <td class="p-3">
                  <span :class="[
                    sub.status === 'active'
                      ? 'bg-green-50 dark:bg-green-950/30 text-green-600 dark:text-green-400 border-green-200/30 dark:border-green-950/40'
                      : 'bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 border-red-200/30 dark:border-red-950/40',
                    'px-2 py-0.5 text-xs font-semibold rounded border uppercase tracking-wider'
                  ]">
                    {{ sub.status }}
                  </span>
                </td>
                <td class="p-3 text-stone-500 dark:text-zinc-400 text-xs">{{ formatDate(sub.starts_at) }}</td>
                <td class="p-3 text-stone-500 dark:text-zinc-400 text-xs">{{ formatDate(sub.expires_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Change Password -->
      <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md p-6 shadow-sm mb-4">
        <div class="border-b border-stone-100 dark:border-zinc-800/60 pb-3 mb-4">
          <span class="text-xs font-semibold text-stone-400 dark:text-zinc-500 uppercase tracking-wider">{{ i18nStore.t('frontend.dashboard.client.security') }}</span>
          <h2 class="text-base font-bold text-stone-900 dark:text-zinc-100 mt-0.5">{{ i18nStore.t('frontend.dashboard.client.change_password') }}</h2>
        </div>

        <div v-if="passwordSuccess" class="mb-4 text-xs font-medium text-green-600 bg-green-50 dark:bg-green-950/20 border border-green-200/30 dark:border-green-950/40 rounded px-3 py-2">{{ passwordSuccess }}</div>

        <form @submit.prevent="changePassword" class="flex flex-col gap-4 max-w-md">
          <div class="flex flex-col gap-1">
            <label for="current-password" class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.dashboard.client.current_password') }}</label>
            <input id="current-password" v-model="passwordForm.old_password" type="password" autocomplete="current-password" required class="px-3 py-2 text-sm bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
          </div>
          <div class="flex flex-col gap-1">
            <label for="new-password" class="text-xs font-medium text-stone-500 dark:text-zinc-400">{{ i18nStore.t('frontend.dashboard.client.new_password') }}</label>
            <input id="new-password" v-model="passwordForm.new_password" type="password" autocomplete="new-password" required class="px-3 py-2 text-sm bg-white dark:bg-zinc-950 border border-stone-200 dark:border-zinc-800 rounded-md text-stone-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
          </div>
          <div class="flex justify-end">
            <button type="submit" :disabled="isSavingPassword" class="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium rounded-md shadow-sm transition-colors cursor-pointer disabled:cursor-not-allowed">
              {{ isSavingPassword ? i18nStore.t('frontend.dashboard.client.updating') : i18nStore.t('frontend.dashboard.client.update_password') }}
            </button>
          </div>
        </form>
      </div>
    </template>
  </DashboardLayout>
</template>
