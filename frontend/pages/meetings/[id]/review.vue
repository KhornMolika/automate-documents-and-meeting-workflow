<template>
  <div class="space-y-6 max-w-7xl mx-auto">
    <!-- Top Action Bar -->
    <div class="bg-white border border-ivory-200 rounded-3xl p-6 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      <div class="space-y-1">
        <div class="flex items-center space-x-2">
          <span class="px-2.5 py-1 rounded-md text-xs font-bold bg-bordeaux-100 text-bordeaux-900 uppercase tracking-wider">
            Human-in-the-Loop Verification
          </span>
          <span class="text-xs text-bordeaux-700 font-medium">• Reviewer: Certified Coordinator</span>
        </div>
        <h2 class="text-2xl font-extrabold text-bordeaux-950">
          Faculty Board Review — Minutes of Meeting (MoM)
        </h2>
      </div>

      <!-- Publishing Action (10% Horizon Accent Button) -->
      <div class="flex items-center space-x-3 w-full sm:w-auto">
        <button
          @click="saveDraft"
          class="px-4 py-2.5 rounded-2xl bg-ivory-200 hover:bg-ivory-300 text-bordeaux-950 font-semibold text-xs transition-all"
        >
          Save Draft
        </button>

        <button
          @click="approveAndExport"
          :disabled="isPublishing"
          class="px-6 py-2.5 rounded-2xl bg-horizon-500 hover:bg-horizon-600 disabled:opacity-50 text-bordeaux-950 font-extrabold text-xs shadow-md transition-all flex items-center space-x-2"
        >
          <svg v-if="!isPublishing" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <span v-else class="h-3 w-3 rounded-full border-2 border-bordeaux-950 border-t-transparent animate-spin"></span>
          <span>{{ isPublishing ? 'Publishing to Workspace...' : 'Approve & Publish to Google Workspace' }}</span>
        </button>
      </div>
    </div>

    <!-- Export Success Notice -->
    <div
      v-if="exportResult"
      class="p-5 rounded-2xl bg-green-50 border border-green-200 text-green-900 flex items-center justify-between shadow-sm animate-fade-in"
    >
      <div class="flex items-center space-x-3">
        <span class="p-2 rounded-xl bg-green-100 text-green-800">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </span>
        <div>
          <h4 class="font-bold text-sm">Successfully Published to Google Workspace!</h4>
          <p class="text-xs text-green-800">Formal MoM created in Google Docs • Action items logged to Google Sheets • Gmail alerts sent.</p>
        </div>
      </div>

      <div class="flex items-center space-x-2">
        <a
          :href="exportResult.docUrl"
          target="_blank"
          class="px-4 py-2 rounded-xl bg-white border border-green-300 text-green-950 font-bold text-xs shadow-sm hover:bg-green-50 flex items-center space-x-1"
        >
          <span>Open Google Doc</span>
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>
      </div>
    </div>

    <!-- Split-Screen Editor (60% Ivory Surface / 30% Bordeaux Structure / 10% Horizon Highlights) -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <!-- Left Column: Source Transcript Reference (5 Columns) -->
      <div class="lg:col-span-5 bg-white border border-ivory-200 rounded-3xl p-6 shadow-sm flex flex-col h-[750px]">
        <div class="pb-3 border-b border-ivory-200 flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="p-1 rounded bg-ivory-200 text-bordeaux-900">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </span>
            <h3 class="font-bold text-xs uppercase tracking-wider text-bordeaux-950">Source Speech Transcript</h3>
          </div>
          <span class="text-[11px] text-bordeaux-700">Chronological</span>
        </div>

        <div class="flex-1 overflow-y-auto py-4 space-y-3 pr-2">
          <div
            v-for="(seg, idx) in sourceTranscripts"
            :key="idx"
            class="p-3.5 rounded-xl bg-ivory-50 border border-ivory-200 text-xs space-y-1 hover:border-horizon-300 transition-colors"
          >
            <div class="flex items-center justify-between font-bold text-bordeaux-950">
              <span>{{ seg.speaker }}</span>
              <span class="text-[10px] text-bordeaux-600 font-mono">{{ seg.time }}</span>
            </div>
            <p class="text-bordeaux-900 font-sans leading-relaxed">{{ seg.khmerText }}</p>
            <p class="text-[11px] text-bordeaux-700 italic border-l-2 border-horizon-400 pl-2 mt-1">
              {{ seg.englishText }}
            </p>
          </div>
        </div>
      </div>

      <!-- Right Column: Interactive Editable MoM Document (7 Columns) -->
      <div class="lg:col-span-7 bg-white border border-ivory-200 rounded-3xl p-8 shadow-md space-y-6 max-h-[750px] overflow-y-auto">
        <!-- Document Institutional Header -->
        <div class="border-b-2 border-bordeaux-900 pb-4 flex items-center justify-between">
          <div>
            <h3 class="text-base font-extrabold text-bordeaux-950 tracking-wider">ACLEDA UNIVERSITY OF BUSINESS</h3>
            <p class="text-xs text-bordeaux-700">Faculty of Science & Technology • Official Minutes of Meeting</p>
          </div>
          <span class="text-xs font-bold text-bordeaux-900 px-2.5 py-1 rounded bg-ivory-100 border border-ivory-200">
            Form MoM-04
          </span>
        </div>

        <!-- Section 1: Executive Summary -->
        <div class="space-y-2">
          <label class="block text-xs font-bold uppercase tracking-wider text-bordeaux-900 flex items-center justify-between">
            <span>1. Executive Summary (AI Synthesized)</span>
            <span class="text-[11px] font-normal text-bordeaux-600">Editable</span>
          </label>
          <textarea
            v-model="mom.executiveSummary"
            rows="4"
            class="w-full p-4 text-xs leading-relaxed bg-ivory-50 border border-ivory-200 rounded-2xl text-bordeaux-950 focus:outline-none focus:ring-2 focus:ring-horizon-500 focus:bg-white transition-all font-sans"
          ></textarea>
        </div>

        <!-- Section 2: Key Discussion Points -->
        <div class="space-y-2">
          <label class="block text-xs font-bold uppercase tracking-wider text-bordeaux-900">
            2. Key Discussion Points
          </label>
          <div class="space-y-2">
            <div
              v-for="(point, idx) in mom.discussionPoints"
              :key="idx"
              class="flex items-center space-x-2"
            >
              <span class="h-2 w-2 rounded-full bg-horizon-500 flex-shrink-0"></span>
              <input
                v-model="mom.discussionPoints[idx]"
                type="text"
                class="flex-1 px-3 py-2 bg-ivory-50 border border-ivory-200 rounded-xl text-xs text-bordeaux-950 focus:outline-none focus:ring-2 focus:ring-horizon-500"
              />
            </div>
          </div>
        </div>

        <!-- Section 3: Formal Agreed Decisions -->
        <div class="space-y-2">
          <label class="block text-xs font-bold uppercase tracking-wider text-bordeaux-900">
            3. Formal Agreed Decisions
          </label>
          <div class="divide-y divide-ivory-200 border border-ivory-200 rounded-2xl overflow-hidden">
            <div
              v-for="(dec, idx) in mom.decisions"
              :key="idx"
              class="p-4 bg-ivory-50/50 space-y-1.5"
            >
              <div class="flex items-center justify-between text-xs font-bold text-bordeaux-900">
                <span class="text-horizon-800">{{ dec.agendaTopic }}</span>
                <span class="text-[10px] text-green-700 bg-green-100 px-2 py-0.5 rounded-full font-bold">Unanimous</span>
              </div>
              <input
                v-model="dec.decisionText"
                class="w-full px-3 py-1.5 bg-white border border-ivory-200 rounded-lg text-xs font-semibold text-bordeaux-950 focus:outline-none focus:ring-1 focus:ring-horizon-500"
              />
            </div>
          </div>
        </div>

        <!-- Section 4: Action Items Registry -->
        <div class="space-y-2">
          <label class="block text-xs font-bold uppercase tracking-wider text-bordeaux-900 flex items-center justify-between">
            <span>4. Delegated Action Items (Syncs to Google Sheets)</span>
            <span class="text-[11px] font-semibold text-horizon-700">Auto-Assigned</span>
          </label>

          <div class="space-y-3">
            <div
              v-for="(item, idx) in mom.actionItems"
              :key="idx"
              class="p-4 bg-ivory-50 border border-ivory-200 rounded-2xl space-y-3"
            >
              <input
                v-model="item.taskDescription"
                class="w-full px-3 py-2 bg-white border border-ivory-200 rounded-xl text-xs font-bold text-bordeaux-950 focus:outline-none focus:ring-2 focus:ring-horizon-500"
              />

              <div class="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <label class="block text-[11px] text-bordeaux-700 mb-1 font-medium">Assignee Name</label>
                  <input
                    v-model="item.assigneeName"
                    class="w-full px-3 py-1.5 bg-white border border-ivory-200 rounded-lg text-xs text-bordeaux-950 focus:outline-none focus:ring-1 focus:ring-horizon-500"
                  />
                </div>
                <div>
                  <label class="block text-[11px] text-bordeaux-700 mb-1 font-medium">Target Deadline</label>
                  <input
                    v-model="item.deadline"
                    type="date"
                    class="w-full px-3 py-1.5 bg-white border border-ivory-200 rounded-lg text-xs text-bordeaux-950 focus:outline-none focus:ring-1 focus:ring-horizon-500"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const isPublishing = ref(false)
const exportResult = ref<any | null>(null)

const sourceTranscripts = ref([
  {
    speaker: 'Dean Lay Thou',
    time: '00:02:15',
    khmerText: 'សូមជម្រាបសួរលោកគ្រូអ្នកគ្រូទាំងអស់គ្នា ថ្ងៃនេះយើងប្រជុំ review the project proposal របស់ក្រុមទី ៤.',
    englishText: 'Good morning everyone, today we meet to review Group 4\'s project proposal.'
  },
  {
    speaker: 'Khorn Molika',
    time: '00:05:40',
    khmerText: 'យើងបាន deploy Chrome extension ដើម្បី capture Meet audio ហើយ stream តាម WebSockets.',
    englishText: 'We deployed the Chrome extension to capture Meet audio and stream over WebSockets.'
  },
  {
    speaker: 'Dean Lay Thou',
    time: '00:14:10',
    khmerText: 'Dean Office បាន approve budget សម្រាប់ compute node RTX 4090.',
    englishText: 'The Dean\'s Office has approved the budget for the RTX 4090 compute node.'
  },
  {
    speaker: 'Em Panharith',
    time: '00:22:30',
    khmerText: 'ខ្ញុំនឹងរៀបចំ Docker orchestration សម្រាប់ local speech tier មុនថ្ងៃសុក្រ.',
    englishText: 'I will prepare the Docker orchestration for the local speech tier before Friday.'
  }
])

const mom = ref({
  executiveSummary: 'During the Faculty Board Review session at ACLEDA University of Business, committee members formally evaluated Group 4\'s Design Science Research project. The system successfully demonstrated bilingual speech transcription, Google Gemini 1.5 Pro decision mining, and direct synchronization with Google Workspace.',
  discussionPoints: [
    'Evaluated DSRM engineering artifacts and 6-phase research lifecycle.',
    'Reviewed bilingual code-switching WER metrics and Netra-NMT translation adequacy.',
    'Confirmed data privacy enclaves ensuring raw meeting audio remains on local campus hardware.'
  ],
  decisions: [
    {
      agendaTopic: 'Hardware Infrastructure Approval',
      decisionText: 'Approved procurement and deployment of on-premise NVIDIA RTX 4090 GPU node for local speech tier inference.'
    },
    {
      agendaTopic: 'MoM Verification Policy',
      decisionText: 'Mandated strict human-in-the-loop verification before exporting official administrative records to Google Docs.'
    }
  ],
  actionItems: [
    {
      taskDescription: 'Finalize Docker containerization and Alembic database migration scripts for campus deployment.',
      assigneeName: 'Em Panharith',
      deadline: '2026-11-20'
    },
    {
      taskDescription: 'Configure Google Cloud OAuth 2.0 credentials and least-privilege REST scopes.',
      assigneeName: 'Khorn Molika',
      deadline: '2026-11-21'
    }
  ]
})

function saveDraft() {
  alert('Draft Minutes of Meeting saved to institutional PostgreSQL database.')
}

async function approveAndExport() {
  isPublishing.value = true
  setTimeout(() => {
    isPublishing.value = false
    exportResult.value = {
      docId: '1aub_mom_99f2a',
      docUrl: 'https://docs.google.com/document/d/1aub_mom_99f2a/edit',
      sheetId: '1aub_tasks_45b8e',
      sheetUrl: 'https://docs.google.com/spreadsheets/d/1aub_tasks_45b8e/edit'
    }
  }, 1200)
}
</script>
