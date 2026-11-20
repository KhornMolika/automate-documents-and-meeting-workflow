<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { cn } from '~/lib/utils'

const props = withDefaults(
  defineProps<{
    value: number
    duration?: number
    decimals?: number
    prefix?: string
    suffix?: string
    class?: any
  }>(),
  { duration: 700, decimals: 0 },
)

const display = ref(0)
let frame = 0

function format(value: number) {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: props.decimals,
    maximumFractionDigits: props.decimals,
  })
}

function animate(to: number) {
  if (typeof window === 'undefined') {
    display.value = to
    return
  }

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduced) {
    display.value = to
    return
  }

  cancelAnimationFrame(frame)
  const from = display.value
  const start = performance.now()

  const tick = (now: number) => {
    const progress = Math.min((now - start) / props.duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)
    display.value = from + (to - from) * eased
    if (progress < 1) frame = requestAnimationFrame(tick)
  }

  frame = requestAnimationFrame(tick)
}

onMounted(() => animate(props.value))
watch(() => props.value, value => animate(value))
onUnmounted(() => cancelAnimationFrame(frame))
</script>

<template>
  <span :class="cn('tabular-nums', props.class)">
    <span v-if="prefix">{{ prefix }}</span>{{ format(display) }}<span v-if="suffix">{{ suffix }}</span>
  </span>
</template>
