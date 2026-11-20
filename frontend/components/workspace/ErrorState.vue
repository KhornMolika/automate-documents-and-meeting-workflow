<script setup lang="ts">
import { AlertCircle } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Card } from '~/components/ui/card'

const props = defineProps<{ message?: string, class?: any }>()
const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <Card :class="['items-start gap-3 p-6', props.class]">
    <div class="flex items-start gap-2.5">
      <AlertCircle class="mt-0.5 h-4 w-4 text-negative" />
      <div>
        <p class="text-sm font-medium">Could not load this view</p>
        <p class="mt-1 max-w-lg text-[13px] leading-relaxed text-muted-foreground">
          {{ props.message || 'The API is unavailable. Check that the backend is running and try again.' }}
        </p>
        <Button variant="outline" size="sm" class="mt-4" @click="emit('retry')">
          Retry
        </Button>
      </div>
    </div>
  </Card>
</template>
