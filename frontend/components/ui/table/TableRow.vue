<script setup lang="ts">
import { cn } from '~/lib/utils'

const props = defineProps<{ class?: any }>()
</script>

<template>
  <tr :class="cn('border-b border-border/70 transition-colors hover:bg-muted/45', props.class)">
    <slot />
  </tr>
</template>
