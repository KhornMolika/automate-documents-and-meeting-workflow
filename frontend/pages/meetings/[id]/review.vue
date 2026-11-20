<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  ArrowLeft,
  Check,
  Download,
  FileAudio,
  FileText,
  Link2,
  Plus,
  Upload,
  X,
} from 'lucide-vue-next'
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
import { Select } from '~/components/ui/select'
import { Textarea } from '~/components/ui/textarea'
import ErrorState from '~/components/workspace/ErrorState.vue'
import LoadingState from '~/components/workspace/LoadingState.vue'
import PageHeader from '~/components/workspace/PageHeader.vue'
import StatusBadge from '~/components/workspace/StatusBadge.vue'
import { useApi } from '~/composables/useApi'
import { formatDate, formatTimeRange, parseDiscussionPoints, plural } from '~/lib/format'
import type {
  Meeting,
  MeetingSummary,
  MinutesOfMeeting,
  MomPayload,
  TranscriptSegment,
  TranscriptionJob,
} from '~/types/api'

useHead({ title: 'Meeting workspace · ACLEDA University' })

const route = useRoute()
const api = useApi()
const meetingId = computed(() => String(route.params.id))

const { data, pending, error, refresh } = await useAsyncData(`workspace-${meetingId.value}`, async () => {
  const [meeting, transcripts, transcription] = await Promise.all([
    api<Meeting>(`/meetings/${meetingId.value}`),
    api<TranscriptSegment[]>(`/meetings/${meetingId.value}/transcripts`),
    api<TranscriptionJob | null>(`/meetings/${meetingId.value}/transcription`),
  ])
  return { meeting, transcripts, transcription }
})

const meeting = computed(() => data.value?.meeting)
const sourceTranscripts = computed(() => data.value?.transcripts ?? [])
const transcription = ref<TranscriptionJob | null>(null)
const mom = reactive({
  executiveSummary: '',
  discussionPoints: [] as string[],
  decisions: [] as { agendaTopic: string, decisionText: string }[],
  actionItems: [] as { taskDescription: string, assigneeName: string, deadline: string }[],
})
const isVerified = ref(false)
const generated = ref(false)
const generating = ref(false)
const generatingSeconds = ref(0)
const momLanguage = ref<'en' | 'km'>('en')
const draftLanguage = ref<'en' | 'km' | null>(null)
const saving = ref(false)
const publishing = ref(false)
const approveOpen = ref(false)
const inputOpen = ref(false)
const draftSaved = ref(false)
const aiError = ref('')
const editingTranscriptId = ref('')
const transcriptDraftSpeaker = ref('')
const transcriptDraftOriginal = ref('')
const savingTranscript = ref(false)

const inputTab = ref('recording')
const recordingFile = ref<File | null>(null)
const languageOptions = [
  { value: 'km', label: 'Khmer', description: 'Google transcription with local fallback' },
  { value: 'en', label: 'English', description: 'Local faster-whisper model' },
  { value: 'auto', label: 'Auto detect', description: 'Detect the spoken language' },
]
const recordingLanguage = ref('km')
const linkUrl = ref('')
const linkLanguage = ref('km')
const transcriptFile = ref<File | null>(null)
const transcriptText = ref('')
const submitting = ref(false)
const inputError = ref('')

let pollTimer: ReturnType<typeof setInterval> | null = null
let generateTimer: ReturnType<typeof setInterval> | null = null

watch(generating, (active) => {
  if (generateTimer) {
    clearInterval(generateTimer)
    generateTimer = null
  }
  generatingSeconds.value = 0
  if (!active) return
  generateTimer = setInterval(() => {
    generatingSeconds.value += 1
  }, 1000)
})

const isProcessing = computed(() => {
  const status = transcription.value?.status
  return status === 'queued' || status === 'processing'
})

const meetingState = computed(() => {
  if (transcription.value?.status === 'queued' || transcription.value?.status === 'processing') return 'Transcribing'
  if (transcription.value?.status === 'failed') return 'Transcription failed'
  if (meeting.value?.summary?.is_verified) return 'Published'
  if (meeting.value?.summary) return 'Draft'
  if (sourceTranscripts.value.length) return 'Transcript ready'
  return 'Scheduled'
})

function textHasKhmer(value: string | null | undefined) {
  return /[\u1780-\u17FF]/.test(value ?? '')
}

function hydrate(summary?: MeetingSummary | null) {
  if (!summary) {
    mom.executiveSummary = ''
    mom.discussionPoints = []
    mom.decisions = []
    mom.actionItems = []
    isVerified.value = false
    generated.value = false
    draftLanguage.value = null
    return
  }
  const combined = [
    summary.executive_summary,
    ...parseDiscussionPoints(summary.discussion_highlights),
    ...summary.decisions.map(decision => `${decision.agenda_topic ?? ''} ${decision.decision_text}`),
    ...summary.action_items.map(item => item.task_description),
  ].join(' ')
  draftLanguage.value = textHasKhmer(combined) ? 'km' : 'en'
  momLanguage.value = draftLanguage.value
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

watch(
  data,
  value => {
    transcription.value = value?.transcription ?? null
    hydrate(value?.meeting?.summary)
  },
  { immediate: true },
)

const itemSummary = computed(() => `${plural(mom.decisions.length, 'decision')} · ${plural(mom.actionItems.length, 'action item')}`)
const hasDraft = computed(() =>
  generated.value
  || !!meeting.value?.summary
  || mom.executiveSummary.trim().length > 0
  || mom.discussionPoints.length > 0
  || mom.decisions.length > 0
  || mom.actionItems.length > 0,
)
const canGenerate = computed(() => sourceTranscripts.value.length > 0 && !hasDraft.value && !isVerified.value)
const canRegenerate = computed(() => sourceTranscripts.value.length > 0 && hasDraft.value && !isVerified.value)

watch(
  sourceTranscripts,
  (items) => {
    if (hasDraft.value) return
    momLanguage.value = items.some(
      item => textHasKhmer(item.original_text) || textHasKhmer(item.translated_text),
    )
      ? 'km'
      : 'en'
  },
  { immediate: true },
)

const steps = computed(() => [
  {
    label: 'Transcript',
    state: sourceTranscripts.value.length ? 'done' : isProcessing.value ? 'current' : 'todo',
  },
  {
    label: 'Minutes',
    state: isVerified.value ? 'done' : hasDraft.value ? 'current' : 'todo',
  },
  {
    label: 'Published',
    state: isVerified.value ? 'done' : 'todo',
  },
] as { label: string, state: 'done' | 'current' | 'todo' }[])

function startPolling() {
  if (!import.meta.client) return
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const job = await api<TranscriptionJob | null>(`/meetings/${meetingId.value}/transcription`)
      transcription.value = job
      if (!job || job.status === 'completed' || job.status === 'failed') {
        stopPolling()
        if (job?.status === 'completed') {
          await refresh()
          toast.success(`Transcript ready · ${plural(job.segment_count, 'segment')}`)
        }
        if (job?.status === 'failed') {
          toast.error(job.error || 'Transcription failed.')
        }
      }
    } catch {
      stopPolling()
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startJob(job: TranscriptionJob) {
  transcription.value = job
  inputOpen.value = false
  resetInputForm()
  toast.success('Transcription started. This can take several minutes.')
  startPolling()
}

function resetInputForm() {
  inputError.value = ''
  recordingFile.value = null
  linkUrl.value = ''
  transcriptFile.value = null
  transcriptText.value = ''
}

function onRecordingFile(event: Event) {
  recordingFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

function onTranscriptFile(event: Event) {
  transcriptFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

async function submitRecording() {
  if (!recordingFile.value) {
    inputError.value = 'Choose an audio or video recording first.'
    return
  }
  submitting.value = true
  inputError.value = ''
  try {
    const form = new FormData()
    form.append('file', recordingFile.value)
    form.append('language', recordingLanguage.value)
    const job = await api<TranscriptionJob>(`/meetings/${meetingId.value}/recording`, {
      method: 'POST',
      body: form,
    })
    startJob(job)
  } catch (err: any) {
    inputError.value = err?.data?.detail ?? 'Could not start the transcription.'
  } finally {
    submitting.value = false
  }
}

function isLiveMeetingPage(value: string) {
  try {
    const host = new URL(value).hostname.toLowerCase().replace(/\.$/, '')
    return ['meet.google.com', 'zoom.us', 'teams.microsoft.com', 'teams.live.com']
      .some(candidate => host === candidate || host.endsWith(`.${candidate}`))
  } catch {
    return false
  }
}

async function submitLink() {
  const value = linkUrl.value.trim()
  if (!value) {
    inputError.value = 'Paste a direct recording or transcript link.'
    return
  }
  if (isLiveMeetingPage(value)) {
    inputError.value = 'This is a live meeting link. The app cannot join a meeting. Download the recording or transcript first, then upload the file.'
    return
  }
  submitting.value = true
  inputError.value = ''
  try {
    const job = await api<TranscriptionJob>(`/meetings/${meetingId.value}/from-link`, {
      method: 'POST',
      body: { url: linkUrl.value.trim(), language: linkLanguage.value },
    })
    startJob(job)
  } catch (err: any) {
    inputError.value = err?.data?.detail ?? 'Could not read that link.'
  } finally {
    submitting.value = false
  }
}

async function submitTranscript() {
  if (!transcriptFile.value && !transcriptText.value.trim()) {
    inputError.value = 'Choose a transcript file or paste the text.'
    return
  }
  submitting.value = true
  inputError.value = ''
  try {
    const form = new FormData()
    if (transcriptFile.value) form.append('file', transcriptFile.value)
    else form.append('text', transcriptText.value)
    const result = await api<{ imported: number, replaced: number }>(
      `/meetings/${meetingId.value}/transcripts/import`,
      { method: 'POST', body: form },
    )
    await refresh()
    transcription.value = null
    inputOpen.value = false
    resetInputForm()
    toast.success(`Imported ${plural(result.imported, 'segment')}.`)
  } catch (err: any) {
    inputError.value = err?.data?.detail ?? 'Could not import the transcript.'
  } finally {
    submitting.value = false
  }
}

function editTranscript(segment: TranscriptSegment) {
  editingTranscriptId.value = segment.id
  transcriptDraftSpeaker.value = segment.speaker_label
  transcriptDraftOriginal.value = segment.original_text
}

function cancelTranscriptEdit() {
  editingTranscriptId.value = ''
  transcriptDraftSpeaker.value = ''
  transcriptDraftOriginal.value = ''
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
        speaker_label: transcriptDraftSpeaker.value.trim() || 'Speaker',
        original_text: transcriptDraftOriginal.value.trim(),
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
    const result = await api<MinutesOfMeeting>(
      `/meetings/${meetingId.value}/synthesize-mom?language=${momLanguage.value}`,
      { method: 'POST' },
    )
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
    draftLanguage.value = momLanguage.value
    toast.success(
      `Draft generated in ${momLanguage.value === 'km' ? 'Khmer' : 'English'}. Review every section before publishing.`,
    )
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
    await api(`/meetings/${meetingId.value}/approve-mom`, {
      method: 'POST',
      body: payload(),
    })
    await refresh()
    approveOpen.value = false
    toast.success('Minutes published, archived in Documents, and follow-ups updated.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not publish the minutes.')
  } finally {
    publishing.value = false
  }
}

function formatTimestamp(value: number) {
  const minutes = Math.floor(value / 60)
  const seconds = Math.floor(value % 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

onMounted(() => {
  if (isProcessing.value) startPolling()
})

onUnmounted(() => {
  stopPolling()
  if (generateTimer) clearInterval(generateTimer)
})
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
        :title="meeting.title"
        :description="`${formatDate(meeting.scheduled_start)} · ${formatTimeRange(meeting.scheduled_start, meeting.scheduled_end)}`"
      >
        <template #meta>
          <StatusBadge :status="meetingState" />
          <span class="text-[13px] text-muted-foreground">{{ itemSummary }}</span>
        </template>
        <template #actions>
          <Button v-if="!isVerified" variant="outline" :disabled="isProcessing" @click="inputOpen = true">
            <Upload class="h-4 w-4" />
            Add content
          </Button>
          <Button v-if="!isVerified" variant="outline" :disabled="saving || !hasDraft" @click="saveDraft">
            {{ saving ? 'Saving…' : 'Save draft' }}
          </Button>
          <Button v-if="!isVerified" :disabled="publishing || !hasDraft" @click="approveOpen = true">
            {{ publishing ? 'Publishing…' : 'Publish minutes' }}
          </Button>
        </template>
      </PageHeader>

      <div class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-y py-2.5 text-[13px] text-muted-foreground">
        <span class="font-medium text-foreground">Agenda</span>
        <span v-for="item in meeting.agendas" :key="item.id">{{ item.title }}</span>
        <span v-if="!meeting.agendas.length">No agenda recorded</span>
      </div>

      <div class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">
        <div v-for="(step, index) in steps" :key="step.label" class="flex items-center gap-2">
          <span
            class="flex h-5 w-5 items-center justify-center rounded-full border text-[11px] font-medium"
            :class="
              step.state === 'done'
                ? 'border-brand bg-brand text-brand-foreground'
                : step.state === 'current'
                  ? 'border-brand text-brand'
                  : 'border-border text-muted-foreground'
            "
          >
            <Check v-if="step.state === 'done'" class="h-3 w-3" />
            <span v-else>{{ index + 1 }}</span>
          </span>
          <span class="text-[13px]" :class="step.state === 'todo' ? 'text-muted-foreground' : 'text-foreground'">
            {{ step.label }}
          </span>
          <span v-if="index < steps.length - 1" class="hidden h-px w-8 bg-border sm:block" />
        </div>
      </div>

      <div v-if="isProcessing" class="mt-4 flex items-start gap-3 rounded-md border border-warning/20 bg-warning-soft px-4 py-3">
        <span class="mt-0.5 h-3.5 w-3.5 animate-spin rounded-full border-2 border-warning border-t-transparent" />
        <div>
          <p class="text-sm font-medium text-warning">Transcribing recording</p>
          <p class="mt-0.5 text-[13px] text-warning/90">
            This can take several minutes for a long meeting. You can leave this page and come back.
          </p>
        </div>
      </div>

      <div v-else-if="transcription?.status === 'failed'" class="mt-4 rounded-md border border-negative/20 bg-negative-soft px-4 py-3 text-[13px] text-negative">
        {{ transcription.error || 'Transcription failed.' }}
        <button class="ml-1 font-medium underline" @click="inputOpen = true">Try again</button>
      </div>

      <div v-if="isVerified" class="mt-4 flex flex-col gap-3 rounded-lg border border-positive/20 bg-positive-soft px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex items-start gap-2.5">
          <Check class="mt-0.5 h-4 w-4 text-positive" />
          <div>
            <p class="text-sm font-medium text-positive">Minutes published</p>
            <p class="mt-0.5 text-[13px] text-positive">
              Archived in Documents. This record is read-only.
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
          <Button variant="outline" size="sm" as-child>
            <NuxtLink to="/tasks">Open tasks</NuxtLink>
          </Button>
        </div>
      </div>

      <div class="mt-4 grid grid-cols-1 items-start gap-4 xl:grid-cols-12">
        <Card class="flex flex-col xl:col-span-5 xl:h-[calc(100vh-13rem)]">
          <CardHeader class="flex-row items-start justify-between gap-3 pb-3">
            <div>
              <CardTitle>Transcript</CardTitle>
              <CardDescription class="mt-1">
                {{ sourceTranscripts.length ? 'Correct names and misheard words before drafting.' : 'Upload a recording, paste a link, or import a transcript.' }}
              </CardDescription>
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
                  <p v-if="segment.start_timestamp > 0" class="tabular-nums text-[13px] text-muted-foreground">
                    {{ formatTimestamp(segment.start_timestamp) }}
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
                <Input v-model="transcriptDraftSpeaker" aria-label="Speaker" placeholder="Speaker" />
                <Textarea
                  v-model="transcriptDraftOriginal"
                  data-testid="transcript-original"
                  rows="4"
                  class="font-khmer"
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
              <p v-else class="mt-1.5 font-khmer text-sm leading-relaxed">{{ segment.original_text }}</p>
            </div>
          </div>

          <div v-else class="flex flex-1 flex-col items-start justify-center border-t px-5 py-10">
            <FileAudio class="h-5 w-5 text-muted-foreground" />
            <p class="mt-3 text-sm font-medium">No transcript yet</p>
            <p class="mt-1 max-w-sm text-[13px] leading-relaxed text-muted-foreground">
              Upload a Khmer recording for local transcription, or import a transcript file.
            </p>
            <Button v-if="!isVerified" class="mt-4" size="sm" :disabled="isProcessing" @click="inputOpen = true">
              <Upload class="h-4 w-4" />
              Add meeting content
            </Button>
          </div>
        </Card>

        <Card class="flex flex-col xl:col-span-7 xl:h-[calc(100vh-13rem)]">
          <CardHeader class="pb-3">
            <CardTitle>Minutes of meeting</CardTitle>
            <CardDescription>
              {{ isVerified ? 'These minutes are published and read-only.' : 'Generate a draft or write the minutes directly. Only the published version becomes official.' }}
            </CardDescription>
            <div v-if="!isVerified" class="mt-3 flex flex-wrap items-center gap-2">
              <span class="text-[12px] text-muted-foreground">Language</span>
              <div
                class="inline-flex rounded-md border bg-muted/30 p-0.5"
                role="group"
                aria-label="Minutes language"
              >
                <button
                  type="button"
                  class="rounded px-2.5 py-1 text-[12px] font-medium transition-colors"
                  :class="momLanguage === 'en' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                  :aria-pressed="momLanguage === 'en'"
                  @click="momLanguage = 'en'"
                >
                  English
                </button>
                <button
                  type="button"
                  class="rounded px-2.5 py-1 font-khmer text-[12px] font-medium transition-colors"
                  :class="momLanguage === 'km' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                  :aria-pressed="momLanguage === 'km'"
                  @click="momLanguage = 'km'"
                >
                  ខ្មែរ
                </button>
              </div>
              <Button
                v-if="canRegenerate"
                variant="ghost"
                size="sm"
                class="ml-auto text-brand"
                :disabled="generating"
                @click="generateDraft"
              >
                <span v-if="generating" class="h-3 w-3 animate-spin rounded-full border-2 border-brand border-t-transparent" />
                {{ generating ? 'Regenerating…' : `Regenerate in ${momLanguage === 'km' ? 'Khmer' : 'English'}` }}
              </Button>
            </div>
            <p
              v-if="!isVerified && canRegenerate && draftLanguage && draftLanguage !== momLanguage"
              class="mt-2 text-[12px] text-muted-foreground"
            >
              Current draft is in {{ draftLanguage === 'km' ? 'Khmer' : 'English' }}. Regenerate to apply {{ momLanguage === 'km' ? 'Khmer' : 'English' }}.
            </p>
            <p v-if="canRegenerate && aiError" class="mt-2 text-[13px] text-negative">{{ aiError }}</p>
          </CardHeader>

          <CardContent class="flex-1 space-y-6 overflow-y-auto border-t pt-5">
            <div v-if="!hasDraft" class="rounded-md border border-dashed border-input bg-muted/30 p-4">
              <p class="text-[13px] font-medium">No minutes yet</p>
              <p class="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                {{ sourceTranscripts.length
                  ? `Generate a draft from ${plural(sourceTranscripts.length, 'transcript segment')}, then review every section.`
                  : 'Add meeting content first, or write the minutes manually below.' }}
              </p>
              <p v-if="aiError" class="mt-2 text-[13px] text-negative">{{ aiError }}</p>
              <Button variant="outline" size="sm" class="mt-3" :disabled="generating || !canGenerate" @click="generateDraft">
                <span v-if="generating" class="h-3 w-3 animate-spin rounded-full border-2 border-foreground border-t-transparent" />
                {{ generating ? 'Generating…' : 'Generate draft from transcript' }}
              </Button>
              <p v-if="generating" class="mt-2 text-[12px] text-muted-foreground" role="status">
                Gemini is drafting the minutes · {{ generatingSeconds }}s
              </p>
            </div>

            <section class="space-y-2">
              <div class="flex items-center justify-between gap-3">
                <Label for="mom-summary">Executive summary</Label>
                <span class="text-[13px] text-muted-foreground">{{ isVerified ? 'Published' : 'Editable' }}</span>
              </div>
              <Textarea
                id="mom-summary"
                v-model="mom.executiveSummary"
                rows="5"
                :readonly="isVerified"
                :class="draftLanguage === 'km' ? 'font-khmer' : ''"
              />
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
                    :class="['flex-1', draftLanguage === 'km' ? 'font-khmer' : '']"
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
                      :class="['h-8 max-w-[260px] text-[13px]', draftLanguage === 'km' ? 'font-khmer' : '']"
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
                    :class="draftLanguage === 'km' ? 'font-khmer' : ''"
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
                      :class="['flex-1', draftLanguage === 'km' ? 'font-khmer' : '']"
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
                      <Input
                        :id="`action-owner-${index}`"
                        v-model="mom.actionItems[index].assigneeName"
                        placeholder="Name"
                        :class="draftLanguage === 'km' ? 'font-khmer' : ''"
                        :readonly="isVerified"
                      />
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
              <span>{{ isVerified ? 'Published record' : draftSaved ? 'Draft saved' : 'Draft · not published' }}</span>
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
              This marks the minutes verified, creates the DOCX and CSV, archives a copy in Documents, and activates the action items and decisions.
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

      <Dialog v-model:open="inputOpen">
        <DialogContent class="max-w-xl" data-testid="meeting-content">
          <DialogHeader>
            <DialogTitle>Add meeting content</DialogTitle>
            <DialogDescription>
              Choose one source. Importing replaces the current transcript.
            </DialogDescription>
          </DialogHeader>

          <div class="flex items-center gap-1 border-b" role="tablist">
            <button
              v-for="option in [
                { value: 'recording', label: 'Recording', icon: FileAudio },
                { value: 'link', label: 'From link', icon: Link2 },
                { value: 'transcript', label: 'Transcript', icon: FileText },
              ]"
              :key="option.value"
              role="tab"
              :aria-selected="inputTab === option.value"
              class="relative inline-flex h-9 flex-1 items-center justify-center gap-1.5 px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground"
              :class="
                inputTab === option.value
                  ? 'text-foreground after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-brand after:content-[\'\']'
                  : ''
              "
              @click="inputTab = option.value"
            >
              <component :is="option.icon" class="h-3.5 w-3.5" />
              {{ option.label }}
            </button>
          </div>

            <div v-if="inputTab === 'recording'" class="mt-4 space-y-4">
              <div class="space-y-1.5">
                <Label for="recording-file">Audio or video recording</Label>
                <input
                  id="recording-file"
                  type="file"
                  accept="audio/*,video/*,.mp3,.m4a,.wav,.mp4,.webm,.ogg,.aac,.flac,.mov"
                  class="sr-only"
                  @change="onRecordingFile"
                />
                <label
                  for="recording-file"
                  class="flex min-h-[88px] cursor-pointer flex-col items-center justify-center gap-1 rounded-md border border-dashed border-input bg-muted/30 px-4 py-4 text-center transition-colors hover:bg-muted/60"
                >
                  <Upload class="h-4 w-4 text-muted-foreground" />
                  <span class="text-[13px] font-medium">
                    {{ recordingFile?.name ?? 'Choose a recording' }}
                  </span>
                  <span class="text-[12px] text-muted-foreground">MP3, M4A, WAV, MP4 or WebM · up to 500 MB</span>
                </label>
                <p class="text-[12px] text-muted-foreground">
                  Transcription may take several minutes. English runs locally; Khmer uses Google when a key is configured.
                </p>
              </div>
              <div class="space-y-1.5">
                <Label for="recording-language">Spoken language</Label>
                <Select
                  id="recording-language"
                  v-model="recordingLanguage"
                  :options="languageOptions"
                  aria-label="Spoken language"
                />
              </div>
            </div>

            <div v-if="inputTab === 'link'" class="mt-4 space-y-4">
              <div class="space-y-1.5">
                <Label for="recording-link">Direct file link</Label>
                <Input id="recording-link" v-model="linkUrl" placeholder="https://example.com/meeting.mp4" />
                <p class="text-[12px] text-muted-foreground">
                  A direct link to a recording or transcript file, for example a public MP4, M4A, MP3, WAV, VTT, SRT, TXT or DOCX.
                </p>
                <div class="rounded-md border border-warning/20 bg-warning-soft px-3 py-2 text-[12px] leading-relaxed text-warning">
                  <p class="font-medium">Not a meeting link.</p>
                  <p class="mt-0.5">
                    Links such as meet.google.com, zoom.us/rec, Teams share pages or Google Drive share pages cannot be read directly. Open the platform, download the recording or transcript, then upload the file.
                  </p>
                </div>
              </div>
              <div class="space-y-1.5">
                <Label for="link-language">Spoken language</Label>
                <Select
                  id="link-language"
                  v-model="linkLanguage"
                  :options="languageOptions"
                  aria-label="Spoken language"
                />
              </div>
            </div>

            <div v-if="inputTab === 'transcript'" class="mt-4 space-y-4">
              <div class="space-y-1.5">
                <Label for="transcript-file">Transcript file</Label>
                <input
                  id="transcript-file"
                  type="file"
                  accept=".txt,.vtt,.srt,.docx"
                  class="sr-only"
                  @change="onTranscriptFile"
                />
                <label
                  for="transcript-file"
                  class="flex min-h-[88px] cursor-pointer flex-col items-center justify-center gap-1 rounded-md border border-dashed border-input bg-muted/30 px-4 py-4 text-center transition-colors hover:bg-muted/60"
                >
                  <FileText class="h-4 w-4 text-muted-foreground" />
                  <span class="text-[13px] font-medium">
                    {{ transcriptFile?.name ?? 'Choose a transcript file' }}
                  </span>
                  <span class="text-[12px] text-muted-foreground">TXT, VTT, SRT or DOCX</span>
                </label>
              </div>
              <div class="space-y-1.5">
                <Label for="transcript-text">Or paste the transcript</Label>
                <Textarea
                  id="transcript-text"
                  v-model="transcriptText"
                  rows="6"
                  class="font-khmer"
                  placeholder="Speaker: text…"
                />
              </div>
            </div>

          <p v-if="inputError" class="text-[13px] text-negative">{{ inputError }}</p>

          <DialogFooter>
            <Button variant="outline" :disabled="submitting" @click="inputOpen = false">Cancel</Button>
            <Button v-if="inputTab === 'recording'" :disabled="submitting" @click="submitRecording">
              {{ submitting ? 'Uploading…' : 'Transcribe recording' }}
            </Button>
            <Button v-else-if="inputTab === 'link'" :disabled="submitting" @click="submitLink">
              {{ submitting ? 'Reading…' : 'Read link' }}
            </Button>
            <Button v-else :disabled="submitting" @click="submitTranscript">
              {{ submitting ? 'Importing…' : 'Import transcript' }}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </template>
  </div>
</template>
