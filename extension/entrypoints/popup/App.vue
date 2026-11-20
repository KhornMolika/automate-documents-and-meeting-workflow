<template>
  <div class="popup">
    <header class="popup-header">
      <div class="brand">
        <img src="/aub-logo.png" alt="ACLEDA University" class="brand-logo" />
        <p class="brand-sub">Meeting ingress</p>
      </div>
      <span class="status" :class="isStreaming ? 'status-live' : 'status-idle'">
        <span class="status-dot" />
        {{ isStreaming ? 'Live' : 'Idle' }}
      </span>
    </header>

    <div class="field">
      <label for="meeting-id">Meeting ID</label>
      <input
        id="meeting-id"
        v-model="meetingId"
        class="input"
        placeholder="Paste the ID from the live console"
        :disabled="isStreaming"
        autocomplete="off"
      />
    </div>

    <div class="field">
      <label for="language">Spoken language</label>
      <select id="language" v-model="language" class="input" :disabled="isStreaming">
        <option value="auto">Auto-detect</option>
        <option value="km">Khmer</option>
        <option value="en">English</option>
      </select>
    </div>

    <div class="telemetry">
      <div class="telemetry-row">
        <span>Audio format</span>
        <strong>16 kHz PCM</strong>
      </div>
      <div class="telemetry-row">
        <span>Gateway</span>
        <strong>127.0.0.1:8000</strong>
      </div>
      <div class="telemetry-row">
        <span>Meeting</span>
        <strong :title="meetingTitle || ''">{{ meetingLabel }}</strong>
      </div>
      <div class="telemetry-row">
        <span>Source</span>
        <strong>{{ sourceLabel }}</strong>
      </div>
      <div class="telemetry-row">
        <span>Chunks sent</span>
        <strong>{{ isStreaming ? chunks : '—' }}</strong>
      </div>
      <div class="telemetry-row">
        <span>Audio level</span>
        <strong>{{ levelLabel }}</strong>
      </div>
      <div class="telemetry-row">
        <span>Microphone</span>
        <strong>{{ microphoneLabel }}</strong>
      </div>
    </div>

    <p class="note">
      Keep the Google Meet tab open and unmuted. Your microphone and the meeting tab are captured together,
      so your own voice is transcribed too.
    </p>

    <p v-if="meetingError" class="warning">{{ meetingError }}</p>
    <p v-if="tabWarning" class="warning">{{ tabWarning }}</p>
    <p v-if="micWarning" class="warning">{{ micWarning }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <button
      v-if="!isStreaming"
      class="button button-primary"
      :disabled="!canStart"
      @click="startIngress"
    >
      {{ starting ? 'Starting…' : 'Start capture' }}
    </button>
    <button v-else class="button button-stop" @click="stopIngress">
      Stop capture
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

const API_BASE = 'http://127.0.0.1:8000/api/v1'

const isStreaming = ref(false)
const meetingId = ref('')
const language = ref('auto')
const meetingTitle = ref('')
const meetingStatus = ref('')
const meetingError = ref('')
const meetingFound = ref<boolean | null>(null)
const validating = ref(false)
const error = ref('')
const micWarning = ref('')
const tabWarning = ref('')
const starting = ref(false)
const chunks = ref(0)
const bytes = ref(0)
const peak = ref(0)
const micActive = ref(false)
const tabActive = ref(false)
const micError = ref('')
const lastChunkAt = ref(0)

let statusTimer: ReturnType<typeof setInterval> | null = null

const sourceLabel = computed(() => {
  if (!isStreaming.value) return '—'
  if (micActive.value && tabActive.value) return 'Tab + microphone'
  if (micActive.value) return 'Microphone only'
  if (tabActive.value) return 'Tab audio only'
  return 'Starting…'
})

const microphoneLabel = computed(() => {
  if (micActive.value) return 'Capturing'
  if (micError.value) return 'Blocked'
  return '—'
})

const levelLabel = computed(() => {
  if (!isStreaming.value) return '—'
  if (chunks.value === 0) return 'Waiting for audio'
  return peak.value < 0.002 ? 'Silent' : `${(peak.value * 100).toFixed(1)}%`
})

const meetingLabel = computed(() => {
  if (validating.value) return 'Checking…'
  if (meetingTitle.value) return `${meetingTitle.value} · ${meetingStatus.value}`
  if (meetingError.value) return 'Not verified'
  return '—'
})

const canStart = computed(() => meetingStatus.value === 'In Progress' && !starting.value)

async function lookupMeeting(rawId: string): Promise<boolean> {
  meetingTitle.value = ''
  meetingStatus.value = ''
  meetingFound.value = null
  meetingError.value = ''
  if (!rawId) return false
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(rawId)) {
    meetingError.value = 'Meeting IDs are 36-character UUIDs copied from the live console.'
    return false
  }

  validating.value = true
  try {
    const response = await fetch(`${API_BASE}/meetings/${rawId}/capture-info`)
    if (response.status === 404) {
      meetingFound.value = false
      meetingError.value =
        'No meeting exists with this ID. Copy the ID from the live console you are watching.'
      return false
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()
    meetingFound.value = true
    meetingTitle.value = data.title ?? ''
    meetingStatus.value = data.status ?? ''
    if (data.status !== 'In Progress') {
      meetingError.value = `"${data.title}" is ${data.status}. Start the session in the web app, then paste the ID again.`
      return false
    }
    return true
  } catch (err: any) {
    meetingFound.value = null
    meetingError.value = `Could not verify the meeting ID (${err?.message ?? err}).`
    return false
  } finally {
    validating.value = false
  }
}

let lookupTimer: ReturnType<typeof setTimeout> | null = null
watch(meetingId, (value) => {
  if (lookupTimer) clearTimeout(lookupTimer)
  lookupTimer = setTimeout(() => {
    void lookupMeeting(String(value ?? '').trim())
  }, 350)
})

function applyStatus(status: any) {
  if (!status) return
  isStreaming.value = Boolean(status.isCapturing)
  if (status.isCapturing && status.meetingId) meetingId.value = status.meetingId
  chunks.value = status.chunks ?? 0
  bytes.value = status.bytes ?? 0
  peak.value = status.peak ?? 0
  micActive.value = Boolean(status.micActive)
  tabActive.value = Boolean(status.tabActive)
  micError.value = status.micError ?? ''
  if (status.tabError) tabWarning.value = status.tabError
  lastChunkAt.value = status.lastChunkAt ?? 0
  if (status.lastError) error.value = status.lastError
}

function refreshStatus() {
  if (typeof chrome === 'undefined' || !chrome.runtime) return
  chrome.runtime.sendMessage({ action: 'GET_STATUS' }, (status) => applyStatus(status))
}

function onRuntimeMessage(message: any) {
  if (message?.action === 'CAPTURE_ERROR') {
    isStreaming.value = false
    error.value = message.error ?? 'Capture stopped unexpectedly.'
    return
  }
  if (message?.action === 'CAPTURE_STATUS' && message.status === 'mic_denied') {
    micWarning.value =
      message.message ??
      'Microphone access was blocked. Only the meeting tab will be transcribed, so your own voice will be missing.'
    return
  }
  if (message?.action === 'CAPTURE_STATUS' && message.status === 'tab_denied') {
    tabWarning.value =
      message.message ??
      'Meeting tab audio is unavailable. Open the Meet tab, click the AUB icon there, then start again.'
    return
  }
  refreshStatus()
}

onMounted(() => {
  if (typeof chrome === 'undefined' || !chrome.runtime) {
    error.value = 'Extension APIs are unavailable.'
    return
  }
  chrome.runtime.onMessage.addListener(onRuntimeMessage)
  chrome.storage.local.get(['preferredLanguage'], (result) => {
    if (result?.preferredLanguage && ['auto', 'km', 'en'].includes(result.preferredLanguage)) {
      language.value = result.preferredLanguage
    }
  })
  refreshStatus()
  statusTimer = setInterval(refreshStatus, 1000)
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
  if (typeof chrome !== 'undefined' && chrome.runtime) {
    chrome.runtime.onMessage.removeListener(onRuntimeMessage)
  }
})

async function primeMicrophone() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    stream.getTracks().forEach((track) => track.stop())
    // Give Chrome a moment to release the device before the offscreen document reopens it.
    await new Promise((resolve) => setTimeout(resolve, 200))
    return true
  } catch (err: any) {
    micWarning.value =
      `Microphone permission was not granted (${err?.message ?? err}). ` +
      'Allow the microphone for this extension in Chrome and macOS, then retry. ' +
      'Without it, only the meeting tab audio is transcribed.'
    return false
  }
}

watch(language, (value) => {
  if (typeof chrome !== 'undefined' && chrome.runtime) {
    chrome.storage.local.set({ preferredLanguage: value })
  }
})

async function startIngress() {
  error.value = ''
  micWarning.value = ''
  tabWarning.value = ''
  if (!meetingId.value.trim()) {
    error.value = 'Paste the meeting ID from the live console first.'
    return
  }
  if (typeof chrome === 'undefined' || !chrome.runtime) {
    error.value = 'Extension APIs are unavailable.'
    return
  }
  starting.value = true
  try {
    const valid = await lookupMeeting(meetingId.value.trim())
    if (!valid) {
      starting.value = false
      return
    }
    await primeMicrophone()
    chrome.runtime.sendMessage(
      { action: 'START_CAPTURE', meetingId: meetingId.value.trim(), language: language.value },
      (res) => {
        starting.value = false
        if (res?.status === 'ERROR') {
          isStreaming.value = false
          error.value = res.error ?? 'Could not start capture.'
        } else if (res?.status === 'CONNECTED') {
          isStreaming.value = true
          if (res.tabError) tabWarning.value = res.tabError
          refreshStatus()
        }
      },
    )
  } catch (err: any) {
    starting.value = false
    error.value = String(err?.message ?? err)
  }
}

function stopIngress() {
  if (typeof chrome === 'undefined' || !chrome.runtime) return
  chrome.runtime.sendMessage({ action: 'STOP_CAPTURE' }, () => {
    isStreaming.value = false
  })
}
</script>
