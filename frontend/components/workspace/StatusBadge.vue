<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '~/components/ui/badge'
import { statusTone } from '~/lib/format'

const props = defineProps<{ status: string, class?: any }>()
const variant = computed(() => statusTone(props.status) as any)
</script>

<template>
  <Badge :variant="variant" :class="props.class">
    {{ props.status }}
  </Badge>
</template>
