<script setup lang="ts">
import { cn } from '~/lib/utils'

const props = withDefaults(defineProps<{ bars?: number, class?: any }>(), { bars: 5 })
</script>

<template>
  <span :class="cn('inline-flex h-4 items-end gap-[2px]', props.class)" aria-hidden="true">
    <span
      v-for="index in bars"
      :key="index"
      class="w-[2px] origin-bottom animate-wave rounded-full bg-brand"
      :style="{
        height: `${[9, 14, 6, 12, 10, 15, 8][index % 7]}px`,
        animationDelay: `${index * 90}ms`,
        animationDuration: `${900 + (index % 3) * 180}ms`,
      }"
    />
  </span>
</template>
