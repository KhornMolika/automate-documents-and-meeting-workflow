<script setup lang="ts">
import {
  SelectContent,
  SelectIcon,
  SelectItem,
  SelectItemIndicator,
  SelectItemText,
  SelectPortal,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'
import { Check, ChevronDown } from 'lucide-vue-next'
import { cn } from '~/lib/utils'
import type { SelectOption } from './types'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    modelValue?: string | number | null
    options: SelectOption[]
    placeholder?: string
    disabled?: boolean
    class?: any
    ariaLabel?: string
    id?: string
  }>(),
  {
    placeholder: 'Select an option',
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string | number]
}>()
</script>

<template>
  <SelectRoot
    :model-value="props.modelValue === null || props.modelValue === undefined ? undefined : props.modelValue"
    :disabled="props.disabled"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <SelectTrigger
      v-bind="$attrs"
      :id="props.id"
      :aria-label="props.ariaLabel"
      :class="
        cn(
          'group flex h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-card px-3 text-left text-sm text-foreground shadow-[0_1px_1px_rgba(35,31,28,0.03)] transition-[border-color,box-shadow,background-color] duration-150 hover:border-brand/35 focus:outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25 disabled:cursor-not-allowed disabled:opacity-50 data-[state=open]:border-brand/50 data-[state=open]:ring-2 data-[state=open]:ring-ring/20 max-sm:h-10',
          props.class,
        )
      "
    >
      <SelectValue :placeholder="props.placeholder" class="min-w-0 truncate" />
      <SelectIcon as-child>
        <ChevronDown
          class="h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-180"
        />
      </SelectIcon>
    </SelectTrigger>

    <SelectPortal>
      <SelectContent
        position="popper"
        :side-offset="6"
        class="z-[100] max-h-[min(22rem,var(--reka-select-content-available-height))] min-w-[var(--reka-select-trigger-width)] overflow-hidden rounded-lg border border-border bg-card p-1 shadow-[0_18px_45px_-18px_rgba(35,31,28,0.35),0_2px_8px_rgba(35,31,28,0.06)] data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95"
      >
        <SelectViewport class="max-h-[min(20rem,var(--reka-select-content-available-height))] overflow-y-auto">
          <SelectItem
            v-for="option in props.options"
            :key="String(option.value)"
            :value="option.value"
            :disabled="option.disabled"
            class="relative flex cursor-default select-none items-start gap-2 rounded-md py-2 pl-8 pr-3 text-[13px] leading-snug outline-none transition-colors data-[disabled]:pointer-events-none data-[disabled]:opacity-45 data-[highlighted]:bg-secondary data-[state=checked]:font-medium data-[state=checked]:text-brand"
          >
            <SelectItemIndicator class="absolute left-2.5 top-2.5">
              <Check class="h-3.5 w-3.5" />
            </SelectItemIndicator>
            <span class="min-w-0">
              <SelectItemText>{{ option.label }}</SelectItemText>
              <span v-if="option.description" class="mt-0.5 block text-[12px] font-normal text-muted-foreground">
                {{ option.description }}
              </span>
            </span>
          </SelectItem>
        </SelectViewport>
      </SelectContent>
    </SelectPortal>
  </SelectRoot>
</template>
