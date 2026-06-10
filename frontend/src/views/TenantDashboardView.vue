<script setup>
import { onMounted, ref } from 'vue'
import { useI18nStore } from '../stores/i18n'
import DashboardLayout from '../components/DashboardLayout.vue'
import ClientManagementPanel from '../components/ClientManagementPanel.vue'
import CatalogPanel from '../components/CatalogPanel.vue'
import MailboxConfigPanel from '../components/MailboxConfigPanel.vue'
import CodeServicesTenantPanel from '../components/CodeServicesTenantPanel.vue'

const i18nStore = useI18nStore()
const activeTab = ref('clients')
</script>

<template>
  <DashboardLayout>
    <div class="mb-6">
      <span class="text-xs font-semibold text-stone-400 dark:text-zinc-500 uppercase tracking-wider">Tenant Panel</span>
      <h1 class="text-xl font-bold tracking-tight text-stone-900 dark:text-zinc-100 mt-0.5">
        {{ i18nStore.t('frontend.tenant.title') || 'Tenant Dashboard' }}
      </h1>
    </div>

    <!-- Premium Tab Selectors -->
    <div class="flex gap-2 border-b border-stone-200 dark:border-zinc-800 mb-6">
      <button
        v-for="tab in ['clients', 'catalog', 'mailbox', 'codes']"
        :key="tab"
        @click="activeTab = tab"
        :class="[
          activeTab === tab
            ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
            : 'border-transparent text-stone-500 hover:text-stone-700 dark:text-zinc-400 dark:hover:text-zinc-200',
          'px-4 py-2 text-sm font-medium border-b-2 transition-all cursor-pointer'
        ]"
      >
        <span class="capitalize">{{ tab }}</span>
      </button>
    </div>

    <!-- Inner panels rendering inside our Linear container grid -->
    <div class="bg-white dark:bg-zinc-900 border border-stone-200 dark:border-zinc-800 rounded-md p-6 shadow-sm">
      <ClientManagementPanel v-if="activeTab === 'clients'" />
      <CatalogPanel v-else-if="activeTab === 'catalog'" />
      <MailboxConfigPanel v-else-if="activeTab === 'mailbox'" />
      <CodeServicesTenantPanel v-else-if="activeTab === 'codes'" />
    </div>
  </DashboardLayout>
</template>
