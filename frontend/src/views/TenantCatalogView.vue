<script setup>
import DashboardLayout from '@/components/DashboardLayout.vue'
import PageHeader from '@/components/PageHeader.vue'
import CatalogPanel from '@/components/CatalogPanel.vue'
</script>

<template>
  <DashboardLayout>
    <div class="space-y-6">
      <PageHeader title="Catalog" description="Manage services, plans, and delete-preview flows." />
      <CatalogPanel />
    </div>
  </DashboardLayout>
</template>
