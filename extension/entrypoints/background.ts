export default defineBackground(() => {
  const OFFSCREEN_PATH = 'offscreen.html'
  let micHelpOpened = false

  async function hasOffscreenDocument() {
    const runtime = chrome.runtime as typeof chrome.runtime & {
      getContexts?: (filter: { contextTypes: string[] }) => Promise<unknown[]>
    }
    if (runtime.getContexts) {
      const contexts = await runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] })
      return contexts.length > 0
    }
    return false
  }

  async function ensureOffscreenDocument() {
    if (await hasOffscreenDocument()) return
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_PATH,
      reasons: [chrome.offscreen.Reason.USER_MEDIA, chrome.offscreen.Reason.AUDIO_PLAYBACK],
      justification:
        'Capture Google Meet tab audio and the microphone, then stream 16 kHz PCM to the campus gateway.',
    })
  }

  async function getMeetTab() {
    const [active] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (active?.id && active.url?.startsWith('https://meet.google.com/')) return active
    const [meetTab] = await chrome.tabs.query({ url: 'https://meet.google.com/*' })
    if (meetTab?.id) return meetTab
    throw new Error('Open a Google Meet tab first.')
  }

  function getStreamId(tabId: number) {
    return new Promise<string>((resolve, reject) => {
      chrome.tabCapture.getMediaStreamId({ targetTabId: tabId }, (streamId) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message ?? 'Could not capture the Meet tab.'))
        } else {
          resolve(streamId)
        }
      })
    })
  }

  async function setCapturing(capturing: boolean) {
    await chrome.action.setBadgeBackgroundColor({ color: capturing ? '#dc2626' : '#00000000' })
    await chrome.action.setBadgeText({ text: capturing ? 'REC' : '' })
  }

  async function resetTelemetry() {
    await chrome.storage.local.set({
      isCapturing: true,
      chunks: 0,
      bytes: 0,
      peak: 0,
      micActive: false,
      tabActive: false,
      micError: '',
      tabError: '',
      lastError: '',
      lastChunkAt: 0,
      startedAt: Date.now(),
    })
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.target === 'offscreen') return

    if (message.action === 'START_CAPTURE') {
      ;(async () => {
        try {
          const meetingId = String(message.meetingId ?? '').trim()
          if (!meetingId) throw new Error('Paste the meeting ID from the live console.')
          micHelpOpened = false
          const language = ['auto', 'km', 'en'].includes(message.language)
            ? message.language
            : 'auto'
          let streamId = ''
          let tabError = ''
          try {
            const tab = await getMeetTab()
            streamId = await getStreamId(tab.id)
          } catch (error) {
            tabError = String(error)
            if (/activeTab|invoked/i.test(tabError)) {
              tabError =
                'Meeting tab audio needs the extension to be opened on the Google Meet tab. ' +
                'Click the AUB icon while the Meet tab is active, then start again.'
            }
          }
          await ensureOffscreenDocument()
          await resetTelemetry()
          await chrome.storage.local.set({ meetingId, tabError, language })
          const result = await chrome.runtime.sendMessage({
            target: 'offscreen',
            type: 'START_CAPTURE',
            streamId,
            tabError,
            meetingId,
            wsUrl:
              message.wsUrl ||
              `ws://127.0.0.1:8000/ws/audio/${meetingId}?language=${encodeURIComponent(language)}&chunk_seconds=10`,
          })
          if (result?.status === 'ERROR') throw new Error(result.error ?? 'Offscreen capture failed.')
          await setCapturing(true)
          sendResponse({ status: 'CONNECTED', meetingId, micOnly: !streamId, tabError })
        } catch (error) {
          await chrome.storage.local.set({ isCapturing: false, lastError: String(error) })
          await setCapturing(false)
          sendResponse({ status: 'ERROR', error: String(error) })
        }
      })()
      return true
    }

    if (message.action === 'STOP_CAPTURE') {
      ;(async () => {
        await chrome.runtime
          .sendMessage({ target: 'offscreen', type: 'STOP_CAPTURE' })
          .catch(() => undefined)
        await chrome.storage.local.set({ isCapturing: false })
        await setCapturing(false)
        sendResponse({ status: 'STOPPED' })
      })()
      return true
    }

    if (message.action === 'GET_STATUS') {
      chrome.storage.local
        .get([
          'isCapturing',
          'meetingId',
          'chunks',
          'bytes',
          'peak',
          'micActive',
          'tabActive',
          'micError',
          'tabError',
          'lastError',
          'lastChunkAt',
        ])
        .then((result) => {
          sendResponse({
            isCapturing: Boolean(result.isCapturing),
            meetingId: result.meetingId ?? '',
            chunks: result.chunks ?? 0,
            bytes: result.bytes ?? 0,
            peak: result.peak ?? 0,
            micActive: Boolean(result.micActive),
            tabActive: Boolean(result.tabActive),
            micError: result.micError ?? '',
            tabError: result.tabError ?? '',
            lastError: result.lastError ?? '',
            lastChunkAt: result.lastChunkAt ?? 0,
          })
        })
      return true
    }

    if (message.action === 'CAPTURE_STATUS') {
      if (message.status === 'mic_denied') {
        chrome.storage.local.set({ micError: message.message ?? 'Microphone unavailable.' })
        if (!micHelpOpened) {
          micHelpOpened = true
          chrome.tabs
            .create({ url: chrome.runtime.getURL('mic.html') })
            .catch(() => undefined)
        }
      } else if (message.status === 'connected') {
        chrome.storage.local.set({
          micActive: Boolean(message.micActive),
          tabActive: Boolean(message.tabActive),
          sampleRate: message.sampleRate ?? 0,
        })
      } else if (message.status === 'tab_denied') {
        chrome.storage.local.set({ tabError: message.message ?? 'Meeting tab audio unavailable.' })
      }
    }

    if (message.action === 'CAPTURE_TELEMETRY') {
      chrome.storage.local.set({
        chunks: message.chunks ?? 0,
        bytes: message.bytes ?? 0,
        peak: message.peak ?? 0,
        micActive: Boolean(message.micActive),
        tabActive: Boolean(message.tabActive),
        lastChunkAt: Date.now(),
      })
    }

    if (message.action === 'CAPTURE_ERROR') {
      chrome.storage.local.set({ isCapturing: false, lastError: message.error ?? 'Capture failed.' })
      setCapturing(false)
    }
  })
})
