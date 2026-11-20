<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CalendarDays, Plus } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '~/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '~/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '~/components/ui/dialog'
import { Input } from '~/components/ui/input'
import { Label } from '~/components/ui/label'
import { Textarea } from '~/components/ui/textarea'
import EmptyState from '~/components/workspace/EmptyState.vue'
import ErrorState from '~/components/workspace/ErrorState.vue'
import LoadingState from '~/components/workspace/LoadingState.vue'
import PageHeader from '~/components/workspace/PageHeader.vue'
import StatusBadge from '~/components/workspace/StatusBadge.vue'
import { useApi } from '~/composables/useApi'
import { useAuth } from '~/composables/useAuth'
import { formatDate, formatTimeRange, plural } from '~/lib/format'
import type { Dashboard, Meeting } from '~/types/api'

useHead({ title: 'Meetings · ACLEDA University' })

const api = useApi()
const { user } = useAuth()
const { data, pending, error, refresh } = await useAsyncData('meetings-page', async () => {
  const [meetings, dashboard] = await Promise.all([
    api<Meeting[]>('/meetings', { query: { limit: 200 } }),
    api<Dashboard>('/dashboard'),
  ])
  return { meetings, dashboard }
})

const meetingList = computed(() => data.value?.meetings ?? [])
const dashboard = computed(() => data.value?.dashboard)
const departmentName = computed(() => user.value?.department?.name ?? 'Department workspace')
const activeFilter = ref<'all' | 'live' | 'scheduled' | 'completed'>('all')
const newMeetingOpen = ref(false)
const saving = ref(false)
const showMore = ref(false)
const meetingForm = ref({
  title: '',
  description: '',
  agenda: '',
})

function resetMeetingForm() {
  meetingForm.value = {
    title: '',
    description: '',
    agenda: '',
  }
  showMore.value = false
}

resetMeetingForm()

watch(newMeetingOpen, (open) => {
  if (open) resetMeetingForm()
})

const filters = computed(() => [
  { value: 'all' as const, label: 'All', count: meetingList.value.length },
  {
    value: 'live' as const,
    label: 'Live',
    count: meetingList.value.filter(meeting => meeting.status === 'In Progress').length,
  },
  {
    value: 'scheduled' as const,
    label: 'Scheduled',
    count: meetingList.value.filter(meeting => meeting.status === 'Scheduled').length,
  },
  {
    value: 'completed' as const,
    label: 'Completed',
    count: meetingList.value.filter(meeting => meeting.status === 'Completed').length,
  },
])

const filteredMeetings = computed(() => {
  if (activeFilter.value === 'all') return meetingList.value
  if (activeFilter.value === 'live') {
    return meetingList.value.filter(meeting => meeting.status === 'In Progress')
  }
  if (activeFilter.value === 'scheduled') {
    return meetingList.value.filter(meeting => meeting.status === 'Scheduled')
  }
  return meetingList.value.filter(meeting => meeting.status === 'Completed')
})

const recentDecisions = computed(() => dashboard.value?.recent_decisions ?? [])
const openActionItems = computed(() => dashboard.value?.action_items ?? [])

async function addMeeting() {
  const departmentId = user.value?.department_id
  if (!departmentId) {
    toast.error('Your account has no department. Ask an administrator to assign one.')
    return
  }
  const title = meetingForm.value.title.trim() || `${departmentName.value} meeting`
  const start = new Date()
  const end = new Date(start.getTime() + 30 * 60_000)

  saving.value = true
  try {
    await api('/meetings', {
      method: 'POST',
      body: {
        title,
        description: meetingForm.value.description.trim() || null,
        scheduled_start: start.toISOString(),
        scheduled_end: end.toISOString(),
        department_id: departmentId,
        agendas: meetingForm.value.agenda
          .split('\n')
          .map(item => item.trim())
          .filter(Boolean)
          .map((item, index) => ({
            item_order: index + 1,
            title: item,
            description: null,
            duration_minutes: 15,
          })),
      },
    })
    await refresh()
    newMeetingOpen.value = false
    resetMeetingForm()
    toast.success('Meeting created.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not create the meeting.')
  } finally {
    saving.value = false
  }
}

function reviewLink(meetingId: string) {
  return `/meetings/${meetingId}/review`
}

function itemDue(deadline?: string | null) {
  return deadline ? formatDate(deadline) : 'No deadline'
}
</script>

<template>
  <div>
    <PageHeader
      title="Meetings"
      :description="`Scheduled sessions, live captures and verified minutes in ${departmentName}.`"
    >
      <template #actions>
        <Button variant="outline" @click="newMeetingOpen = true">
          <Plus class="h-4 w-4" />
          New meeting
        </Button>
      </template>
    </PageHeader>

    <LoadingState v-if="pending" class="mt-6" />
    <ErrorState v-else-if="error" class="mt-6" :message="error.message" @retry="refresh" />

    <template v-else>
      <div class="mt-6 flex flex-wrap items-end justify-between gap-3 border-b">
        <div class="flex items-center gap-1" role="tablist" aria-label="Filter meetings">
          <button
            v-for="filter in filters"
            :key="filter.value"
            role="tab"
            :aria-selected="activeFilter === filter.value"
            class="relative inline-flex h-9 items-center gap-1.5 px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground"
            :class="
              activeFilter === filter.value
                ? 'text-foreground after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-brand after:content-[\'\']'
                : ''
            "
            @click="activeFilter = filter.value"
          >
            {{ filter.label }}
            <span class="tabular-nums text-[13px] text-muted-foreground">{{ filter.count }}</span>
          </button>
        </div>
        <p v-if="dashboard?.live_meeting" class="pb-2 text-[13px] text-muted-foreground">
          {{ dashboard.live_meeting.title }} is live
        </p>
      </div>

      <Card v-if="filteredMeetings.length" class="mt-4 overflow-hidden" data-testid="meeting-list">
        <div
          v-for="meeting in filteredMeetings"
          :key="meeting.id"
          class="flex flex-col gap-3 border-b px-5 py-4 last:border-b-0 sm:flex-row sm:items-center"
          data-testid="meeting-row"
        >
          <div class="w-28 shrink-0">
            <p class="text-sm font-medium">{{ formatDate(meeting.scheduled_start) }}</p>
            <p class="mt-0.5 tabular-nums text-[13px] text-muted-foreground">
              {{ formatTimeRange(meeting.scheduled_start, meeting.scheduled_end) }}
            </p>
          </div>

          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <p class="truncate text-sm font-medium">{{ meeting.title }}</p>
              <StatusBadge :status="meeting.status" />
            </div>
            <p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted-foreground">
              <span>{{ plural(meeting.participant_count, 'participant') }}</span>
              <span aria-hidden="true">·</span>
              <span>{{ plural(meeting.agendas.length, 'agenda item') }}</span>
              <span v-if="meeting.summary?.is_verified" aria-hidden="true">·</span>
              <span v-if="meeting.summary?.is_verified">Minutes verified</span>
            </p>
          </div>

          <div class="flex shrink-0 items-center gap-2">
            <Button v-if="meeting.status === 'In Progress'" as-child size="sm">
              <NuxtLink :to="`/meetings/${meeting.id}/live`">Open live</NuxtLink>
            </Button>
            <Button v-else-if="meeting.status === 'Scheduled'" as-child size="sm" variant="outline">
              <NuxtLink :to="`/meetings/${meeting.id}/live`">Open console</NuxtLink>
            </Button>
            <Button v-else-if="meeting.status === 'Completed'" as-child size="sm" variant="outline">
              <NuxtLink :to="reviewLink(meeting.id)">View minutes</NuxtLink>
            </Button>
          </div>
        </div>
        <div class="flex items-center justify-between px-5 py-3 text-[13px] text-muted-foreground">
          <span>{{ filteredMeetings.length }} of {{ plural(meetingList.length, 'meeting') }}</span>
          <span class="flex items-center gap-1.5">
            <CalendarDays class="h-3.5 w-3.5" />
            {{ departmentName }}
          </span>
        </div>
      </Card>

      <EmptyState
        v-else
        class="mt-4"
        :title="meetingList.length ? 'No meetings in this view' : 'No meetings yet'"
        :description="meetingList.length ? 'Switch the filter to see the other meetings.' : 'Schedule the first meeting to prepare an agenda and minutes.'"
      >
        <Button variant="outline" size="sm" class="mt-3" @click="newMeetingOpen = true">
          <Plus class="h-4 w-4" />
          New meeting
        </Button>
      </EmptyState>

      <div class="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card class="flex flex-col lg:col-span-7">
          <CardHeader class="pb-3">
            <CardTitle>Recent decisions</CardTitle>
            <CardDescription class="mt-1">Agreed outcomes from verified minutes.</CardDescription>
          </CardHeader>
          <div v-if="recentDecisions.length" class="flex-1 border-t">
            <div
              v-for="decision in recentDecisions"
              :key="decision.id"
              class="flex items-start gap-3 border-b px-5 py-3 last:border-b-0"
            >
              <div class="min-w-0 flex-1">
                <p class="text-[13px] leading-snug">{{ decision.text }}</p>
                <p class="mt-1 text-[13px] text-muted-foreground">
                  {{ decision.meeting_title }} · {{ formatDate(decision.date) }}
                </p>
              </div>
              <NuxtLink
                :to="reviewLink(decision.meeting_id)"
                class="shrink-0 text-[13px] font-medium text-brand hover:underline"
              >
                Minutes
              </NuxtLink>
            </div>
          </div>
          <div v-else class="flex flex-1 items-center border-t px-5 py-6">
            <p class="text-[13px] text-muted-foreground">No verified decisions yet.</p>
          </div>
        </Card>

        <Card class="flex flex-col lg:col-span-5">
          <CardHeader class="pb-3">
            <CardTitle>Open action items</CardTitle>
            <CardDescription class="mt-1">Tasks from verified minutes that are not complete.</CardDescription>
          </CardHeader>
          <div v-if="openActionItems.length" class="flex-1 border-t">
            <div
              v-for="item in openActionItems"
              :key="item.id"
              class="flex items-center gap-3 border-b px-5 py-3 last:border-b-0"
            >
              <div class="min-w-0 flex-1">
                <p class="line-clamp-1 text-[13px] font-medium">{{ item.task }}</p>
                <p class="mt-0.5 text-[13px] text-muted-foreground">
                  {{ item.assignee || 'Unassigned' }} · due {{ itemDue(item.deadline) }}
                </p>
              </div>
              <StatusBadge :status="item.status" />
            </div>
          </div>
          <div v-else class="flex flex-1 items-center border-t px-5 py-6">
            <p class="text-[13px] text-muted-foreground">No open action items.</p>
          </div>
        </Card>
      </div>
    </template>

    <Dialog v-model:open="newMeetingOpen">
      <DialogContent class="max-w-lg" data-testid="new-meeting">
        <DialogHeader>
          <DialogTitle>New meeting</DialogTitle>
          <DialogDescription>
            Just create it. The start time and department are prepared for you.
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-4">
          <div class="space-y-1.5">
            <Label for="meeting-title">
              Title
              <span class="font-normal text-muted-foreground">(optional)</span>
            </Label>
            <Input id="meeting-title" v-model="meetingForm.title" placeholder="e.g. Research Committee review" />
            <p class="text-[12px] text-muted-foreground">
              Left blank, it becomes “{{ departmentName }} meeting”.
            </p>
          </div>

          <button
            type="button"
            class="text-[13px] font-medium text-brand hover:underline"
            @click="showMore = !showMore"
          >
            {{ showMore ? 'Hide optional details' : 'Add description or agenda (optional)' }}
          </button>

          <div v-if="showMore" class="space-y-4">
            <div class="space-y-1.5">
              <Label for="meeting-description">Description</Label>
              <Input id="meeting-description" v-model="meetingForm.description" placeholder="Optional context" />
            </div>
            <div class="space-y-1.5">
              <Label for="meeting-agenda">Agenda</Label>
              <Textarea id="meeting-agenda" v-model="meetingForm.agenda" rows="3" placeholder="One item per line" />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" :disabled="saving" @click="newMeetingOpen = false">Cancel</Button>
          <Button :disabled="saving" @click="addMeeting">
            {{ saving ? 'Creating…' : 'Create meeting' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
