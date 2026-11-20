<script setup lang="ts">
import { cn } from '~/lib/utils'

const props = defineProps<{ class?: any }>()
</script>

<template>
  <span
    :class="cn('inline-flex h-1.5 w-1.5 shrink-0 rounded-full bg-brand ring-2 ring-brand/20', props.class)"
    aria-hidden="true"
  />
</template>
