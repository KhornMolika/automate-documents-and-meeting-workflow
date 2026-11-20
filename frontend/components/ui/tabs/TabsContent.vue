<script setup lang="ts">
import { TabsContent, type TabsContentProps } from 'reka-ui'
import { cn } from '~/lib/utils'

const props = defineProps<TabsContentProps & { class?: any }>()
</script>

<template>
  <TabsContent
    :class="cn('mt-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2', props.class)"
  >
    <slot />
  </TabsContent>
</template>
