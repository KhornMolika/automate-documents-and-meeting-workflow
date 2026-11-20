<script setup lang="ts">
import { DialogClose, type DialogCloseProps } from 'reka-ui'
import { cn } from '~/lib/utils'

const props = defineProps<DialogCloseProps & { class?: any }>()
</script>

<template>
  <DialogClose v-bind="props" :class="cn(props.class)">
    <slot />
  </DialogClose>
</template>
