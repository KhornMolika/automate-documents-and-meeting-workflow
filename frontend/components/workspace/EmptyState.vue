<script setup lang="ts">
import { FileText } from 'lucide-vue-next'
import { cn } from '~/lib/utils'

const props = defineProps<{
  title: string
  description: string
  class?: any
}>()
</script>

<template>
  <div
    :class="
      cn(
        'flex min-h-[160px] flex-col items-start justify-center gap-1 rounded-lg border border-dashed border-input bg-card px-6 py-8',
        props.class,
      )
    "
  >
    <FileText class="mb-2 h-5 w-5 text-muted-foreground" />
    <p class="text-sm font-medium">{{ title }}</p>
    <p class="max-w-md text-[13px] leading-relaxed text-muted-foreground">{{ description }}</p>
    <slot />
  </div>
</template>
