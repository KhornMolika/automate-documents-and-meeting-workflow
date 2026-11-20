<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Check, Download, Plus, X } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '~/components/ui/card'
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
import ErrorState from '~/components/workspace/ErrorState.vue'
import LoadingState from '~/components/workspace/LoadingState.vue'
import PageHeader from '~/components/workspace/PageHeader.vue'
import StatusBadge from '~/components/workspace/StatusBadge.vue'
import { useApi } from '~/composables/useApi'
import { formatDate, formatTimeRange, parseDiscussionPoints, plural } from '~/lib/format'
import type { Meeting, MeetingSummary, MinutesOfMeeting, MomPayload, TranscriptSegment } from '~/types/api'

useHead({ title: 'Minutes review · ACLEDA University' })

const route = useRoute()
const api = useApi()
const meetingId = computed(() => String(route.params.id))
const { data, pending, error, refresh } = await useAsyncData(`review-${meetingId.value}`, async () => {
  const [meeting, transcripts] = await Promise.all([
    api<Meeting>(`/meetings/${meetingId.value}`),
    api<TranscriptSegment[]>(`/meetings/${meetingId.value}/transcripts`),
  ])
  return { meeting, transcripts }
})

const meeting = computed(() => data.value?.meeting)
const sourceTranscripts = computed(() => data.value?.transcripts ?? [])
const mom = reactive({
  executiveSummary: '',
  discussionPoints: [] as string[],
  decisions: [] as { agendaTopic: string, decisionText: string }[],
  actionItems: [] as { taskDescription: string, assigneeName: string, deadline: string }[],
})
const isVerified = ref(false)
const generated = ref(false)
const generating = ref(false)
const saving = ref(false)
const publishing = ref(false)
const approveOpen = ref(false)
const draftSaved = ref(false)
const aiError = ref('')
const editingTranscriptId = ref('')
const transcriptDraftOriginal = ref('')
const transcriptDraftTranslated = ref('')
const savingTranscript = ref(false)

function hydrate(summary?: MeetingSummary | null) {
  if (!summary) {
    mom.executiveSummary = ''
    mom.discussionPoints = []
    mom.decisions = []
    mom.actionItems = []
    isVerified.value = false
    return
  }
  mom.executiveSummary = summary.executive_summary
  mom.discussionPoints = parseDiscussionPoints(summary.discussion_highlights)
  mom.decisions = summary.decisions.map(decision => ({
    agendaTopic: decision.agenda_topic ?? '',
    decisionText: decision.decision_text,
  }))
  mom.actionItems = summary.action_items.map(item => ({
    taskDescription: item.task_description,
    assigneeName: item.raw_assignee_name ?? '',
    deadline: item.deadline ?? '',
  }))
  isVerified.value = summary.is_verified
  generated.value = true
}

watch(meeting, value => hydrate(value?.summary), { immediate: true })

const itemSummary = computed(() => `${plural(mom.decisions.length, 'decision')} · ${plural(mom.actionItems.length, 'action item')}`)
const hasDraft = computed(() =>
  generated.value
  || !!meeting.value?.summary
  || mom.executiveSummary.trim().length > 0
  || mom.discussionPoints.length > 0
  || mom.decisions.length > 0
  || mom.actionItems.length > 0,
)
const canGenerate = computed(() => sourceTranscripts.value.length > 0 && !hasDraft.value)

function editTranscript(segment: TranscriptSegment) {
  editingTranscriptId.value = segment.id
  transcriptDraftOriginal.value = segment.original_text
  transcriptDraftTranslated.value = segment.translated_text ?? ''
}

function cancelTranscriptEdit() {
  editingTranscriptId.value = ''
  transcriptDraftOriginal.value = ''
  transcriptDraftTranslated.value = ''
}

async function saveTranscript(segmentId: string) {
  if (!transcriptDraftOriginal.value.trim()) {
    toast.error('Transcript text cannot be empty.')
    return
  }
  savingTranscript.value = true
  try {
    await api(`/meetings/${meetingId.value}/transcripts/${segmentId}`, {
      method: 'PUT',
      body: {
        original_text: transcriptDraftOriginal.value.trim(),
        translated_text: transcriptDraftTranslated.value.trim(),
      },
    })
    await refresh()
    cancelTranscriptEdit()
    toast.success('Transcript corrected.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not save the transcript correction.')
  } finally {
    savingTranscript.value = false
  }
}

function addPoint() {
  mom.discussionPoints.push('')
}

function removePoint(index: number) {
  mom.discussionPoints.splice(index, 1)
}

function addDecision() {
  mom.decisions.push({ agendaTopic: '', decisionText: '' })
}

function removeDecision(index: number) {
  mom.decisions.splice(index, 1)
}

function addActionItem() {
  mom.actionItems.push({ taskDescription: '', assigneeName: '', deadline: '' })
}

function removeActionItem(index: number) {
  mom.actionItems.splice(index, 1)
}

function payload(): MomPayload {
  return {
    executive_summary: mom.executiveSummary,
    discussion_points: mom.discussionPoints.map(point => point.trim()).filter(Boolean),
    decisions: mom.decisions
      .filter(decision => decision.decisionText.trim())
      .map(decision => ({
        agenda_topic: decision.agendaTopic.trim() || null,
        decision_text: decision.decisionText.trim(),
        context_notes: null,
      })),
    action_items: mom.actionItems
      .filter(item => item.taskDescription.trim())
      .map(item => ({
        task_description: item.taskDescription.trim(),
        assignee_name: item.assigneeName.trim() || null,
        deadline: item.deadline || null,
        confidence_score: 0.95,
      })),
  }
}

async function generateDraft() {
  generating.value = true
  aiError.value = ''
  try {
    const result = await api<MinutesOfMeeting>(`/meetings/${meetingId.value}/synthesize-mom`, {
      method: 'POST',
    })
    mom.executiveSummary = result.executive_summary
    mom.discussionPoints = result.discussion_points
    mom.decisions = result.decisions.map(decision => ({
      agendaTopic: decision.agenda_topic ?? '',
      decisionText: decision.decision_text,
    }))
    mom.actionItems = result.action_items.map(item => ({
      taskDescription: item.task_description,
      assigneeName: item.assignee_name ?? '',
      deadline: item.deadline ?? '',
    }))
    generated.value = true
    toast.success('Draft generated. Review every section before publishing.')
  } catch (err: any) {
    aiError.value = err?.data?.detail ?? 'Could not generate a draft.'
  } finally {
    generating.value = false
  }
}

async function saveDraft() {
  saving.value = true
  try {
    const summary = await api<MeetingSummary>(`/meetings/${meetingId.value}/mom-draft`, {
      method: 'PUT',
      body: payload(),
    })
    hydrate(summary)
    draftSaved.value = true
    toast.success('Draft saved.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not save the draft.')
  } finally {
    saving.value = false
  }
}

async function downloadFile(url: string, filename: string) {
  try {
    const blob = await api<Blob>(url, { responseType: 'blob' })
    const objectUrl = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = objectUrl
    anchor.download = filename
    anchor.click()
    URL.revokeObjectURL(objectUrl)
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Download failed.')
  }
}

async function publish() {
  if (!mom.executiveSummary.trim()) {
    toast.error('Add an executive summary before publishing.')
    return
  }
  publishing.value = true
  try {
    const summary = await api<MeetingSummary>(`/meetings/${meetingId.value}/approve-mom`, {
      method: 'POST',
      body: {
        ...payload(),
        export_to_google_docs: false,
        export_to_google_sheets: false,
      },
    })
    hydrate(summary)
    approveOpen.value = false

    try {
      await api(`/workspace/meetings/${meetingId.value}/export-docs`, { method: 'POST' })
    } catch (err: any) {
      toast.error(err?.data?.detail ?? 'Minutes verified, but the DOCX export failed.')
    }
    try {
      await api(`/workspace/meetings/${meetingId.value}/export-sheets`, { method: 'POST' })
    } catch (err: any) {
      toast.error(err?.data?.detail ?? 'Minutes verified, but the CSV export failed.')
    }
    await refresh()
    toast.success('Minutes verified and published.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not publish the minutes.')
  } finally {
    publishing.value = false
  }
}
</script>

<template>
  <div>
    <NuxtLink
      to="/meetings"
      class="mb-4 inline-flex items-center gap-1.5 text-[13px] text-muted-foreground transition-colors hover:text-foreground"
    >
      <ArrowLeft class="h-3.5 w-3.5" />
      Meetings
    </NuxtLink>

    <LoadingState v-if="pending" />
    <ErrorState v-else-if="error" :message="error.message" @retry="refresh" />

    <template v-else-if="meeting">
      <PageHeader
        title="Minutes review"
        :description="`${meeting.title} · ${formatDate(meeting.scheduled_start)} · ${formatTimeRange(meeting.scheduled_start, meeting.scheduled_end)}`"
      >
        <template #meta>
          <StatusBadge :status="isVerified ? 'Verified' : 'Draft'" />
          <span class="text-[13px] text-muted-foreground">{{ itemSummary }}</span>
        </template>
        <template #actions>
          <Button v-if="!isVerified" variant="outline" :disabled="saving || !hasDraft" @click="saveDraft">
            {{ saving ? 'Saving…' : 'Save draft' }}
          </Button>
          <Button v-if="!isVerified" :disabled="publishing || !hasDraft" @click="approveOpen = true">
            {{ publishing ? 'Publishing…' : 'Approve & publish' }}
          </Button>
        </template>
      </PageHeader>

      <div v-if="isVerified" class="mt-4 flex flex-col gap-3 rounded-lg border border-positive/20 bg-positive-soft px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex items-start gap-2.5">
          <Check class="mt-0.5 h-4 w-4 text-positive" />
          <div>
            <p class="text-sm font-medium text-positive">Minutes verified</p>
            <p class="mt-0.5 text-[13px] text-positive">
              This record is read-only. Download the DOCX or the action-item CSV.
            </p>
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" @click="downloadFile(`/workspace/meetings/${meeting.id}/minutes.docx`, 'minutes.docx')">
            <Download class="h-3.5 w-3.5" />
            DOCX
          </Button>
          <Button variant="outline" size="sm" @click="downloadFile(`/workspace/meetings/${meeting.id}/action-items.csv`, 'action-items.csv')">
            <Download class="h-3.5 w-3.5" />
            CSV
          </Button>
        </div>
      </div>

      <div class="mt-4 grid grid-cols-1 items-start gap-4 xl:grid-cols-12">
        <Card class="flex flex-col xl:col-span-5 xl:h-[calc(100vh-10rem)]">
          <CardHeader class="flex-row items-start justify-between gap-3 pb-3">
            <div>
              <CardTitle>Source transcript</CardTitle>
              <CardDescription class="mt-1">Correct any misheard Khmer words before generating the draft.</CardDescription>
            </div>
            <Badge variant="outline">{{ plural(sourceTranscripts.length, 'segment') }}</Badge>
          </CardHeader>
          <div v-if="sourceTranscripts.length" class="max-h-[480px] flex-1 overflow-y-auto border-t p-5 xl:max-h-none">
            <div
              v-for="segment in sourceTranscripts"
              :key="segment.id"
              class="border-b py-3.5 first:pt-0 last:border-b-0 last:pb-0"
            >
              <div class="flex items-center justify-between gap-3">
                <p class="text-[13px] font-medium">{{ segment.speaker_label }}</p>
                <div class="flex items-center gap-1.5">
                  <p class="tabular-nums text-[13px] text-muted-foreground">
                    {{ Math.floor(segment.start_timestamp / 60).toString().padStart(2, '0') }}:{{ Math.floor(segment.start_timestamp % 60).toString().padStart(2, '0') }}
                  </p>
                  <Button
                    v-if="!isVerified && editingTranscriptId !== segment.id"
                    variant="ghost"
                    size="sm"
                    @click="editTranscript(segment)"
                  >
                    Edit
                  </Button>
                </div>
              </div>
              <div v-if="editingTranscriptId === segment.id" class="mt-2 space-y-2">
                <Textarea
                  v-model="transcriptDraftOriginal"
                  data-testid="transcript-original"
                  rows="4"
                  class="font-khmer"
                />
                <Textarea
                  v-model="transcriptDraftTranslated"
                  data-testid="transcript-translation"
                  rows="3"
                  placeholder="English translation"
                />
                <div class="flex gap-2">
                  <Button size="sm" :disabled="savingTranscript" @click="saveTranscript(segment.id)">
                    {{ savingTranscript ? 'Saving…' : 'Save correction' }}
                  </Button>
                  <Button size="sm" variant="outline" :disabled="savingTranscript" @click="cancelTranscriptEdit">
                    Cancel
                  </Button>
                </div>
              </div>
              <div v-else>
                <p class="mt-1.5 font-khmer text-sm leading-relaxed">{{ segment.original_text }}</p>
                <p v-if="segment.translated_text" class="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
                  {{ segment.translated_text }}
                </p>
              </div>
            </div>
          </div>
          <div v-else class="flex flex-1 items-center border-t px-5 py-8">
            <p class="text-[13px] text-muted-foreground">
              No transcript segments have been recorded for this meeting.
            </p>
          </div>
        </Card>

        <Card class="flex flex-col xl:col-span-7 xl:h-[calc(100vh-10rem)]">
          <CardHeader class="pb-3">
            <CardTitle>Minutes of meeting</CardTitle>
            <CardDescription>
              {{ isVerified ? 'These minutes are verified and read-only.' : 'Edit the generated record. The approved version becomes the official minutes.' }}
            </CardDescription>
          </CardHeader>

          <CardContent class="flex-1 space-y-6 overflow-y-auto border-t pt-5">
            <div v-if="!hasDraft" class="rounded-md border border-dashed border-input bg-muted/30 p-4">
              <p class="text-[13px] font-medium">No draft yet</p>
              <p class="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                Generate a draft from {{ sourceTranscripts.length }} transcript segment{{ sourceTranscripts.length === 1 ? '' : 's' }}, then review and edit every section.
              </p>
              <p v-if="aiError" class="mt-2 text-[13px] text-negative">{{ aiError }}</p>
              <Button variant="outline" size="sm" class="mt-3" :disabled="generating || !canGenerate" @click="generateDraft">
                {{ generating ? 'Generating…' : 'Generate draft' }}
              </Button>
            </div>

            <section class="space-y-2">
              <div class="flex items-center justify-between gap-3">
                <Label for="mom-summary">Executive summary</Label>
                <span class="text-[13px] text-muted-foreground">{{ isVerified ? 'Verified' : 'Editable' }}</span>
              </div>
              <Textarea id="mom-summary" v-model="mom.executiveSummary" rows="5" :readonly="isVerified" />
            </section>

            <section class="space-y-2">
              <div class="flex items-center justify-between gap-3">
                <Label>Key discussion points</Label>
                <span class="text-[13px] text-muted-foreground">{{ plural(mom.discussionPoints.length, 'point') }}</span>
              </div>
              <div class="space-y-2">
                <div v-for="(_, index) in mom.discussionPoints" :key="index" class="flex items-start gap-2">
                  <span class="mt-3 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden="true" />
                  <Input
                    v-model="mom.discussionPoints[index]"
                    :aria-label="`Discussion point ${index + 1}`"
                    class="flex-1"
                    :readonly="isVerified"
                  />
                  <Button
                    v-if="!isVerified"
                    variant="ghost"
                    size="icon-sm"
                    :aria-label="`Remove discussion point ${index + 1}`"
                    @click="removePoint(index)"
                  >
                    <X class="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              <Button v-if="!isVerified" variant="ghost" size="sm" class="px-0 text-brand" @click="addPoint">
                <Plus class="h-3.5 w-3.5" />
                Add discussion point
              </Button>
            </section>

            <section class="space-y-2">
              <div class="flex items-center justify-between gap-3">
                <Label>Formal decisions</Label>
                <span class="text-[13px] text-muted-foreground">{{ plural(mom.decisions.length, 'decision') }}</span>
              </div>
              <div class="divide-y border-y">
                <div v-for="(_, index) in mom.decisions" :key="index" class="space-y-2 py-3 first:pt-2.5 last:pb-2.5">
                  <div class="flex items-center gap-2">
                    <Input
                      v-model="mom.decisions[index].agendaTopic"
                      :aria-label="`Decision ${index + 1} agenda topic`"
                      placeholder="Agenda topic"
                      class="h-8 max-w-[260px] text-[13px]"
                      :readonly="isVerified"
                    />
                    <Button
                      v-if="!isVerified"
                      variant="ghost"
                      size="icon-sm"
                      class="ml-auto"
                      :aria-label="`Remove decision ${index + 1}`"
                      @click="removeDecision(index)"
                    >
                      <X class="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  <Input
                    v-model="mom.decisions[index].decisionText"
                    :aria-label="`Decision ${index + 1} text`"
                    placeholder="What was agreed"
                    :readonly="isVerified"
                  />
                </div>
              </div>
              <Button v-if="!isVerified" variant="ghost" size="sm" class="px-0 text-brand" @click="addDecision">
                <Plus class="h-3.5 w-3.5" />
                Add decision
              </Button>
            </section>

            <section class="space-y-2">
              <div class="flex items-center justify-between gap-3">
                <Label>Action items</Label>
                <span class="text-[13px] text-muted-foreground">{{ plural(mom.actionItems.length, 'action item') }}</span>
              </div>
              <div class="divide-y border-y">
                <div v-for="(_, index) in mom.actionItems" :key="index" class="space-y-2 py-3 first:pt-2.5 last:pb-2.5">
                  <div class="flex items-start gap-2">
                    <Input
                      v-model="mom.actionItems[index].taskDescription"
                      :aria-label="`Action item ${index + 1} task`"
                      placeholder="Task description"
                      class="flex-1"
                      :readonly="isVerified"
                    />
                    <Button
                      v-if="!isVerified"
                      variant="ghost"
                      size="icon-sm"
                      :aria-label="`Remove action item ${index + 1}`"
                      @click="removeActionItem(index)"
                    >
                      <X class="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <div class="space-y-1">
                      <Label :for="`action-owner-${index}`" class="text-[13px] text-muted-foreground">Assignee</Label>
                      <Input :id="`action-owner-${index}`" v-model="mom.actionItems[index].assigneeName" placeholder="Name" :readonly="isVerified" />
                    </div>
                    <div class="space-y-1">
                      <Label :for="`action-deadline-${index}`" class="text-[13px] text-muted-foreground">Deadline</Label>
                      <Input :id="`action-deadline-${index}`" v-model="mom.actionItems[index].deadline" type="date" :readonly="isVerified" />
                    </div>
                  </div>
                </div>
              </div>
              <Button v-if="!isVerified" variant="ghost" size="sm" class="px-0 text-brand" @click="addActionItem">
                <Plus class="h-3.5 w-3.5" />
                Add action item
              </Button>
            </section>

            <div class="flex flex-col gap-1 border-t pt-4 text-[13px] text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
              <span>{{ isVerified ? 'Verified record' : draftSaved ? 'Draft saved' : 'Draft · not yet verified' }}</span>
              <span>{{ itemSummary }}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Dialog v-model:open="approveOpen">
        <DialogContent data-testid="approve-minutes">
          <DialogHeader>
            <DialogTitle>Publish these minutes?</DialogTitle>
            <DialogDescription>
              This marks the record verified. The export creates a local DOCX and CSV from the stored minutes.
            </DialogDescription>
          </DialogHeader>
          <div class="rounded-md border bg-muted/40 p-3 text-[13px] text-muted-foreground">
            <p class="font-medium text-foreground">{{ meeting.title }}</p>
            <p class="mt-1">{{ itemSummary }}</p>
          </div>
          <DialogFooter>
            <Button variant="outline" :disabled="publishing" @click="approveOpen = false">Cancel</Button>
            <Button :disabled="publishing" @click="publish">
              <span v-if="publishing" class="h-3 w-3 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
              {{ publishing ? 'Publishing…' : 'Confirm & publish' }}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </template>
  </div>
</template>
