<template>
  <div>
    <NuxtLoadingIndicator color="#7A1F35" :height="3" :duration="1800" />
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <Toaster position="bottom-right" :duration="2600" />
  </div>
</template>

<script setup lang="ts">
import { Toaster } from 'vue-sonner'
</script>
