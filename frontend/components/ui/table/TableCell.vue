<script setup lang="ts">
import { cn } from '~/lib/utils'

const props = defineProps<{ class?: any }>()
</script>

<template>
  <td :class="cn('px-3 py-3 align-middle [&:has([role=checkbox])]:pr-0', props.class)">
    <slot />
  </td>
</template>
