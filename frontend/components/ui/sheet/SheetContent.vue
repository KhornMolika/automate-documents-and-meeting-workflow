<script setup lang="ts">
import {
  DialogClose,
  DialogContent as DialogContentPrimitive,
  DialogOverlay,
  DialogPortal,
} from 'reka-ui'
import { X } from 'lucide-vue-next'
import { cn } from '~/lib/utils'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ class?: any }>()
</script>

<template>
  <DialogPortal>
    <DialogOverlay
      data-testid="sheet-overlay"
      class="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
    />
    <DialogContentPrimitive
      v-bind="$attrs"
      :class="
        cn(
          'fixed inset-y-0 left-0 z-50 flex h-full w-[280px] flex-col border-r bg-background p-0 shadow-lg outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left',
          props.class,
        )
      "
    >
      <slot />
      <DialogClose
        class="absolute right-3 top-3 rounded-sm p-1 text-muted-foreground opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X class="h-4 w-4" />
        <span class="sr-only">Close</span>
      </DialogClose>
    </DialogContentPrimitive>
  </DialogPortal>
</template>
