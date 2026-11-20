<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Copy, FileCheck2, Play } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '~/components/ui/card'
import AudioWave from '~/components/motion/AudioWave.vue'
import LiveDot from '~/components/motion/LiveDot.vue'
import ErrorState from '~/components/workspace/ErrorState.vue'
import LoadingState from '~/components/workspace/LoadingState.vue'
import PageHeader from '~/components/workspace/PageHeader.vue'
import StatusBadge from '~/components/workspace/StatusBadge.vue'
import { useApi } from '~/composables/useApi'
import { formatDate, formatTimeRange, plural } from '~/lib/format'
import type { Meeting, TranscriptSegment } from '~/types/api'

useHead({ title: 'Live meeting · ACLEDA University' })

const route = useRoute()
const api = useApi()
const config = useRuntimeConfig()
const meetingId = computed(() => String(route.params.id))
const { data, pending, error, refresh } = await useAsyncData(`live-${meetingId.value}`, async () => {
  const [meeting, transcripts] = await Promise.all([
    api<Meeting>(`/meetings/${meetingId.value}`),
    api<TranscriptSegment[]>(`/meetings/${meetingId.value}/transcripts`),
  ])
  return { meeting, transcripts }
})

const meeting = computed(() => data.value?.meeting)
const segments = ref<TranscriptSegment[]>([])
const liveNotice = ref('')
const acting = ref(false)
const captureState = ref<'idle' | 'connected' | 'receiving' | 'disconnected'>('idle')
const lastChunk = ref(0)
const audioPeak = ref(0)
const micBlocked = ref(false)
const tabBlocked = ref(false)
let socket: WebSocket | null = null

const captureLabel = computed(() => {
  if (captureState.value === 'receiving') return `Receiving audio · chunk ${lastChunk.value}`
  if (captureState.value === 'connected') return 'Capture connected'
  if (captureState.value === 'disconnected') return 'Capture disconnected'
  return 'Waiting for capture'
})

  watch(
  data,
  value => {
    if (value) segments.value = value.transcripts.filter(segment => segment.original_text.trim())
  },
  { immediate: true },
)

function formatTimestamp(value: number) {
  const minutes = Math.floor(value / 60)
  const seconds = Math.floor(value % 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function closeSocket() {
  socket?.close()
  socket = null
}

function connectSocket() {
  if (socket && socket.readyState === WebSocket.OPEN) return
  closeSocket()
  try {
    socket = new WebSocket(`${config.public.wsBase}/ws/live-transcript/${meetingId.value}`)
    socket.onmessage = event => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'capture_status') {
          captureState.value = payload.status
          lastChunk.value = payload.chunk ?? 0
          if (payload.source === 'mic' || payload.source === 'mixed' || !payload.source) {
            audioPeak.value = payload.peak ?? 0
          }
          const micBlockedNow = payload.mic === '0' || payload.mic === 0 || payload.mic === false
          const tabBlockedNow = payload.tab === '0' || payload.tab === 0 || payload.tab === false
          micBlocked.value = micBlockedNow
          tabBlocked.value = tabBlockedNow
          if (micBlockedNow) {
            liveNotice.value =
              'The extension could not access the microphone. Allow it for the extension in Chrome and macOS, then start capture again.'
          } else if (payload.status === 'disconnected') {
            liveNotice.value = 'Audio capture disconnected. Reopen the extension popup and start capture again.'
          } else if (payload.status === 'connected') {
            liveNotice.value = tabBlockedNow
              ? 'Capture connected without Meet tab audio — recording the microphone only. Open the extension from the Meet tab to include other participants.'
              : 'Capture connected — waiting for the first 10-second audio chunk.'
          } else if (payload.status === 'receiving') {
            if (payload.source === 'tab') {
              // Remote participants are speaking; keep any microphone warning visible.
            } else if (audioPeak.value < 0.002) {
              liveNotice.value = `Audio is arriving but the level is very low (${(audioPeak.value * 100).toFixed(2)}%). Check that the Meet tab is unmuted and the microphone is allowed.`
            } else {
              liveNotice.value = ''
            }
          }
          return
        }
        if (payload.type === 'transcription_error') {
          liveNotice.value = payload.message ?? 'Live transcription is unavailable.'
          return
        }
        if (payload.type !== 'transcript_segment') {
          if (payload.type === 'transcription_status' && payload.status === 'no_speech') {
            if (payload.source === 'tab') return
            if (micBlocked.value) {
              liveNotice.value =
                'The extension could not access the microphone. Allow it for the extension in Chrome and macOS, then start capture again.'
            } else {
              liveNotice.value =
                audioPeak.value < 0.002
                  ? `Audio is arriving but the level is very low (${(audioPeak.value * 100).toFixed(2)}%). Check that the Meet tab is unmuted and the microphone is allowed.`
                  : 'Listening — no speech detected in the last audio chunk.'
            }
          }
          return
        }
        if (!String(payload.original_text ?? '').trim()) return
        liveNotice.value = ''
        segments.value.push({
          id: `live-${Date.now()}-${segments.value.length}`,
          speaker_label: payload.speaker_label ?? 'Speaker',
          start_timestamp: payload.start_timestamp ?? 0,
          end_timestamp: payload.end_timestamp ?? 0,
          original_text: payload.original_text ?? '',
          translated_text: payload.translated_text ?? null,
          confidence_score: payload.confidence_score ?? 0,
          language_detected: payload.language_detected ?? 'unknown',
          created_at: new Date().toISOString(),
        })
      } catch {
        liveNotice.value = 'Received an unreadable transcript message.'
      }
    }
    socket.onerror = () => {
      liveNotice.value = 'The live transcript channel is unavailable.'
    }
  } catch {
    liveNotice.value = 'The live transcript channel could not be opened.'
  }
}

watch(
  () => meeting.value?.status,
  status => {
    if (status === 'In Progress') connectSocket()
    else closeSocket()
  },
  { immediate: true },
)

onUnmounted(closeSocket)

async function startSession() {
  acting.value = true
  try {
    await api(`/meetings/${meetingId.value}/start`, { method: 'POST' })
    await refresh()
    toast.success('Session started.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not start the session.')
  } finally {
    acting.value = false
  }
}

async function endSession() {
  acting.value = true
  try {
    await api(`/meetings/${meetingId.value}/end`, { method: 'POST' })
    await navigateTo(`/meetings/${meetingId.value}/review`)
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not end the session.')
  } finally {
    acting.value = false
  }
}

async function copyMeetingId() {
  try {
    await navigator.clipboard.writeText(meetingId.value)
    toast.success('Meeting ID copied. Paste it into the extension popup.')
  } catch {
    toast.error('Could not copy the meeting ID.')
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
      <PageHeader :title="meeting.title">
        <template #meta>
          <Badge v-if="meeting.status === 'In Progress'" variant="live">
            <LiveDot />
            Live
          </Badge>
          <StatusBadge v-else :status="meeting.status" />
          <span class="text-[13px] text-muted-foreground">
            {{ formatDate(meeting.scheduled_start) }} · {{ formatTimeRange(meeting.scheduled_start, meeting.scheduled_end) }}
          </span>
          <span v-if="meeting.status === 'In Progress'" class="hidden items-center gap-1.5 text-[13px] text-muted-foreground sm:flex">
            <AudioWave v-if="captureState === 'receiving'" />
            <LiveDot v-else-if="captureState === 'connected'" />
            {{ captureLabel }}
          </span>
        </template>
        <template #actions>
          <Button variant="outline" size="sm" @click="copyMeetingId">
            <Copy class="h-4 w-4" />
            Copy meeting ID
          </Button>
          <Button v-if="meeting.status === 'Scheduled'" :disabled="acting" @click="startSession">
            <Play class="h-4 w-4" />
            {{ acting ? 'Starting…' : 'Start session' }}
          </Button>
          <Button v-else-if="meeting.status === 'In Progress'" :disabled="acting" @click="endSession">
            <FileCheck2 class="h-4 w-4" />
            {{ acting ? 'Ending…' : 'End & generate MoM' }}
          </Button>
          <Button v-else as-child>
            <NuxtLink :to="`/meetings/${meeting.id}/review`">
              <FileCheck2 class="h-4 w-4" />
              Review minutes
            </NuxtLink>
          </Button>
        </template>
      </PageHeader>

      <div class="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted-foreground">
        <span>{{ plural(meeting.participant_count, 'participant') }}</span>
        <span aria-hidden="true">·</span>
        <span>{{ plural(meeting.agendas.length, 'agenda item') }}</span>
        <span v-if="meeting.summary?.is_verified" aria-hidden="true">·</span>
        <span v-if="meeting.summary?.is_verified">Minutes verified</span>
      </div>

      <div v-if="meeting.agendas.length" class="mt-4 flex flex-wrap gap-x-5 gap-y-1 border-y py-2.5 text-[13px] text-muted-foreground">
        <span class="font-medium text-foreground">Agenda</span>
        <span v-for="item in meeting.agendas" :key="item.id">{{ item.title }}</span>
      </div>

      <div class="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted-foreground">
        <span>To record a Google Meet, open the Meet tab, click the</span>
        <span class="font-medium text-foreground">AUB Meeting Ingress</span>
        <span>extension icon there, then paste this meeting ID and allow microphone access.</span>
      </div>

      <div v-if="liveNotice" class="mt-4 rounded-md border border-warning/20 bg-warning-soft px-4 py-3 text-[13px] text-warning">
        {{ liveNotice }}
      </div>

      <div class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Card class="flex flex-col xl:col-span-7">
          <CardHeader class="flex-row items-start justify-between gap-3 pb-3">
            <div>
              <CardTitle>Original transcript</CardTitle>
              <CardDescription class="mt-1">Khmer and English as spoken.</CardDescription>
            </div>
            <Badge variant="outline">ASR</Badge>
          </CardHeader>
          <div v-if="segments.length" class="max-h-[520px] flex-1 overflow-y-auto border-t p-5 xl:max-h-none">
            <div
              v-for="segment in segments"
              :key="segment.id"
              class="rounded-md px-2 py-3.5 transition-colors first:pt-0 last:pb-0 hover:bg-muted/40"
              data-testid="original-segment"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-2">
                  <p class="text-[13px] font-medium">{{ segment.speaker_label }}</p>
                  <span
                    v-if="segment.language_detected && segment.language_detected !== 'unknown'"
                    class="rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    {{ segment.language_detected }}
                  </span>
                </div>
                <p class="tabular-nums text-[13px] text-muted-foreground">
                  {{ formatTimestamp(segment.start_timestamp) }}–{{ formatTimestamp(segment.end_timestamp) }}
                </p>
              </div>
              <p class="mt-1.5 font-khmer text-sm leading-relaxed">{{ segment.original_text }}</p>
            </div>
          </div>
          <div v-else class="flex flex-1 items-center border-t px-5 py-8">
            <p class="text-[13px] text-muted-foreground">
              No transcript yet. Start the session and connect the audio ingress extension.
            </p>
          </div>
          <div class="mt-auto flex items-center justify-between border-t px-5 py-3 text-[13px] text-muted-foreground">
            <span class="flex items-center gap-2">
              <AudioWave v-if="meeting.status === 'In Progress'" class="h-3" />
              {{ meeting.status === 'In Progress' ? 'Listening for new speech…' : 'Session not capturing audio' }}
            </span>
            <span class="hidden sm:block">Audio stays on campus</span>
          </div>
        </Card>

        <Card class="flex flex-col xl:col-span-5">
          <CardHeader class="flex-row items-start justify-between gap-3 pb-3">
            <div>
              <CardTitle>English translation</CardTitle>
              <CardDescription class="mt-1">Translated as the meeting runs.</CardDescription>
            </div>
            <Badge variant="outline">NMT</Badge>
          </CardHeader>
          <div v-if="segments.length" class="max-h-[520px] flex-1 overflow-y-auto border-t p-5 xl:max-h-none">
            <div
              v-for="segment in segments"
              :key="segment.id"
              class="rounded-md px-2 py-3.5 transition-colors first:pt-0 last:pb-0 hover:bg-muted/40"
              data-testid="translation-segment"
            >
              <div class="flex items-center justify-between gap-3">
                <p class="text-[13px] font-medium">{{ segment.speaker_label }}</p>
                <p class="tabular-nums text-[13px] text-muted-foreground">
                  {{ formatTimestamp(segment.start_timestamp) }}–{{ formatTimestamp(segment.end_timestamp) }}
                </p>
              </div>
              <p class="mt-1.5 text-sm leading-relaxed">{{ segment.translated_text || 'Translation unavailable' }}</p>
            </div>
          </div>
          <div v-else class="flex flex-1 items-center border-t px-5 py-8">
            <p class="text-[13px] text-muted-foreground">No translation yet.</p>
          </div>
        </Card>
      </div>
    </template>
  </div>
</template>
