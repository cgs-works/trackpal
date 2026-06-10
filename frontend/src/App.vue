<script setup>
import 'vue-sonner/style.css'
import { Toaster } from '@/components/ui/sonner'
</script>

<template>
  <router-view />
  <Toaster class="pointer-events-auto" rich-colors close-button />
</template>
