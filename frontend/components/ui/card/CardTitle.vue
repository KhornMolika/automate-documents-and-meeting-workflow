<script setup lang="ts">
import { cn } from '~/lib/utils'

const props = defineProps<{ class?: any }>()
</script>

<template>
  <h3 :class="cn('text-[15px] font-semibold leading-tight tracking-[-0.01em]', props.class)">
    <slot />
  </h3>
</template>
