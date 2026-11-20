<script setup lang="ts">
import { AvatarImage, type AvatarImageProps } from 'reka-ui'
import { cn } from '~/lib/utils'

const props = defineProps<AvatarImageProps & { class?: any }>()
</script>

<template>
  <AvatarImage :class="cn('aspect-square h-full w-full object-cover', props.class)" v-bind="props" />
</template>
