<script setup lang="ts">
import { cn } from '~/lib/utils'

const props = defineProps<{ class?: any }>()
</script>

<template>
  <div :class="cn('rounded-lg border bg-card text-card-foreground transition-shadow duration-200 hover:shadow-[0_2px_10px_rgba(35,31,28,0.045)]', props.class)">
    <slot />
  </div>
</template>
