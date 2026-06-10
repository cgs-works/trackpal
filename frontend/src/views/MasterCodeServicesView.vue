<script setup>
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'
import CodeServicesGlobalPanel from '@/components/CodeServicesGlobalPanel.vue'
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Code Services" description="Manage global code services." />
      <CodeServicesGlobalPanel />
    </div>
  </DashboardLayout>
</template>
