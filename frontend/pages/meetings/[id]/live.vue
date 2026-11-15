<template>
  <div class="space-y-6 max-w-7xl mx-auto">
    <!-- Top Action & Status Bar -->
    <div class="bg-white border border-ivory-200 rounded-3xl p-6 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      <div class="space-y-1">
        <div class="flex items-center space-x-2">
          <span class="relative flex h-3 w-3">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-3 w-3 bg-red-600"></span>
          </span>
          <span class="text-xs font-bold text-red-600 uppercase tracking-wider">Live Streaming Ingress</span>
          <span class="text-xs text-bordeaux-700 font-medium">• Google Meet Tab: Active</span>
        </div>
        <h2 class="text-2xl font-extrabold text-bordeaux-950">Faculty Board Review: Research Methodology Proposals</h2>
      </div>

      <!-- Action & Audio Telemetry (10% Horizon Accent) -->
      <div class="flex items-center space-x-3 w-full sm:w-auto">
        <!-- Live Audio Waveform Animation -->
        <div class="flex items-center space-x-1 px-3 py-2 bg-ivory-100 rounded-xl border border-ivory-200">
          <span class="w-1 h-3 bg-horizon-500 rounded-full animate-bounce"></span>
          <span class="w-1 h-6 bg-horizon-600 rounded-full animate-bounce" style="animation-delay: 0.1s"></span>
          <span class="w-1 h-4 bg-horizon-500 rounded-full animate-bounce" style="animation-delay: 0.2s"></span>
          <span class="w-1 h-7 bg-horizon-700 rounded-full animate-bounce" style="animation-delay: 0.3s"></span>
          <span class="w-1 h-3 bg-horizon-500 rounded-full animate-bounce" style="animation-delay: 0.15s"></span>
          <span class="text-[11px] font-bold text-bordeaux-900 ml-2">16kHz PCM</span>
        </div>

        <NuxtLink
          :to="`/meetings/${meetingId}/review`"
          class="px-5 py-2.5 rounded-2xl bg-horizon-500 hover:bg-horizon-600 text-bordeaux-950 font-bold text-xs shadow-md transition-all flex items-center space-x-2"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <span>Adjourn & Generate MoM</span>
        </NuxtLink>
      </div>
    </div>

    <!-- Dual-Pane Live Transcript Console (60% Ivory Canvas / 30% Bordeaux Content / 10% Horizon Streaming Badges) -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Left Column: Original Khmer / Code-Switched Speech -->
      <div class="bg-white border border-ivory-200 rounded-3xl p-6 shadow-sm flex flex-col h-[600px]">
        <div class="flex items-center justify-between pb-4 border-b border-ivory-200">
          <div class="flex items-center space-x-2">
            <span class="p-1.5 rounded-lg bg-bordeaux-100 text-bordeaux-900">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 100-6 3 3 0 000 6z" />
              </svg>
            </span>
            <h3 class="font-bold text-sm text-bordeaux-950 uppercase tracking-wider">
              Original Spoken Utterance (Khmer / English)
            </h3>
          </div>
          <span class="text-[11px] font-bold px-2.5 py-0.5 rounded bg-bordeaux-100 text-bordeaux-900">
            Omnilingual-ASR-Khm
          </span>
        </div>

        <div class="flex-1 overflow-y-auto py-4 space-y-4 pr-2">
          <div
            v-for="(seg, idx) in segments"
            :key="idx"
            class="p-4 rounded-2xl bg-ivory-50 border border-ivory-200 space-y-1.5 hover:border-horizon-300 transition-all"
          >
            <div class="flex items-center justify-between text-xs">
              <span class="font-bold text-bordeaux-900 flex items-center space-x-1.5">
                <span class="h-2 w-2 rounded-full bg-horizon-500"></span>
                <span>{{ seg.speaker_label }}</span>
              </span>
              <span class="text-bordeaux-600 font-mono">{{ seg.start_timestamp }}s - {{ seg.end_timestamp }}s</span>
            </div>
            <p class="text-sm font-medium text-bordeaux-950 leading-relaxed font-sans">
              {{ seg.original_text }}
            </p>
          </div>
        </div>
      </div>

      <!-- Right Column: Real-Time English / Khmer Translation -->
      <div class="bg-white border border-ivory-200 rounded-3xl p-6 shadow-sm flex flex-col h-[600px]">
        <div class="flex items-center justify-between pb-4 border-b border-ivory-200">
          <div class="flex items-center space-x-2">
            <span class="p-1.5 rounded-lg bg-horizon-100 text-horizon-800">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
              </svg>
            </span>
            <h3 class="font-bold text-sm text-bordeaux-950 uppercase tracking-wider">
              Live Bidirectional Translation
            </h3>
          </div>
          <span class="text-[11px] font-bold px-2.5 py-0.5 rounded bg-horizon-100 text-horizon-800">
            Netra-NMT (77M)
          </span>
        </div>

        <div class="flex-1 overflow-y-auto py-4 space-y-4 pr-2">
          <div
            v-for="(seg, idx) in segments"
            :key="idx"
            class="p-4 rounded-2xl bg-ivory-50 border border-ivory-200 space-y-1.5 border-l-4 border-l-horizon-500"
          >
            <div class="flex items-center justify-between text-xs">
              <span class="font-semibold text-horizon-800">English Translation</span>
              <span class="text-bordeaux-600 font-mono">Confidence: {{ Math.round(seg.confidence_score * 100) }}%</span>
            </div>
            <p class="text-sm italic text-bordeaux-900 leading-relaxed">
              {{ seg.translated_text }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const meetingId = ref(route.params.id || 'demo-meeting-01')

const segments = ref([
  {
    speaker_label: 'Dean Lay Thou',
    start_timestamp: 0.0,
    end_timestamp: 4.5,
    original_text: 'សូមជម្រាបសួរលោកគ្រូអ្នកគ្រូទាំងអស់គ្នា ថ្ងៃនេះយើងប្រជុំ review the project proposal របស់ក្រុមទី ៤.',
    translated_text: 'Good morning teachers and everyone, today we meet to review Group 4\'s project proposal.',
    confidence_score: 0.97
  },
  {
    speaker_label: 'Khorn Molika (Group 4)',
    start_timestamp: 5.0,
    end_timestamp: 11.2,
    original_text: 'ជំរាបសួរលោកគ្រូ! ក្រុមយើងបាន design software architecture ដោយប្រើ Nuxt 3, FastAPI និង Omnilingual ASR.',
    translated_text: 'Hello teacher! Our team designed the software architecture utilizing Nuxt 3, FastAPI, and Omnilingual ASR.',
    confidence_score: 0.95
  },
  {
    speaker_label: 'Dean Lay Thou',
    start_timestamp: 12.0,
    end_timestamp: 17.8,
    original_text: 'ល្អណាស់! យើងត្រូវ enforce human-in-the-loop review មុនពេល export MoM ទៅ Google Docs.',
    translated_text: 'Excellent! We must enforce human-in-the-loop review before exporting the MoM to Google Docs.',
    confidence_score: 0.98
  },
  {
    speaker_label: 'Heng Liza (Group 4)',
    start_timestamp: 18.5,
    end_timestamp: 24.0,
    original_text: 'បាទលោកគ្រូ! Action items ទាំងអស់នឹង sync ចូល Google Sheets ដោយស្វ័យប្រវត្តិតាម Sheets API.',
    translated_text: 'Yes teacher! All action items will automatically synchronize into Google Sheets via the Sheets API.',
    confidence_score: 0.96
  }
])

let ws: WebSocket | null = null

onMounted(() => {
  // Connect to live transcript WebSocket
  try {
    const wsUrl = `ws://localhost:8000/ws/live-transcript/${meetingId.value}`
    ws = new WebSocket(wsUrl)
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'transcript_segment') {
          segments.value.push(data)
        }
      } catch (e) {
        // Ignored
      }
    }
  } catch (err) {
    console.warn('Live WebSocket unavailable, displaying simulated real-time stream:', err)
  }
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
})
</script>
