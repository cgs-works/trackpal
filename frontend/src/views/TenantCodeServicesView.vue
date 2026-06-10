<script setup>
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'
import CodeServicesTenantPanel from '@/components/CodeServicesTenantPanel.vue'
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Code Services" description="Select which lookup services are active for this tenant." />
      <CodeServicesTenantPanel />
    </div>
  </DashboardLayout>
</template>
