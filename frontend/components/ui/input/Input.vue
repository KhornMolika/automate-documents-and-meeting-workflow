<script setup lang="ts">
import { cn } from '~/lib/utils'

defineOptions({ inheritAttrs: false })

const model = defineModel<string | number>()
const props = defineProps<{ class?: any }>()
</script>

<template>
  <input
    v-model="model"
    v-bind="$attrs"
    :class="
      cn(
        'flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm text-foreground transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50 max-sm:h-10',
        props.class,
      )
    "
  />
</template>
