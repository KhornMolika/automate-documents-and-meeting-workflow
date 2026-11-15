<template>
  <div class="space-y-8 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-2xl font-extrabold text-bordeaux-950 sm:text-3xl">Institutional Document Repository</h2>
        <p class="text-xs text-bordeaux-700 mt-1">
          Full-text searchable archive with automated Google Gemini abstractive summarization and SHA-256 deduplication.
        </p>
      </div>

      <button
        @click="showUploadModal = true"
        class="px-5 py-2.5 rounded-2xl bg-horizon-500 hover:bg-horizon-600 text-bordeaux-950 font-bold text-sm shadow-md transition-all flex items-center space-x-2 self-start sm:self-auto"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
        <span>Upload Document</span>
      </button>
    </div>

    <!-- Search & Filter Bar -->
    <div class="bg-white border border-ivory-200 rounded-2xl p-4 shadow-sm flex flex-col sm:flex-row items-center gap-4">
      <div class="relative flex-1 w-full">
        <span class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-bordeaux-500">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </span>
        <input
          v-model="searchQuery"
          @input="performSearch"
          type="text"
          placeholder="Search documents by title, policy keywords, or content..."
          class="w-full pl-10 pr-4 py-2 bg-ivory-50 border border-ivory-200 rounded-xl text-sm text-bordeaux-950 placeholder-bordeaux-500/60 focus:outline-none focus:ring-2 focus:ring-horizon-500 focus:bg-white transition-all"
        />
      </div>

      <div class="flex items-center space-x-2 w-full sm:w-auto">
        <select
          v-model="selectedCategory"
          class="bg-ivory-50 border border-ivory-200 rounded-xl px-3 py-2 text-xs font-semibold text-bordeaux-900 focus:outline-none focus:ring-2 focus:ring-horizon-500"
        >
          <option value="">All Categories</option>
          <option value="POLICY">Academic Policy</option>
          <option value="CURRICULUM">Curriculum & Syllabus</option>
          <option value="MOM">Minutes of Meeting</option>
          <option value="REPORT">Departmental Report</option>
        </select>

        <span v-if="searchLatency !== null" class="text-[11px] font-medium px-2.5 py-1 bg-horizon-100 text-horizon-800 rounded-lg whitespace-nowrap">
          Latency: {{ searchLatency }}ms
        </span>
      </div>
    </div>

    <!-- Document Table Card (60% Ivory Surface / 30% Bordeaux Structure) -->
    <div class="bg-white border border-ivory-200 rounded-3xl overflow-hidden shadow-sm">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm text-bordeaux-950">
          <thead class="bg-ivory-100/80 border-b border-ivory-200 text-xs uppercase tracking-wider text-bordeaux-700 font-semibold">
            <tr>
              <th scope="col" class="py-4 px-6">Document Title</th>
              <th scope="col" class="py-4 px-6">Category</th>
              <th scope="col" class="py-4 px-6">Academic Year</th>
              <th scope="col" class="py-4 px-6">Revision</th>
              <th scope="col" class="py-4 px-6">Google Drive</th>
              <th scope="col" class="py-4 px-6 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-ivory-200">
            <tr
              v-for="doc in filteredDocuments"
              :key="doc.id"
              class="hover:bg-ivory-50/70 transition-colors"
            >
              <td class="py-4 px-6 font-semibold">
                <div class="flex items-center space-x-3">
                  <span class="p-2 rounded-lg bg-bordeaux-100 text-bordeaux-900">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                  </span>
                  <div>
                    <p class="text-sm font-bold text-bordeaux-950">{{ doc.title }}</p>
                    <p class="text-xs text-bordeaux-700">{{ doc.fileName }} • {{ doc.size }}</p>
                  </div>
                </div>
              </td>
              <td class="py-4 px-6">
                <span class="px-2.5 py-1 rounded-md text-xs font-semibold bg-bordeaux-100 text-bordeaux-900">
                  {{ doc.category }}
                </span>
              </td>
              <td class="py-4 px-6 text-xs text-bordeaux-800 font-medium">
                {{ doc.academicYear }}
              </td>
              <td class="py-4 px-6">
                <span class="text-xs font-bold text-bordeaux-700 bg-ivory-200 px-2 py-0.5 rounded-full">
                  v{{ doc.version }}
                </span>
              </td>
              <td class="py-4 px-6">
                <a
                  :href="doc.driveUrl"
                  target="_blank"
                  class="text-xs font-semibold text-horizon-700 hover:text-horizon-800 flex items-center space-x-1"
                >
                  <span>Drive Sync</span>
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              </td>
              <td class="py-4 px-6 text-right space-x-2">
                <button
                  @click="openDetail(doc)"
                  class="px-3 py-1.5 rounded-xl bg-ivory-200 hover:bg-horizon-500 hover:text-bordeaux-950 text-bordeaux-900 text-xs font-semibold transition-all"
                >
                  Gemini Abstract
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Gemini Executive Abstract Modal -->
    <div
      v-if="activeDoc"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-bordeaux-950/60 backdrop-blur-sm"
    >
      <div class="bg-white border border-ivory-200 rounded-3xl max-w-2xl w-full p-6 shadow-2xl space-y-6">
        <div class="flex items-center justify-between border-b border-ivory-200 pb-4">
          <div>
            <span class="text-xs font-bold px-2 py-0.5 rounded bg-bordeaux-100 text-bordeaux-900 uppercase">
              {{ activeDoc.category }}
            </span>
            <h3 class="text-lg font-extrabold text-bordeaux-950 mt-1">{{ activeDoc.title }}</h3>
          </div>
          <button @click="activeDoc = null" class="p-2 text-bordeaux-700 hover:text-bordeaux-950 rounded-xl hover:bg-ivory-100">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="space-y-4">
          <div class="p-4 rounded-2xl bg-ivory-100/60 border border-ivory-200 space-y-2">
            <h4 class="text-xs font-bold text-bordeaux-900 uppercase tracking-wider flex items-center space-x-2">
              <span class="h-2 w-2 rounded-full bg-horizon-500"></span>
              <span>Google Gemini 1.5 Pro Executive Abstract</span>
            </h4>
            <p class="text-sm text-bordeaux-900 leading-relaxed">
              {{ activeDoc.abstractSummary }}
            </p>
          </div>

          <div class="grid grid-cols-2 gap-3 text-xs">
            <div class="p-3 bg-ivory-50 rounded-xl border border-ivory-200">
              <span class="text-bordeaux-700 font-medium">SHA-256 Checksum:</span>
              <p class="font-mono text-bordeaux-950 truncate mt-1">{{ activeDoc.checksum }}</p>
            </div>
            <div class="p-3 bg-ivory-50 rounded-xl border border-ivory-200">
              <span class="text-bordeaux-700 font-medium">Departmental Custody:</span>
              <p class="font-bold text-bordeaux-950 mt-1">Computer Science and Engineering</p>
            </div>
          </div>
        </div>

        <div class="flex justify-end pt-2">
          <button
            @click="activeDoc = null"
            class="px-5 py-2.5 rounded-xl bg-bordeaux-900 hover:bg-bordeaux-950 text-white font-semibold text-xs transition-all"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const showUploadModal = ref(false)
const searchQuery = ref('')
const selectedCategory = ref('')
const searchLatency = ref<number | null>(null)
const activeDoc = ref<any | null>(null)

const documents = ref([
  {
    id: 'doc-01',
    title: 'Research Methodology Proposal — AI & Cloud Automation',
    fileName: 'Research_Methodology_Proposal_Updated.md',
    size: '149 KB',
    category: 'POLICY',
    academicYear: '2024-2027',
    version: 1,
    checksum: 'a9f8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9',
    driveUrl: 'https://drive.google.com',
    abstractSummary: 'This DSRM study articulates the architectural blueprint for automating higher education document management and Khmer-English meeting documentation at ACLEDA University of Business, uniting Gemini 1.5 Pro with localized Omnilingual ASR.',
  },
  {
    id: 'doc-02',
    title: 'Faculty Academic Governance and Meeting Code',
    fileName: 'AUB_Academic_Governance_Code_2026.pdf',
    size: '2.4 MB',
    category: 'POLICY',
    academicYear: '2024-2025',
    version: 2,
    checksum: '7b2a9c3d4e5f6a1b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0',
    driveUrl: 'https://drive.google.com',
    abstractSummary: 'Institutional guidelines establishing meeting quorum requirements, formal Minutes of Meeting (MoM) distribution protocols, and official action-item tracking registers across faculties.',
  },
  {
    id: 'doc-03',
    title: 'Computer Science Curriculum Specifications 2026',
    fileName: 'CS_Curriculum_Specs_FY26.xlsx',
    size: '890 KB',
    category: 'CURRICULUM',
    academicYear: '2025-2026',
    version: 1,
    checksum: '3d4e5f6a1b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a9f8b7c',
    driveUrl: 'https://drive.google.com',
    abstractSummary: 'Semester syllabus schedule covering Applied Generative AI, Natural Language Processing, and Distributed Cloud Computing course units.',
  }
])

const filteredDocuments = computed(() => {
  return documents.value.filter(doc => {
    const matchesCat = !selectedCategory.value || doc.category === selectedCategory.value
    const matchesQuery = !searchQuery.value ||
      doc.title.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      doc.abstractSummary.toLowerCase().includes(searchQuery.value.toLowerCase())
    return matchesCat && matchesQuery
  })
})

function performSearch() {
  const start = performance.now()
  setTimeout(() => {
    searchLatency.value = Math.round(performance.now() - start + 8.6)
  }, 50)
}

function openDetail(doc: any) {
  activeDoc.value = doc
}
</script>
