<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { MoreHorizontal, Pencil, Plus, Search, Trash2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '~/components/ui/button'
import { Card } from '~/components/ui/card'
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
import { Select } from '~/components/ui/select'
import { Textarea } from '~/components/ui/textarea'
import EmptyState from '~/components/workspace/EmptyState.vue'
import ErrorState from '~/components/workspace/ErrorState.vue'
import LoadingState from '~/components/workspace/LoadingState.vue'
import PageHeader from '~/components/workspace/PageHeader.vue'
import StatusBadge from '~/components/workspace/StatusBadge.vue'
import { useApi } from '~/composables/useApi'
import { useAuth } from '~/composables/useAuth'
import { formatDate, formatTimeRange, plural } from '~/lib/format'
import type { Meeting, MeetingPage } from '~/types/api'

useHead({ title: 'Meetings · ACLEDA University' })

type MeetingView = 'all' | 'scheduled' | 'draft' | 'published'

const api = useApi()
const { user } = useAuth()
const departmentName = computed(() => user.value?.department?.name ?? 'Department workspace')

const page = ref(1)
const pageSize = ref(10)
const pageSizeOptions = [
  { value: 10, label: '10 rows' },
  { value: 20, label: '20 rows' },
  { value: 50, label: '50 rows' },
]
const view = ref<MeetingView>('all')
const search = ref('')
const debouncedSearch = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

const { data, pending, error, refresh } = await useAsyncData(
  'meetings-page',
  () => api<MeetingPage>('/meetings', {
    query: {
      page: page.value,
      page_size: pageSize.value,
      view: view.value,
      q: debouncedSearch.value || undefined,
    },
  }),
  { watch: [page, pageSize, view, debouncedSearch] },
)

const meetingList = computed(() => data.value?.items ?? [])
const total = computed(() => data.value?.total ?? 0)
const pages = computed(() => data.value?.pages ?? 1)
const counts = computed(() => data.value?.counts ?? { all: 0, scheduled: 0, draft: 0, published: 0 })
const rangeStart = computed(() => total.value ? (page.value - 1) * pageSize.value + 1 : 0)
const rangeEnd = computed(() => Math.min(page.value * pageSize.value, total.value))

watch(search, (value) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    debouncedSearch.value = value.trim()
    page.value = 1
  }, 300)
})

watch([view, pageSize], () => {
  page.value = 1
})

function stateOf(meeting: Meeting) {
  if (meeting.summary?.is_verified) return 'Published'
  if (meeting.summary) return 'Draft'
  return 'Scheduled'
}

function actionLabel(meeting: Meeting) {
  const state = stateOf(meeting)
  if (state === 'Published') return 'View minutes'
  if (state === 'Draft') return 'Continue minutes'
  return 'Open workspace'
}

const filters = computed(() => [
  { value: 'all' as const, label: 'All', count: counts.value.all ?? 0 },
  { value: 'scheduled' as const, label: 'Scheduled', count: counts.value.scheduled ?? 0 },
  { value: 'draft' as const, label: 'Draft', count: counts.value.draft ?? 0 },
  { value: 'published' as const, label: 'Published', count: counts.value.published ?? 0 },
])

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
    const created = await api<Meeting>('/meetings', {
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
    newMeetingOpen.value = false
    resetMeetingForm()
    toast.success('Meeting created.')
    await navigateTo(`/meetings/${created.id}/review`)
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not create the meeting.')
  } finally {
    saving.value = false
  }
}

const openMenuId = ref('')
const renameOpen = ref(false)
const renameTarget = ref<Meeting | null>(null)
const renameTitle = ref('')
const renaming = ref(false)
const deleteOpen = ref(false)
const deleteTarget = ref<Meeting | null>(null)
const deleting = ref(false)

function toggleMenu(meetingId: string) {
  openMenuId.value = openMenuId.value === meetingId ? '' : meetingId
}

function closeMenu() {
  openMenuId.value = ''
}

function openRename(meeting: Meeting) {
  closeMenu()
  renameTarget.value = meeting
  renameTitle.value = meeting.title
  renameOpen.value = true
}

async function renameMeeting() {
  const meeting = renameTarget.value
  const title = renameTitle.value.trim()
  if (!meeting || !title) {
    toast.error('Enter a meeting title.')
    return
  }
  renaming.value = true
  try {
    await api(`/meetings/${meeting.id}`, {
      method: 'PATCH',
      body: { title },
    })
    renameOpen.value = false
    renameTarget.value = null
    await refresh()
    toast.success('Meeting renamed.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not rename the meeting.')
  } finally {
    renaming.value = false
  }
}

function openDelete(meeting: Meeting) {
  closeMenu()
  deleteTarget.value = meeting
  deleteOpen.value = true
}

async function deleteMeeting() {
  const meeting = deleteTarget.value
  if (!meeting) return
  deleting.value = true
  try {
    await api(`/meetings/${meeting.id}`, { method: 'DELETE' })
    deleteOpen.value = false
    deleteTarget.value = null
    if (meetingList.value.length === 1 && page.value > 1) {
      page.value -= 1
    } else {
      await refresh()
    }
    toast.success('Meeting deleted.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not delete the meeting.')
  } finally {
    deleting.value = false
  }
}

function goToPage(next: number) {
  page.value = Math.min(Math.max(1, next), pages.value)
}

onMounted(() => document.addEventListener('click', closeMenu))
onUnmounted(() => {
  document.removeEventListener('click', closeMenu)
  if (searchTimer) clearTimeout(searchTimer)
})
</script>

<template>
  <div>
    <PageHeader
      title="Meetings"
      :description="`Recordings, transcripts and published minutes in ${departmentName}.`"
    >
      <template #actions>
        <Button variant="outline" @click="newMeetingOpen = true">
          <Plus class="h-4 w-4" />
          New meeting
        </Button>
      </template>
    </PageHeader>

    <LoadingState v-if="pending && !data" class="mt-6" />
    <ErrorState v-else-if="error" class="mt-6" :message="error.message" @retry="refresh" />

    <template v-else>
      <div class="mt-6 flex flex-col gap-2 sm:flex-row sm:items-center">
        <div class="relative min-w-0 flex-1">
          <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            v-model="search"
            type="search"
            placeholder="Search meetings"
            aria-label="Search meetings"
            class="pl-9"
          />
        </div>
        <div class="flex items-center gap-2">
          <label for="meetings-page-size" class="text-[13px] text-muted-foreground">Show</label>
          <Select
            id="meetings-page-size"
            v-model="pageSize"
            :options="pageSizeOptions"
            aria-label="Rows per page"
            class="w-32"
          />
        </div>
      </div>

      <div class="mt-4 flex flex-wrap items-end justify-between gap-3 border-b">
        <div class="no-scrollbar flex items-center gap-1 overflow-x-auto" role="tablist" aria-label="Filter meetings">
          <button
            v-for="filter in filters"
            :key="filter.value"
            role="tab"
            :aria-selected="view === filter.value"
            class="relative inline-flex h-9 items-center gap-1.5 px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground"
            :class="
              view === filter.value
                ? 'text-foreground after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-brand after:content-[\'\']'
                : ''
            "
            @click="view = filter.value"
          >
            {{ filter.label }}
            <span class="tabular-nums text-[13px] text-muted-foreground">{{ filter.count }}</span>
          </button>
        </div>
        <p v-if="total" class="pb-2 text-[13px] text-muted-foreground">
          {{ total }} {{ total === 1 ? 'meeting' : 'meetings' }}
        </p>
      </div>

      <Card v-if="meetingList.length" class="mt-4 overflow-visible" data-testid="meeting-list">
        <div
          v-for="meeting in meetingList"
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
              <StatusBadge :status="stateOf(meeting)" />
            </div>
            <p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted-foreground">
              <span>{{ plural(meeting.participant_count, 'participant') }}</span>
              <span aria-hidden="true">·</span>
              <span>{{ plural(meeting.agendas.length, 'agenda item') }}</span>
              <span v-if="meeting.summary" aria-hidden="true">·</span>
              <span v-if="meeting.summary">{{ plural(meeting.summary.action_items.length, 'action item') }}</span>
            </p>
          </div>

          <div class="flex shrink-0 items-center gap-2">
            <Button as-child size="sm" variant="outline">
              <NuxtLink :to="`/meetings/${meeting.id}/review`">{{ actionLabel(meeting) }}</NuxtLink>
            </Button>
            <div class="relative" @click.stop>
              <Button
                variant="ghost"
                size="icon-sm"
                :aria-label="`Actions for ${meeting.title}`"
                :aria-expanded="openMenuId === meeting.id"
                @click="toggleMenu(meeting.id)"
              >
                <MoreHorizontal class="h-4 w-4" />
              </Button>
              <div
                v-if="openMenuId === meeting.id"
                class="absolute right-0 top-full z-30 mt-1 w-40 rounded-md border bg-card p-1 shadow-lg"
                role="menu"
              >
                <button
                  type="button"
                  class="flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-[13px] transition-colors hover:bg-secondary"
                  role="menuitem"
                  @click="openRename(meeting)"
                >
                  <Pencil class="h-3.5 w-3.5" />
                  Rename
                </button>
                <button
                  type="button"
                  class="flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-[13px] text-negative transition-colors hover:bg-negative-soft"
                  role="menuitem"
                  @click="openDelete(meeting)"
                >
                  <Trash2 class="h-3.5 w-3.5" />
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="flex flex-col gap-3 border-t px-5 py-3 text-[13px] text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span>Showing {{ rangeStart }}–{{ rangeEnd }} of {{ total }}</span>
          <div class="flex items-center gap-1.5">
            <span class="mr-1">{{ departmentName }}</span>
            <Button variant="outline" size="sm" :disabled="page <= 1" @click="goToPage(page - 1)">
              Previous
            </Button>
            <span class="px-2 tabular-nums">{{ page }} / {{ pages }}</span>
            <Button variant="outline" size="sm" :disabled="page >= pages" @click="goToPage(page + 1)">
              Next
            </Button>
          </div>
        </div>
      </Card>

      <EmptyState
        v-else
        class="mt-4"
        :title="total ? 'No meetings on this page' : search || view !== 'all' ? 'No meetings match this view' : 'No meetings yet'"
        :description="total ? 'Go back to the previous page.' : search || view !== 'all' ? 'Clear the search or switch the filter.' : 'Create the first meeting, then add a recording or transcript.'"
      >
        <Button variant="outline" size="sm" class="mt-3" @click="newMeetingOpen = true">
          <Plus class="h-4 w-4" />
          New meeting
        </Button>
      </EmptyState>
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

    <Dialog v-model:open="renameOpen">
      <DialogContent class="max-w-md">
        <DialogHeader>
          <DialogTitle>Rename meeting</DialogTitle>
          <DialogDescription>This title appears in the workspace, minutes and document archive.</DialogDescription>
        </DialogHeader>
        <div class="space-y-1.5">
          <Label for="rename-meeting-title">Title</Label>
          <Input id="rename-meeting-title" v-model="renameTitle" @keyup.enter="renameMeeting" />
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="renaming" @click="renameOpen = false">Cancel</Button>
          <Button :disabled="renaming || !renameTitle.trim()" @click="renameMeeting">
            {{ renaming ? 'Saving…' : 'Save name' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="deleteOpen">
      <DialogContent class="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete this meeting?</DialogTitle>
          <DialogDescription>
            This permanently removes the meeting, its transcript, minutes, action items and archived document copy. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <div class="rounded-md border border-negative/20 bg-negative-soft px-3 py-2.5 text-[13px] text-negative">
          {{ deleteTarget?.title }}
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="deleting" @click="deleteOpen = false">Cancel</Button>
          <Button variant="destructive" :disabled="deleting" @click="deleteMeeting">
            {{ deleting ? 'Deleting…' : 'Delete meeting' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
