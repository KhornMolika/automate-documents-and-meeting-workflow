<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '~/components/ui/badge'
import LiveDot from '~/components/motion/LiveDot.vue'
import { statusTone } from '~/lib/format'

const props = defineProps<{ status: string, class?: any }>()
const variant = computed(() => statusTone(props.status) as any)
const live = computed(() => props.status === 'In Progress' || props.status === 'Live')
</script>

<template>
  <Badge :variant="variant" :class="props.class">
    <LiveDot v-if="live" />
    {{ props.status }}
  </Badge>
</template>
