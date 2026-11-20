<script setup lang="ts">
import { cn } from '~/lib/utils'

const props = defineProps<{
  title: string
  description?: string
  class?: any
}>()
</script>

<template>
  <header :class="cn('flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between', props.class)">
    <div class="min-w-0">
      <div v-if="$slots.meta" class="mb-2 flex flex-wrap items-center gap-2">
        <slot name="meta" />
      </div>
      <h1 class="text-[22px] font-semibold leading-tight tracking-[-0.025em] sm:text-[24px]">
        {{ title }}
      </h1>
      <p v-if="description" class="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        {{ description }}
      </p>
    </div>
    <div v-if="$slots.actions" class="flex shrink-0 flex-wrap items-center gap-2">
      <slot name="actions" />
    </div>
  </header>
</template>
