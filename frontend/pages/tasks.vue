<script setup lang="ts">
import { computed, ref } from 'vue'
import { CheckSquare, Scale } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Badge } from '~/components/ui/badge'
import { Card } from '~/components/ui/card'
import EmptyState from '~/components/workspace/EmptyState.vue'
import ErrorState from '~/components/workspace/ErrorState.vue'
import LoadingState from '~/components/workspace/LoadingState.vue'
import PageHeader from '~/components/workspace/PageHeader.vue'
import { useApi } from '~/composables/useApi'
import { formatDate, plural } from '~/lib/format'
import type { TaskActionItem, TaskDecision } from '~/types/api'

useHead({ title: 'Tasks · ACLEDA University' })

const api = useApi()
const { data, pending, error, refresh } = await useAsyncData('tasks-page', async () => {
  const [actionItems, decisions] = await Promise.all([
    api<TaskActionItem[]>('/tasks/action-items'),
    api<TaskDecision[]>('/tasks/decisions'),
  ])
  return { actionItems, decisions }
})

const actionItems = computed(() => data.value?.actionItems ?? [])
const decisions = computed(() => data.value?.decisions ?? [])
const tab = ref<'actions' | 'decisions'>('actions')
const filter = ref<'all' | 'open' | 'overdue' | 'completed'>('all')
const updatingId = ref('')

const filters = computed(() => [
  { value: 'all' as const, label: 'All', count: actionItems.value.length },
  {
    value: 'open' as const,
    label: 'Open',
    count: actionItems.value.filter(item => item.status !== 'Completed').length,
  },
  {
    value: 'overdue' as const,
    label: 'Overdue',
    count: actionItems.value.filter(item => item.is_overdue).length,
  },
  {
    value: 'completed' as const,
    label: 'Completed',
    count: actionItems.value.filter(item => item.status === 'Completed').length,
  },
])

const filteredItems = computed(() => {
  if (filter.value === 'all') return actionItems.value
  if (filter.value === 'open') return actionItems.value.filter(item => item.status !== 'Completed')
  if (filter.value === 'overdue') return actionItems.value.filter(item => item.is_overdue)
  return actionItems.value.filter(item => item.status === 'Completed')
})

async function updateStatus(item: TaskActionItem, event: Event) {
  const status = (event.target as HTMLSelectElement).value
  if (status === item.status) return
  updatingId.value = item.id
  try {
    const updated = await api<TaskActionItem>(`/tasks/action-items/${item.id}`, {
      method: 'PATCH',
      body: { status },
    })
    item.status = updated.status
    item.is_overdue = updated.is_overdue
    toast.success('Task updated.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not update the task.')
    await refresh()
  } finally {
    updatingId.value = ''
  }
}
</script>

<template>
  <div>
    <PageHeader
      title="Tasks"
      description="Action items and decisions from published minutes."
    />

    <LoadingState v-if="pending" class="mt-6" />
    <ErrorState v-else-if="error" class="mt-6" :message="error.message" @retry="refresh" />

    <div v-else class="mt-6">
      <div class="flex items-center gap-1 border-b" role="tablist">
        <button
          role="tab"
          :aria-selected="tab === 'actions'"
          class="relative inline-flex h-9 items-center gap-1.5 px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground"
          :class="
            tab === 'actions'
              ? 'text-foreground after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-brand after:content-[\'\']'
              : ''
          "
          @click="tab = 'actions'"
        >
          <CheckSquare class="h-3.5 w-3.5" />
          Action items
          <span class="tabular-nums text-muted-foreground">{{ actionItems.length }}</span>
        </button>
        <button
          role="tab"
          :aria-selected="tab === 'decisions'"
          class="relative inline-flex h-9 items-center gap-1.5 px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground"
          :class="
            tab === 'decisions'
              ? 'text-foreground after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-brand after:content-[\'\']'
              : ''
          "
          @click="tab = 'decisions'"
        >
          <Scale class="h-3.5 w-3.5" />
          Decisions
          <span class="tabular-nums text-muted-foreground">{{ decisions.length }}</span>
        </button>
      </div>

      <template v-if="tab === 'actions'">
        <div class="flex items-center gap-1 border-b">
          <button
            v-for="option in filters"
            :key="option.value"
            class="relative inline-flex h-9 items-center gap-1.5 px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground"
            :class="
              filter === option.value
                ? 'text-foreground after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-brand after:content-[\'\']'
                : ''
            "
            @click="filter = option.value"
          >
            {{ option.label }}
            <span class="tabular-nums text-[13px] text-muted-foreground">{{ option.count }}</span>
          </button>
        </div>

        <Card v-if="filteredItems.length" class="mt-4 overflow-hidden">
          <div
            v-for="item in filteredItems"
            :key="item.id"
            class="flex flex-col gap-3 border-b px-5 py-4 last:border-b-0 sm:flex-row sm:items-center"
          >
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <p class="text-sm font-medium leading-snug">{{ item.task_description }}</p>
                <Badge v-if="item.is_overdue" variant="negative">Overdue</Badge>
              </div>
              <p class="mt-1 text-[13px] text-muted-foreground">
                {{ item.assignee_name || 'Unassigned' }} · due {{ item.deadline ? formatDate(item.deadline) : 'no deadline' }}
                · <NuxtLink :to="`/meetings/${item.meeting_id}/review`" class="font-medium text-brand hover:underline">
                  {{ item.meeting_title }}
                </NuxtLink>
              </p>
            </div>
            <select
              :value="item.status"
              :disabled="updatingId === item.id"
              class="h-9 w-full shrink-0 rounded-md border border-input bg-background px-2.5 text-[13px] sm:w-36"
              :aria-label="`Status for ${item.task_description}`"
              @change="updateStatus(item, $event)"
            >
              <option value="Pending">Pending</option>
              <option value="In Progress">In Progress</option>
              <option value="Completed">Completed</option>
            </select>
          </div>
        </Card>

        <EmptyState
          v-else
          class="mt-4"
          title="No action items"
          :description="actionItems.length ? 'Switch the filter to see the other tasks.' : 'Publish minutes with action items to see them here.'"
        />
      </template>

      <template v-else>
        <Card v-if="decisions.length" class="mt-4 overflow-hidden">
          <div
            v-for="decision in decisions"
            :key="decision.id"
            class="border-b px-5 py-4 last:border-b-0"
          >
            <div class="flex flex-wrap items-center gap-2">
              <Badge v-if="decision.agenda_topic" variant="outline">{{ decision.agenda_topic }}</Badge>
              <span class="text-[13px] text-muted-foreground">{{ formatDate(decision.meeting_date) }}</span>
            </div>
            <p class="mt-2 text-sm leading-relaxed">{{ decision.decision_text }}</p>
            <NuxtLink
              :to="`/meetings/${decision.meeting_id}/review`"
              class="mt-1.5 inline-block text-[13px] font-medium text-brand hover:underline"
            >
              {{ decision.meeting_title }}
            </NuxtLink>
          </div>
        </Card>

        <EmptyState
          v-else
          class="mt-4"
          title="No decisions yet"
          :description="`${plural(decisions.length, 'decision')} recorded. Publish minutes to add formal decisions.`"
        />
      </template>
    </div>
  </div>
</template>
