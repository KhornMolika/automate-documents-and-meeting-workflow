<script setup lang="ts">
import { Card } from '~/components/ui/card'
import { cn } from '~/lib/utils'

const props = defineProps<{ class?: any }>()
</script>

<template>
  <div :class="cn('space-y-4', props.class)" aria-busy="true" aria-live="polite">
    <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Card v-for="index in 4" :key="index" class="p-5">
        <div class="h-3 w-20 rounded bg-muted" />
        <div class="mt-3 h-7 w-12 rounded bg-muted" />
        <div class="mt-3 h-3 w-24 rounded bg-muted" />
      </Card>
    </div>
    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <Card class="p-5 xl:col-span-8">
        <div class="h-4 w-40 rounded bg-muted" />
        <div class="mt-4 h-3 w-full rounded bg-muted" />
        <div class="mt-2 h-3 w-4/5 rounded bg-muted" />
        <div class="mt-2 h-3 w-3/5 rounded bg-muted" />
      </Card>
      <Card class="p-5 xl:col-span-4">
        <div class="h-4 w-28 rounded bg-muted" />
        <div class="mt-4 h-3 w-full rounded bg-muted" />
        <div class="mt-2 h-3 w-4/5 rounded bg-muted" />
      </Card>
    </div>
  </div>
</template>
