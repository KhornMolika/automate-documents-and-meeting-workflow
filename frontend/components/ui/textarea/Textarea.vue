<script setup lang="ts">
import { cn } from '~/lib/utils'

defineOptions({ inheritAttrs: false })

const model = defineModel<string | number>()
const props = defineProps<{ class?: any }>()
</script>

<template>
  <textarea
    v-model="model"
    v-bind="$attrs"
    :class="
      cn(
        'flex min-h-[80px] w-full rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50',
        props.class,
      )
    "
  />
</template>
