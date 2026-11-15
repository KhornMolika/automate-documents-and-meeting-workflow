<template>
  <div class="space-y-8 max-w-7xl mx-auto">
    <!-- Welcome Header Banner -->
    <div class="bg-gradient-to-r from-bordeaux-900 to-bordeaux-800 rounded-3xl p-8 text-white shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-6 relative overflow-hidden">
      <div class="relative z-10 max-w-2xl">
        <div class="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-bordeaux-950/60 border border-horizon-500/40 text-horizon-300 text-xs font-semibold uppercase tracking-wider mb-3">
          <span>Faculty of Science & Technology</span>
          <span>•</span>
          <span>Computer Science</span>
        </div>
        <h2 class="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          Institutional Document & Meeting AI
        </h2>
        <p class="mt-2 text-ivory-200 text-sm leading-relaxed">
          Automating academic records, Khmer-English meeting transcription, and Google Workspace delivery with Design Science Research rigor.
        </p>
      </div>

      <div class="flex items-center gap-3 relative z-10">
        <NuxtLink
          to="/meetings"
          class="px-5 py-3 rounded-2xl bg-horizon-500 hover:bg-horizon-600 text-bordeaux-950 font-bold text-sm shadow-md transition-all flex items-center space-x-2"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          <span>New Meeting</span>
        </NuxtLink>
        <NuxtLink
          to="/documents"
          class="px-5 py-3 rounded-2xl bg-ivory-100/10 hover:bg-ivory-100/20 text-white font-medium text-sm border border-white/20 transition-all"
        >
          Browse Documents
        </NuxtLink>
      </div>
    </div>

    <!-- 4 Key Metrics Cards (60% Ivory Mist Surface with 10% Horizon Highlights) -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
      <div class="bg-ivory-100 border border-ivory-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-bordeaux-700 uppercase tracking-wider">MoM Delivery Speedup</span>
          <span class="p-2 bg-horizon-100 text-horizon-700 rounded-xl">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </span>
        </div>
        <p class="text-3xl font-extrabold text-bordeaux-950 mt-3">88.7%</p>
        <p class="text-xs text-bordeaux-700 mt-1">245m &rarr; 27.75m turnaround</p>
      </div>

      <div class="bg-ivory-100 border border-ivory-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-bordeaux-700 uppercase tracking-wider">Usability SUS Score</span>
          <span class="p-2 bg-horizon-100 text-horizon-700 rounded-xl">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </span>
        </div>
        <p class="text-3xl font-extrabold text-bordeaux-950 mt-3">84.2<span class="text-lg font-normal text-bordeaux-700">/100</span></p>
        <p class="text-xs text-bordeaux-700 mt-1">Grade A (96th percentile, N=40)</p>
      </div>

      <div class="bg-ivory-100 border border-ivory-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-bordeaux-700 uppercase tracking-wider">Code-Switching WER</span>
          <span class="p-2 bg-horizon-100 text-horizon-700 rounded-xl">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 100-6 3 3 0 000 6z" />
            </svg>
          </span>
        </div>
        <p class="text-3xl font-extrabold text-bordeaux-950 mt-3">16.4%</p>
        <p class="text-xs text-bordeaux-700 mt-1">61.7% error reduction over baseline</p>
      </div>

      <div class="bg-ivory-100 border border-ivory-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-bordeaux-700 uppercase tracking-wider">FTS Retrieval Latency</span>
          <span class="p-2 bg-horizon-100 text-horizon-700 rounded-xl">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </span>
        </div>
        <p class="text-3xl font-extrabold text-bordeaux-950 mt-3">8.6s</p>
        <p class="text-xs text-bordeaux-700 mt-1">99.2% speedup vs. decentralized Drive</p>
      </div>
    </div>

    <!-- Active Meetings & Recent Documents Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Active & Upcoming Meetings (2 Columns) -->
      <div class="lg:col-span-2 space-y-6">
        <div class="bg-white border border-ivory-200 rounded-3xl p-6 shadow-sm">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h3 class="font-bold text-lg text-bordeaux-950">Active & Upcoming Meetings</h3>
              <p class="text-xs text-bordeaux-700">Direct audio capture via Chrome Extension and Gemini AI MoM</p>
            </div>
            <NuxtLink to="/meetings" class="text-xs font-semibold text-horizon-700 hover:text-horizon-800">
              View All &rarr;
            </NuxtLink>
          </div>

          <div class="space-y-4">
            <!-- Sample Meeting 1 -->
            <div class="p-5 rounded-2xl bg-ivory-50 border border-ivory-200 hover:border-horizon-300 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div class="space-y-1">
                <div class="flex items-center space-x-2">
                  <span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-green-100 text-green-800">
                    In Progress
                  </span>
                  <span class="text-xs text-bordeaux-700 font-medium">Google Meet Active</span>
                </div>
                <h4 class="font-bold text-base text-bordeaux-950">Faculty Curriculum & Research Methodology Review</h4>
                <p class="text-xs text-bordeaux-700">Chaired by Dean Lay Thou • Attendees: 8 faculty members</p>
              </div>

              <div class="flex items-center space-x-2">
                <NuxtLink
                  to="/meetings/demo-meeting-01/live"
                  class="px-4 py-2 rounded-xl bg-horizon-500 hover:bg-horizon-600 text-bordeaux-950 font-bold text-xs shadow-sm flex items-center space-x-1.5 transition-all"
                >
                  <span class="h-2 w-2 rounded-full bg-bordeaux-950 animate-ping"></span>
                  <span>Join Live Console</span>
                </NuxtLink>
                <NuxtLink
                  to="/meetings/demo-meeting-01/review"
                  class="px-3.5 py-2 rounded-xl bg-ivory-200 hover:bg-ivory-300 text-bordeaux-900 font-semibold text-xs transition-all"
                >
                  Review MoM
                </NuxtLink>
              </div>
            </div>

            <!-- Sample Meeting 2 -->
            <div class="p-5 rounded-2xl bg-ivory-50 border border-ivory-200 hover:border-horizon-300 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div class="space-y-1">
                <div class="flex items-center space-x-2">
                  <span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-bordeaux-100 text-bordeaux-900">
                    Completed
                  </span>
                  <span class="text-xs text-bordeaux-700 font-medium">Verified by Secretary</span>
                </div>
                <h4 class="font-bold text-base text-bordeaux-950">AUB Academic Year 2026 Resource Allocation</h4>
                <p class="text-xs text-bordeaux-700">MoM compiled in Google Docs • 5 Action Items synced to Sheets</p>
              </div>

              <div class="flex items-center space-x-2">
                <a
                  href="https://docs.google.com"
                  target="_blank"
                  class="px-3.5 py-2 rounded-xl bg-white border border-ivory-300 hover:bg-ivory-100 text-bordeaux-900 font-semibold text-xs flex items-center space-x-1.5 transition-all"
                >
                  <span>Google Doc</span>
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              </div>
            </div>
          </div>
        </div>

        <!-- Action Items Registry Preview -->
        <div class="bg-white border border-ivory-200 rounded-3xl p-6 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="font-bold text-lg text-bordeaux-950">Recent Delegated Action Items</h3>
              <p class="text-xs text-bordeaux-700">Automated synchronization with Departmental Google Sheets</p>
            </div>
            <span class="px-2.5 py-1 rounded-md bg-horizon-100 text-horizon-800 text-xs font-semibold">
              Synced to Sheets
            </span>
          </div>

          <div class="divide-y divide-ivory-200">
            <div class="py-3 flex items-center justify-between">
              <div>
                <p class="text-sm font-semibold text-bordeaux-950">Finalize bilingual curriculum syllabus for S1-2026</p>
                <p class="text-xs text-bordeaux-700">Assignee: Dr. Seng Sam • Deadline: Nov 21, 2026</p>
              </div>
              <span class="px-2 py-1 text-xs font-bold rounded-lg bg-yellow-100 text-yellow-800">
                In Progress
              </span>
            </div>
            <div class="py-3 flex items-center justify-between">
              <div>
                <p class="text-sm font-semibold text-bordeaux-950">Deploy local GPU inference node for Omnilingual ASR</p>
                <p class="text-xs text-bordeaux-700">Assignee: IT Support Team • Deadline: Nov 18, 2026</p>
              </div>
              <span class="px-2 py-1 text-xs font-bold rounded-lg bg-green-100 text-green-800">
                Completed
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Document Access & Gemini Abstract (1 Column) -->
      <div class="space-y-6">
        <div class="bg-white border border-ivory-200 rounded-3xl p-6 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-bold text-lg text-bordeaux-950">Recent Documents</h3>
            <NuxtLink to="/documents" class="text-xs font-semibold text-horizon-700 hover:text-horizon-800">
              Upload &rarr;
            </NuxtLink>
          </div>

          <div class="space-y-4">
            <div class="p-4 rounded-2xl bg-ivory-50 border border-ivory-200 space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-[11px] font-bold px-2 py-0.5 rounded bg-bordeaux-100 text-bordeaux-900">
                  POLICY
                </span>
                <span class="text-[11px] text-bordeaux-700">v1 • PDF</span>
              </div>
              <h5 class="font-bold text-sm text-bordeaux-950">Research_Methodology_Proposal_Updated.md</h5>
              <div class="p-3 bg-white rounded-xl border border-ivory-200 text-xs text-bordeaux-800 leading-relaxed">
                <span class="font-bold text-bordeaux-950">Gemini Abstract:</span> This DSRM proposal outlines an AI workflow combining Google Gemini 1.5 Pro with localized Omnilingual ASR for Cambodian bilingual academic meeting automation.
              </div>
            </div>

            <div class="p-4 rounded-2xl bg-ivory-50 border border-ivory-200 space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-[11px] font-bold px-2 py-0.5 rounded bg-bordeaux-100 text-bordeaux-900">
                  MOM
                </span>
                <span class="text-[11px] text-bordeaux-700">v2 • DOCX</span>
              </div>
              <h5 class="font-bold text-sm text-bordeaux-950">AUB_Faculty_Meeting_Minutes_Nov2026.docx</h5>
              <div class="p-3 bg-white rounded-xl border border-ivory-200 text-xs text-bordeaux-800 leading-relaxed">
                <span class="font-bold text-bordeaux-950">Gemini Abstract:</span> Official minutes covering budget authorization, curriculum timelines, and task assignments for Group 4 research.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
