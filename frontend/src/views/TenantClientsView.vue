<script setup>
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'
import ClientManagementPanel from '@/components/ClientManagementPanel.vue'
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Clients" description="Create, update, activate, and remove client access." />
      <ClientManagementPanel />
    </div>
  </DashboardLayout>
</template>
