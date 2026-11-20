<script setup lang="ts">
import { DialogTitle, type DialogTitleProps } from 'reka-ui'
import { cn } from '~/lib/utils'

const props = defineProps<DialogTitleProps & { class?: any }>()
</script>

<template>
  <DialogTitle :class="cn('text-lg font-semibold tracking-[-0.01em]', props.class)">
    <slot />
  </DialogTitle>
</template>
