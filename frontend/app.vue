<template>
  <div>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <Toaster position="bottom-right" :duration="2600" />
  </div>
</template>

<script setup lang="ts">
import { Toaster } from 'vue-sonner'
</script>
