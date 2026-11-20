<script setup lang="ts">
import { cn } from '~/lib/utils'

const props = defineProps<{ class?: any }>()
</script>

<template>
  <p :class="cn('text-[13px] text-muted-foreground', props.class)">
    <slot />
  </p>
</template>
