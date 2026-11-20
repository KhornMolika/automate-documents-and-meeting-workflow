<script setup lang="ts">
import { Card } from '~/components/ui/card'
import CountUp from '~/components/motion/CountUp.vue'
import { cn } from '~/lib/utils'

interface Metric {
  label: string
  value: number | string
  suffix?: string
  decimals?: number
  note?: string
}

const props = defineProps<{ items: Metric[], class?: any }>()
</script>

<template>
  <Card :class="cn('overflow-hidden p-0', props.class)">
    <div class="grid grid-cols-2 gap-px bg-border lg:grid-cols-4">
      <div v-for="item in items" :key="item.label" class="bg-card p-5">
        <p class="text-[13px] text-muted-foreground">{{ item.label }}</p>
        <p class="mt-1.5 text-[28px] font-medium leading-none tracking-[-0.03em]">
          <CountUp
            v-if="typeof item.value === 'number'"
            :value="item.value"
            :decimals="item.decimals ?? 0"
            :suffix="item.suffix"
          />
          <span v-else class="tabular">{{ item.value }}</span>
        </p>
        <p v-if="item.note" class="mt-2 text-[13px] leading-snug text-muted-foreground">{{ item.note }}</p>
      </div>
    </div>
  </Card>
</template>
