<script setup lang="ts">
import { TabsList, type TabsListProps } from 'reka-ui'
import { cn } from '~/lib/utils'

const props = defineProps<TabsListProps & { class?: any }>()
</script>

<template>
  <TabsList
    :class="cn('inline-flex h-9 items-center justify-start gap-1 border-b border-border', props.class)"
  >
    <slot />
  </TabsList>
</template>
