const status = document.getElementById('status')
const allow = document.getElementById('allow')

function setStatus(message) {
  if (status) status.textContent = message
}

if (navigator.permissions?.query) {
  navigator.permissions
    .query({ name: 'microphone' })
    .then((permission) => {
      if (permission.state === 'granted') {
        setStatus('Microphone permission is already granted. Close this tab and start capture again.')
      } else if (permission.state === 'denied') {
        setStatus(
          'Chrome has blocked the microphone for this extension. Remove the block in Chrome settings, then reload this page.',
        )
      }
    })
    .catch(() => undefined)
}

allow?.addEventListener('click', async () => {
  allow.disabled = true
  setStatus('Requesting microphone access…')
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    stream.getTracks().forEach((track) => track.stop())
    setStatus('Microphone enabled. You can close this tab and start capture again.')
  } catch (error) {
    allow.disabled = false
    setStatus(
      `Could not enable the microphone: ${error?.message ?? error}. ` +
        'Check Chrome and macOS microphone permissions, then try again.',
    )
  }
})
