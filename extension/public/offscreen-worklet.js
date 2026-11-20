let connections = []
let keepAlive = []
let tabStream = null
let micStream = null
let audioContext = null
let active = false
let chunksSent = 0
let bytesSent = 0
let lastProcessedAt = 0
let watchdog = null
let micActive = false

const TARGET_RATE = 16000
const CHUNK_SECONDS = 10

function report(action, payload = {}) {
  chrome.runtime.sendMessage({ action, ...payload }).catch(() => undefined)
}

function socketUrlWithSources(wsUrl, sourceName, mic, tab, language) {
  try {
    const url = new URL(wsUrl)
    url.searchParams.set('source', sourceName)
    url.searchParams.set('mic', mic ? '1' : '0')
    url.searchParams.set('tab', tab ? '1' : '0')
    if (language) url.searchParams.set('language', language)
    return url.toString()
  } catch {
    return wsUrl
  }
}

function stopCapture() {
  active = false
  if (watchdog) {
    clearTimeout(watchdog)
    watchdog = null
  }
  for (const connection of connections) {
    try {
      connection.worklet.port.onmessage = null
      connection.worklet.disconnect()
      connection.sourceNode.disconnect()
      connection.gain.disconnect()
      connection.socket.onclose = null
      connection.socket.close()
    } catch {
      // already closed
    }
  }
  connections = []
  keepAlive = []
  for (const stream of [tabStream, micStream]) {
    if (stream) stream.getTracks().forEach((track) => track.stop())
  }
  tabStream = null
  micStream = null
  if (audioContext) {
    audioContext.close().catch(() => undefined)
    audioContext = null
  }
  chunksSent = 0
  bytesSent = 0
  lastProcessedAt = 0
  micActive = false
}

async function startCapture(message) {
  stopCapture()
  active = true

  let tabError = message.tabError || ''
  if (message.streamId) {
    try {
      tabStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          mandatory: {
            chromeMediaSource: 'tab',
            chromeMediaSourceId: message.streamId,
            googDisableLocalEcho: false,
          },
        },
        video: false,
      })
    } catch (error) {
      tabError = String(error)
    }
  }

  micActive = false
  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    })
    micActive = true
  } catch (error) {
    report('CAPTURE_STATUS', {
      status: 'mic_denied',
      message: `Microphone unavailable: ${String(error)}`,
    })
  }

  if (!tabStream && !micStream) {
    throw new Error(
      'Neither the Meet tab nor the microphone could be captured. ' +
        'Open the Google Meet tab, click the AUB extension icon there, and start again.',
    )
  }
  if (!tabStream) {
    report('CAPTURE_STATUS', {
      status: 'tab_denied',
      message:
        tabError ||
        'Meeting tab audio is unavailable. Click the AUB extension icon while the Google Meet tab is active.',
    })
  }

  audioContext = new AudioContext({ latencyHint: 'interactive' })
  await audioContext.audioWorklet.addModule(chrome.runtime.getURL('pcm-worklet.js'))
  await audioContext.resume().catch(() => undefined)
  if (audioContext.state !== 'running') {
    throw new Error(`Audio processing could not start (AudioContext is ${audioContext.state}).`)
  }

  const inputs = []
  if (tabStream) {
    const tabSource = audioContext.createMediaStreamSource(tabStream)
    // tabCapture redirects the tab's audio; route it back so the meeting stays audible.
    tabSource.connect(audioContext.destination)
    const tabDestination = audioContext.createMediaStreamDestination()
    tabSource.connect(tabDestination)
    keepAlive.push(tabSource, tabDestination)
    inputs.push({ source: 'tab', stream: tabDestination.stream })
  }
  if (micStream) {
    const micSource = audioContext.createMediaStreamSource(micStream)
    const micGain = audioContext.createGain()
    micGain.gain.value = 1
    const micDestination = audioContext.createMediaStreamDestination()
    micSource.connect(micGain)
    micGain.connect(micDestination)
    keepAlive.push(micSource, micGain, micDestination)
    inputs.push({ source: 'mic', stream: micDestination.stream })
  }

  for (const input of inputs) {
    keepAlive.push(input.stream)
    const sourceNode = audioContext.createMediaStreamSource(input.stream)
    const worklet = new AudioWorkletNode(audioContext, 'pcm-chunk-processor', {
      processorOptions: { targetRate: TARGET_RATE, chunkSeconds: CHUNK_SECONDS },
    })
    const gain = audioContext.createGain()
    gain.gain.value = 0
    sourceNode.connect(worklet)
    worklet.connect(gain)
    gain.connect(audioContext.destination)

    const socket = new WebSocket(
      socketUrlWithSources(
        message.wsUrl,
        input.source,
        micActive,
        Boolean(tabStream),
        input.source === 'tab' ? 'auto' : '',
      ),
    )
    socket.binaryType = 'arraybuffer'

    worklet.port.onmessage = (event) => {
      if (!active) return
      const { pcm, peak } = event.data ?? {}
      if (!pcm || socket.readyState !== WebSocket.OPEN) return
      socket.send(pcm)
      chunksSent += 1
      bytesSent += pcm.byteLength
      lastProcessedAt = Date.now()
      report('CAPTURE_TELEMETRY', {
        chunks: chunksSent,
        bytes: bytesSent,
        peak: peak ?? 0,
        micActive,
        tabActive: Boolean(tabStream),
        contextState: audioContext?.state ?? 'unknown',
      })
    }

    socket.onopen = () => {
      report('CAPTURE_STATUS', {
        status: 'connected',
        micActive,
        tabActive: Boolean(tabStream),
        source: input.source,
        sampleRate: audioContext?.sampleRate ?? 0,
      })
    }
    socket.onerror = () => {
      report('CAPTURE_ERROR', { error: `Could not connect to the gateway at ${message.wsUrl}.` })
      stopCapture()
    }
    socket.onclose = () => {
      if (active) {
        report('CAPTURE_ERROR', { error: 'The gateway closed the audio connection.' })
        stopCapture()
      }
    }

    connections.push({ socket, worklet, sourceNode, gain, source: input.source })
  }

  watchdog = setTimeout(() => {
    if (!active || chunksSent > 0) return
    const state = audioContext?.state ?? 'closed'
    report('CAPTURE_ERROR', {
      error: `No audio frames arrived (AudioContext ${state}). Keep the Meet tab open and unmuted, then retry.`,
    })
    stopCapture()
  }, 8000)
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.target !== 'offscreen') return

  if (message.type === 'START_CAPTURE') {
    startCapture(message)
      .then(() => sendResponse({ status: 'STARTED' }))
      .catch((error) => {
        stopCapture()
        report('CAPTURE_ERROR', { error: String(error) })
        sendResponse({ status: 'ERROR', error: String(error) })
      })
    return true
  }

  if (message.type === 'STOP_CAPTURE') {
    stopCapture()
    sendResponse({ status: 'STOPPED' })
    return true
  }
})
