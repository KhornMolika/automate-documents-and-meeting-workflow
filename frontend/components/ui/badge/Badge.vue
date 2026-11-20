<script setup lang="ts">
import { cn } from '~/lib/utils'
import { badgeVariants, type BadgeVariants } from '.'

interface Props {
  variant?: BadgeVariants['variant']
  class?: any
}

const props = withDefaults(defineProps<Props>(), { variant: 'default' })
</script>

<template>
  <span :class="cn(badgeVariants({ variant }), props.class)">
    <slot />
  </span>
</template>
