<script setup lang="ts">
import { computed } from 'vue'
import {
  ArrowUpRight,
  CalendarDays,
  Check,
  Plus,
  Upload,
} from 'lucide-vue-next'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '~/components/ui/card'
import AudioWave from '~/components/motion/AudioWave.vue'
import LiveDot from '~/components/motion/LiveDot.vue'
import ErrorState from '~/components/workspace/ErrorState.vue'
import LoadingState from '~/components/workspace/LoadingState.vue'
import MetricStrip from '~/components/workspace/MetricStrip.vue'
import PageHeader from '~/components/workspace/PageHeader.vue'
import StatusBadge from '~/components/workspace/StatusBadge.vue'
import { useApi } from '~/composables/useApi'
import { useAuth } from '~/composables/useAuth'
import { fileType, formatBytes, formatDate, formatTimeRange, plural } from '~/lib/format'
import type { Dashboard } from '~/types/api'

useHead({ title: 'Overview · ACLEDA University' })

const api = useApi()
const { user } = useAuth()
const { data, pending, error, refresh } = await useAsyncData('dashboard', () => api<Dashboard>('/dashboard'))

const dashboard = computed(() => data.value)
const liveMeeting = computed(() => dashboard.value?.live_meeting ?? null)
const nextMeeting = computed(() => dashboard.value?.next_meeting ?? null)
const recentDocuments = computed(() => dashboard.value?.recent_documents ?? [])
const actionItems = computed(() => dashboard.value?.action_items ?? [])
const attentionItems = computed(() => actionItems.value.slice(0, 4))
const departmentName = computed(() => user.value?.department?.name ?? 'Department workspace')

const metrics = computed(() => {
  const value = dashboard.value
  return [
    { label: 'Documents', value: value?.documents_count ?? 0, note: 'in the repository' },
    { label: 'Meetings', value: value?.meetings_count ?? 0, note: 'in the workspace' },
    {
      label: 'Open action items',
      value: value?.open_action_items_count ?? 0,
      note: 'across verified minutes',
    },
    {
      label: 'MoM turnaround',
      value: value?.mom_turnaround_minutes ?? '—',
      suffix: value?.mom_turnaround_minutes ? ' min' : '',
      decimals: 1,
      note: value?.mom_turnaround_minutes ? 'meeting end to verification' : 'no verified minutes yet',
    },
  ]
})

const momSteps = computed(() => {
  if (!liveMeeting.value) return []
  const meeting = liveMeeting.value
  return [
    {
      label: 'Transcript captured',
      state: meeting.transcript_count > 0 ? 'done' : 'todo',
    },
    {
      label: 'Decisions extracted',
      state: meeting.summary && meeting.summary.decisions_count > 0 ? 'done' : meeting.summary ? 'current' : 'todo',
    },
    {
      label: 'Verification',
      state: meeting.summary?.is_verified ? 'done' : meeting.summary ? 'current' : 'todo',
    },
  ] as { label: string, state: 'done' | 'current' | 'todo' }[]
})

const completedSteps = computed(() => momSteps.value.filter(step => step.state === 'done').length)

function documentCategory(document: { category?: { name: string } | null }) {
  return document.category?.name ?? 'Uncategorised'
}

function fileSize(document: { latest_version?: { file_size_bytes: number } | null }) {
  return formatBytes(document.latest_version?.file_size_bytes)
}

function fileName(document: { latest_version?: { file_name: string } | null }) {
  return document.latest_version?.file_name ?? 'No file'
}

function itemDue(item: { deadline?: string | null }) {
  return item.deadline ? formatDate(item.deadline) : 'No deadline'
}

function itemAssignee(item: { assignee?: string | null }) {
  return item.assignee || 'Unassigned'
}
</script>

<template>
  <div>
    <PageHeader
      title="Overview"
      :description="`${departmentName} · Document and meeting workspace`"
    >
      <template #actions>
        <Button variant="outline" as-child>
          <NuxtLink to="/documents">
            <Upload class="h-4 w-4" />
            Upload document
          </NuxtLink>
        </Button>
        <Button variant="outline" as-child>
          <NuxtLink to="/meetings">
            <Plus class="h-4 w-4" />
            New meeting
          </NuxtLink>
        </Button>
      </template>
    </PageHeader>

    <LoadingState v-if="pending" class="mt-6" />
    <ErrorState
      v-else-if="error"
      class="mt-6"
      :message="error.message"
      @retry="refresh"
    />

    <template v-else>
      <p class="mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        {{ liveMeeting ? 'A meeting is live.' : 'No meeting is live.' }}
        {{ plural(dashboard?.open_action_items_count ?? 0, 'action item') }} open.
        <template v-if="!dashboard?.mom_turnaround_minutes">No minutes have been verified yet.</template>
      </p>

      <MetricStrip :items="metrics" class="mt-6" />

      <div class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Card v-if="liveMeeting" class="flex flex-col xl:col-span-8">
          <CardHeader class="flex-row items-start justify-between gap-4 pb-4">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <Badge variant="live">
                  <LiveDot />
                  Live
                </Badge>
                <span class="text-[13px] text-muted-foreground">
                  {{ formatDate(liveMeeting.scheduled_start) }} · {{ formatTimeRange(liveMeeting.scheduled_start, liveMeeting.scheduled_end) }}
                </span>
              </div>
              <CardTitle class="mt-2 text-lg">{{ liveMeeting.title }}</CardTitle>
              <CardDescription class="mt-1">
                {{ plural(liveMeeting.participants, 'participant') }} · {{ plural(liveMeeting.agenda.length, 'agenda item') }}
              </CardDescription>
            </div>
            <div class="hidden shrink-0 items-center gap-2 sm:flex">
              <AudioWave />
              <span class="text-[13px] text-muted-foreground">Listening</span>
            </div>
          </CardHeader>

          <CardContent class="flex flex-1 flex-col gap-5">
            <div class="rounded-md border bg-background/70 p-4">
              <p class="text-[13px] font-medium">Agenda</p>
              <div v-if="liveMeeting.agenda.length" class="mt-3 space-y-2.5">
                <div
                  v-for="(item, index) in liveMeeting.agenda"
                  :key="`${item.title}-${index}`"
                  class="flex items-start justify-between gap-3"
                >
                  <p class="text-[13px] leading-snug">{{ item.title }}</p>
                  <span class="tabular-nums shrink-0 text-[13px] text-muted-foreground">{{ item.duration_minutes }} min</span>
                </div>
              </div>
              <p v-else class="mt-2 text-[13px] text-muted-foreground">No agenda items recorded.</p>
            </div>

            <div>
              <div class="flex items-center justify-between gap-3">
                <p class="text-[13px] font-medium">Minutes readiness</p>
                <p class="text-[13px] text-muted-foreground">
                  {{ completedSteps }} of {{ momSteps.length }} steps complete
                </p>
              </div>
              <div class="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
                <div
                  v-for="(step, index) in momSteps"
                  :key="step.label"
                  class="flex items-center gap-1.5"
                >
                  <span
                    class="flex h-4 w-4 items-center justify-center rounded-full border"
                    :class="
                      step.state === 'done'
                        ? 'border-brand bg-brand text-brand-foreground'
                        : step.state === 'current'
                          ? 'border-brand text-brand'
                          : 'border-border text-muted-foreground'
                    "
                  >
                    <Check v-if="step.state === 'done'" class="h-2.5 w-2.5" />
                    <span v-else class="h-1.5 w-1.5 rounded-full bg-current" />
                  </span>
                  <span class="text-[13px]" :class="step.state === 'todo' ? 'text-muted-foreground' : 'text-foreground'">
                    {{ step.label }}
                  </span>
                  <span
                    v-if="index < momSteps.length - 1"
                    class="ml-1 hidden h-px w-4 bg-border sm:block"
                  />
                </div>
              </div>
              <div class="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  class="h-full rounded-full bg-brand transition-[width] duration-500"
                  :style="{ width: `${momSteps.length ? (completedSteps / momSteps.length) * 100 : 0}%` }"
                />
              </div>
            </div>

            <div class="mt-auto flex flex-wrap items-center gap-2 pt-1">
              <Button as-child>
                <NuxtLink :to="`/meetings/${liveMeeting.id}/live`">
                  Open live console
                  <ArrowUpRight class="h-4 w-4" />
                </NuxtLink>
              </Button>
              <Button variant="outline" as-child>
                <NuxtLink :to="`/meetings/${liveMeeting.id}/review`">Review minutes</NuxtLink>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card v-else class="flex flex-col xl:col-span-8">
          <CardHeader class="pb-3">
            <CardTitle>No meeting is live</CardTitle>
            <CardDescription v-if="nextMeeting">
              Next up: {{ nextMeeting.title }} · {{ formatDate(nextMeeting.scheduled_start) }}
            </CardDescription>
            <CardDescription v-else>Schedule a meeting to start capturing minutes.</CardDescription>
          </CardHeader>
          <CardContent class="flex flex-1 flex-col justify-between gap-4">
            <div v-if="nextMeeting" class="rounded-md border bg-background/70 p-4">
              <div class="flex flex-wrap items-center gap-2">
                <StatusBadge :status="nextMeeting.status" />
                <span class="text-[13px] text-muted-foreground">
                  {{ formatDate(nextMeeting.scheduled_start) }} · {{ formatTimeRange(nextMeeting.scheduled_start, nextMeeting.scheduled_end) }}
                </span>
              </div>
              <p class="mt-2 text-[15px] font-medium">{{ nextMeeting.title }}</p>
              <p class="mt-1 text-[13px] text-muted-foreground">
                {{ plural(nextMeeting.participants, 'participant') }} · {{ plural(nextMeeting.agenda.length, 'agenda item') }}
              </p>
            </div>
            <p v-else class="max-w-lg text-sm leading-relaxed text-muted-foreground">
              There are no scheduled meetings. Create one to prepare an agenda and begin the record.
            </p>
            <div class="flex flex-wrap gap-2">
              <Button v-if="nextMeeting" as-child>
                <NuxtLink :to="`/meetings/${nextMeeting.id}/live`">Open meeting console</NuxtLink>
              </Button>
              <Button as-child variant="outline">
                <NuxtLink to="/meetings">
                  <Plus class="h-4 w-4" />
                  New meeting
                </NuxtLink>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card class="flex flex-col xl:col-span-4">
          <CardHeader class="pb-3">
            <CardTitle>Needs attention</CardTitle>
            <CardDescription>Open tasks assigned in verified minutes.</CardDescription>
          </CardHeader>
          <div v-if="attentionItems.length" class="flex flex-1 flex-col border-t">
            <div
              v-for="item in attentionItems"
              :key="item.id"
              class="flex flex-1 items-start gap-3 border-b px-5 py-3.5 last:border-b-0"
            >
              <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
              <div class="min-w-0 flex-1">
                <p class="line-clamp-2 text-sm font-medium leading-snug">{{ item.task }}</p>
                <p class="mt-1 text-[13px] text-muted-foreground">
                  {{ itemAssignee(item) }} · due {{ itemDue(item) }}
                </p>
              </div>
              <StatusBadge :status="item.status" />
            </div>
          </div>
          <div v-else class="flex flex-1 items-center border-t px-5 py-6">
            <p class="text-[13px] text-muted-foreground">No open action items.</p>
          </div>
          <div v-if="nextMeeting" class="border-t px-5 py-3.5">
            <p class="text-[13px] text-muted-foreground">Next meeting</p>
            <div class="mt-1 flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="line-clamp-1 text-sm font-medium">{{ nextMeeting.title }}</p>
                <p class="mt-0.5 text-[13px] text-muted-foreground">
                  {{ formatDate(nextMeeting.scheduled_start) }} · {{ formatTimeRange(nextMeeting.scheduled_start, nextMeeting.scheduled_end) }}
                </p>
              </div>
              <CalendarDays class="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            </div>
          </div>
        </Card>
      </div>

      <div class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Card class="flex flex-col xl:col-span-7">
          <CardHeader class="flex-row items-center justify-between gap-3 pb-3">
            <div>
              <CardTitle>Recent documents</CardTitle>
              <CardDescription class="mt-1">Latest files added to the department repository.</CardDescription>
            </div>
            <NuxtLink to="/documents" class="shrink-0 text-[13px] font-medium text-brand hover:underline">
              View all
            </NuxtLink>
          </CardHeader>
          <div v-if="recentDocuments.length" class="flex flex-1 flex-col border-t">
            <div
              v-for="document in recentDocuments"
              :key="document.id"
              class="flex flex-1 items-center gap-3 border-b px-5 py-3 last:border-b-0"
            >
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-medium">{{ document.title }}</p>
                <p class="mt-0.5 text-[13px] text-muted-foreground">
                  {{ fileType(fileName(document)) }} · {{ fileSize(document) }} · v{{ document.current_version }}
                </p>
              </div>
              <Badge variant="outline">{{ documentCategory(document) }}</Badge>
              <span class="hidden w-24 text-right text-[13px] text-muted-foreground sm:block">
                {{ formatDate(document.created_at) }}
              </span>
            </div>
          </div>
          <div v-else class="flex flex-1 items-center border-t px-5 py-6">
            <p class="text-[13px] text-muted-foreground">No documents have been uploaded yet.</p>
          </div>
        </Card>

        <Card class="flex flex-col xl:col-span-5">
          <CardHeader class="flex-row items-center justify-between gap-3 pb-3">
            <div>
              <CardTitle>Action items</CardTitle>
              <CardDescription class="mt-1">Open tasks created from verified minutes.</CardDescription>
            </div>
            <NuxtLink to="/meetings" class="shrink-0 text-[13px] font-medium text-brand hover:underline">
              View all
            </NuxtLink>
          </CardHeader>
          <div v-if="actionItems.length" class="flex flex-1 flex-col border-t">
            <div
              v-for="item in actionItems"
              :key="item.id"
              class="flex flex-1 items-center gap-3 border-b px-5 py-3 last:border-b-0"
            >
              <div class="min-w-0 flex-1">
                <p class="line-clamp-1 text-sm font-medium">{{ item.task }}</p>
                <p class="mt-0.5 text-[13px] text-muted-foreground">
                  {{ itemAssignee(item) }} · due {{ itemDue(item) }}
                </p>
              </div>
              <StatusBadge :status="item.status" />
            </div>
          </div>
          <div v-else class="flex flex-1 items-center border-t px-5 py-6">
            <p class="text-[13px] text-muted-foreground">No action items yet.</p>
          </div>
        </Card>
      </div>
    </template>
  </div>
</template>
