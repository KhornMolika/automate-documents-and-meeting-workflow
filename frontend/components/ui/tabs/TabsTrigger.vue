<script setup lang="ts">
import { TabsTrigger, type TabsTriggerProps } from 'reka-ui'
import { cn } from '~/lib/utils'

const props = defineProps<TabsTriggerProps & { class?: any }>()
</script>

<template>
  <TabsTrigger
    :class="
      cn(
        'relative inline-flex h-9 items-center justify-center whitespace-nowrap px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:text-foreground data-[state=active]:after:absolute data-[state=active]:after:inset-x-0 data-[state=active]:after:-bottom-px data-[state=active]:after:h-0.5 data-[state=active]:after:bg-brand data-[state=active]:after:content-[\'\']',
        props.class,
      )
    "
  >
    <slot />
  </TabsTrigger>
</template>
