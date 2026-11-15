<template>
  <div class="popup-container">
    <div class="popup-header">
      <div>
        <h1 class="title">AUB Meeting Ingress</h1>
        <p class="subtitle">Google Meet WebRTC Streamer</p>
      </div>
      <span
        class="status-badge"
        :class="isStreaming ? 'status-active' : 'status-idle'"
      >
        {{ isStreaming ? 'Capturing' : 'Idle' }}
      </span>
    </div>

    <!-- Active Stream Controls -->
    <div class="telemetry-card">
      <div style="display: flex; justify-content: space-between;">
        <span>Ingress Format:</span>
        <strong>16,000 Hz Linear PCM</strong>
      </div>
      <div style="display: flex; justify-content: space-between;">
        <span>Target Gateway:</span>
        <strong style="color: #3A78C5;">ws://localhost:8000</strong>
      </div>
      <div v-if="isStreaming" style="display: flex; justify-content: space-between;">
        <span>Chunks Transmitted:</span>
        <strong style="color: #5B0015;">{{ chunkCount }} segments</strong>
      </div>
    </div>

    <!-- Start / Stop Button (10% Horizon Accent or Bordeaux) -->
    <button
      v-if="!isStreaming"
      @click="startIngress"
      class="btn-primary"
    >
      Start Meeting Capture
    </button>
    <button
      v-else
      @click="stopIngress"
      class="btn-danger"
    >
      Stop & Adjourn Stream
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';

const isStreaming = ref(false);
const chunkCount = ref(0);
let chunkTimer: any = null;

onMounted(() => {
  if (typeof chrome !== 'undefined' && chrome.runtime) {
    chrome.runtime.sendMessage({ action: 'GET_STATUS' }, (res) => {
      if (res && res.isCapturing) {
        isStreaming.value = true;
      }
    });
  }
});

function startIngress() {
  if (typeof chrome !== 'undefined' && chrome.runtime) {
    chrome.runtime.sendMessage(
      { action: 'START_CAPTURE', meetingId: 'demo-meeting-01' },
      (res) => {
        isStreaming.value = true;
        chunkCount.value = 0;
        chunkTimer = setInterval(() => {
          chunkCount.value += 1;
        }, 3000);
      }
    );
  } else {
    // Development mode fallback
    isStreaming.value = true;
    chunkCount.value = 0;
    chunkTimer = setInterval(() => {
      chunkCount.value += 1;
    }, 3000);
  }
}

function stopIngress() {
  if (chunkTimer) clearInterval(chunkTimer);
  if (typeof chrome !== 'undefined' && chrome.runtime) {
    chrome.runtime.sendMessage({ action: 'STOP_CAPTURE' }, () => {
      isStreaming.value = false;
    });
  } else {
    isStreaming.value = false;
  }
}
</script>
