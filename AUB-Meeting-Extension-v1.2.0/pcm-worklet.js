/**
 * AudioWorklet that downsamples the mixed meeting audio to 16 kHz mono PCM
 * and emits a chunk every `chunkSeconds` (default 5 seconds).
 *
 * Runs on the audio rendering thread, so it replaces the deprecated
 * ScriptProcessorNode without glitching the main thread.
 */
class PCMChunkProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super()
    const settings = options?.processorOptions ?? {}
    this.targetRate = settings.targetRate || 16000
    this.chunkSamples = this.targetRate * (settings.chunkSeconds || 5)
    this.ratio = sampleRate / this.targetRate
    this.buffer = new Int16Array(this.chunkSamples)
    this.offset = 0
    this.sum = 0
    this.count = 0
  }

  process(inputs) {
    const input = inputs[0]
    if (!input || !input[0]) return true
    const channel = input[0]

    for (let index = 0; index < channel.length; index += 1) {
      this.sum += channel[index]
      this.count += 1
      if (this.count < this.ratio) continue

      const value = Math.max(-1, Math.min(1, this.sum / this.count))
      this.buffer[this.offset] = value < 0 ? value * 0x8000 : value * 0x7fff
      this.offset += 1
      this.sum = 0
      this.count = 0

      if (this.offset >= this.chunkSamples) {
        const chunk = this.buffer.slice(0, this.offset)
        let peak = 0
        for (let sample = 0; sample < chunk.length; sample += 1) {
          const magnitude = Math.abs(chunk[sample])
          if (magnitude > peak) peak = magnitude
        }
        this.port.postMessage(
          { pcm: chunk.buffer, peak: Number((peak / 32768).toFixed(4)) },
          [chunk.buffer],
        )
        this.buffer = new Int16Array(this.chunkSamples)
        this.offset = 0
      }
    }

    return true
  }
}

registerProcessor('pcm-chunk-processor', PCMChunkProcessor)
