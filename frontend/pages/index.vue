<script setup lang="ts">
import { computed } from 'vue'
import { ArrowUpRight, Plus, Upload } from 'lucide-vue-next'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '~/components/ui/card'
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
      note: 'from published minutes',
    },
    {
      label: 'Overdue',
      value: value?.overdue_action_items_count ?? 0,
      note: value?.overdue_action_items_count ? 'need attention now' : 'nothing overdue',
    },
  ]
})

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
      :description="`${departmentName} · Documents, meetings and follow-ups`"
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
    <ErrorState v-else-if="error" class="mt-6" :message="error.message" @retry="refresh" />

    <template v-else>
      <p class="mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        {{ plural(dashboard?.open_action_items_count ?? 0, 'action item') }} open.
        <template v-if="dashboard?.overdue_action_items_count">
          {{ dashboard.overdue_action_items_count }} overdue.
        </template>
        <template v-else>Nothing is overdue.</template>
      </p>

      <MetricStrip :items="metrics" class="mt-6" />

      <div class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Card class="flex flex-col xl:col-span-8">
          <CardHeader class="pb-3">
            <CardTitle>Next meeting</CardTitle>
            <CardDescription v-if="nextMeeting">The next scheduled session in this department.</CardDescription>
            <CardDescription v-else>No meeting is scheduled.</CardDescription>
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
              <div v-if="nextMeeting.agenda.length" class="mt-3 border-t pt-3">
                <p class="text-[13px] font-medium">Agenda</p>
                <p v-for="item in nextMeeting.agenda" :key="item.title" class="mt-1 text-[13px] text-muted-foreground">
                  {{ item.title }}
                </p>
              </div>
            </div>
            <p v-else class="max-w-lg text-sm leading-relaxed text-muted-foreground">
              Create a meeting to upload a recording or transcript and prepare the minutes.
            </p>
            <div class="flex flex-wrap gap-2">
              <Button v-if="nextMeeting" as-child>
                <NuxtLink :to="`/meetings/${nextMeeting.id}/review`">
                  Open meeting
                  <ArrowUpRight class="h-4 w-4" />
                </NuxtLink>
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
          <CardHeader class="flex-row items-center justify-between gap-3 pb-3">
            <div>
              <CardTitle>Needs attention</CardTitle>
              <CardDescription class="mt-1">Open tasks from published minutes.</CardDescription>
            </div>
            <NuxtLink to="/tasks" class="shrink-0 text-[13px] font-medium text-brand hover:underline">
              View all
            </NuxtLink>
          </CardHeader>
          <div v-if="attentionItems.length" class="flex flex-1 flex-col border-t">
            <div
              v-for="item in attentionItems"
              :key="item.id"
              class="flex flex-1 items-start gap-3 border-b px-5 py-3.5 last:border-b-0"
            >
              <span
                class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                :class="item.is_overdue ? 'bg-negative' : 'bg-brand'"
              />
              <div class="min-w-0 flex-1">
                <p class="line-clamp-2 text-sm font-medium leading-snug">{{ item.task }}</p>
                <p class="mt-1 text-[13px] text-muted-foreground">
                  {{ itemAssignee(item) }} · due {{ itemDue(item) }}
                </p>
              </div>
              <Badge :variant="item.is_overdue ? 'negative' : 'outline'">
                {{ item.is_overdue ? 'Overdue' : item.status }}
              </Badge>
            </div>
          </div>
          <div v-else class="flex flex-1 items-center border-t px-5 py-6">
            <p class="text-[13px] text-muted-foreground">No open action items.</p>
          </div>
        </Card>
      </div>

      <Card class="mt-4">
        <CardHeader class="flex-row items-center justify-between gap-3 pb-3">
          <div>
            <CardTitle>Recent documents</CardTitle>
            <CardDescription class="mt-1">Latest files, including published minutes.</CardDescription>
          </div>
          <NuxtLink to="/documents" class="shrink-0 text-[13px] font-medium text-brand hover:underline">
            View all
          </NuxtLink>
        </CardHeader>
        <div v-if="recentDocuments.length" class="flex flex-col border-t">
          <div
            v-for="document in recentDocuments"
            :key="document.id"
            class="flex items-center gap-3 border-b px-5 py-3 last:border-b-0"
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
        <div v-else class="flex items-center border-t px-5 py-6">
          <p class="text-[13px] text-muted-foreground">No documents have been uploaded yet.</p>
        </div>
      </Card>
    </template>
  </div>
</template>
