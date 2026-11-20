<script setup lang="ts">
import { AvatarFallback } from 'reka-ui'
import { cn } from '~/lib/utils'

const props = defineProps<{ class?: any }>()
</script>

<template>
  <AvatarFallback
    :class="
      cn(
        'flex h-full w-full items-center justify-center rounded-full bg-secondary text-[11px] font-semibold text-secondary-foreground',
        props.class,
      )
    "
  >
    <slot />
  </AvatarFallback>
</template>
