<template>
  <div class="space-y-8 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-2xl font-extrabold text-bordeaux-950 sm:text-3xl">Meeting Intelligence & MoM Governance</h2>
        <p class="text-xs text-bordeaux-700 mt-1">
          Bilingual Khmer-English speech transcription, Gemini decision mining, and automated Google Workspace compilation.
        </p>
      </div>

      <NuxtLink
        to="/meetings/demo-meeting-01/live"
        class="px-5 py-2.5 rounded-2xl bg-horizon-500 hover:bg-horizon-600 text-bordeaux-950 font-bold text-sm shadow-md transition-all flex items-center space-x-2 self-start sm:self-auto"
      >
        <span class="h-2.5 w-2.5 rounded-full bg-bordeaux-950 animate-ping"></span>
        <span>Enter Live Meeting Console</span>
      </NuxtLink>
    </div>

    <!-- Active Sessions Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Session 1: In Progress -->
      <div class="bg-white border-2 border-horizon-300 rounded-3xl p-6 shadow-md space-y-5 relative overflow-hidden">
        <div class="absolute top-0 right-0 bg-horizon-500 text-bordeaux-950 font-extrabold text-[11px] px-3 py-1 rounded-bl-2xl uppercase tracking-wider">
          Live Ingress Active
        </div>

        <div class="space-y-2">
          <div class="flex items-center space-x-2">
            <span class="h-2 w-2 rounded-full bg-green-500 animate-pulse"></span>
            <span class="text-xs font-bold text-green-700 uppercase tracking-wider">Google Meet Connected</span>
          </div>
          <h3 class="text-xl font-extrabold text-bordeaux-950">
            Faculty Board Review: Research Methodology Proposals
          </h3>
          <p class="text-xs text-bordeaux-700 leading-relaxed">
            Chair: Dean Lay Thou • Group 4 Thesis Presentation • Department of Computer Science
          </p>
        </div>

        <!-- Agendas -->
        <div class="p-4 rounded-2xl bg-ivory-50 border border-ivory-200 space-y-2">
          <h4 class="text-xs font-bold text-bordeaux-900 uppercase tracking-wider">Scheduled Agendas</h4>
          <ol class="list-decimal list-inside text-xs text-bordeaux-800 space-y-1">
            <li>Review DSRM architectural methodology and empirical metrics</li>
            <li>Omnilingual-ASR-Khm and Netra-NMT evaluation benchmarks</li>
            <li>Google Workspace REST pipeline and action-item tracking</li>
          </ol>
        </div>

        <!-- Telemetry -->
        <div class="flex items-center justify-between text-xs text-bordeaux-700 pt-2 border-t border-ivory-200">
          <span>Captured via WXT Extension (16kHz PCM)</span>
          <span class="font-bold text-horizon-700">Latency: 1.48s (p95)</span>
        </div>

        <div class="flex items-center space-x-3 pt-2">
          <NuxtLink
            to="/meetings/demo-meeting-01/live"
            class="flex-1 py-2.5 rounded-xl bg-horizon-500 hover:bg-horizon-600 text-bordeaux-950 font-bold text-xs text-center shadow-sm transition-all"
          >
            Open Live Captions & Waveform
          </NuxtLink>
          <NuxtLink
            to="/meetings/demo-meeting-01/review"
            class="py-2.5 px-4 rounded-xl bg-ivory-200 hover:bg-ivory-300 text-bordeaux-900 font-semibold text-xs transition-all"
          >
            Review MoM Draft
          </NuxtLink>
        </div>
      </div>

      <!-- Session 2: Completed -->
      <div class="bg-white border border-ivory-200 rounded-3xl p-6 shadow-sm space-y-5">
        <div class="space-y-2">
          <div class="flex items-center space-x-2">
            <span class="px-2 py-0.5 rounded text-[11px] font-bold bg-bordeaux-100 text-bordeaux-900">
              Verified & Published
            </span>
            <span class="text-xs text-bordeaux-700">Nov 10, 2026</span>
          </div>
          <h3 class="text-xl font-extrabold text-bordeaux-950">
            AUB Departmental Budget & Infrastructure Planning
          </h3>
          <p class="text-xs text-bordeaux-700 leading-relaxed">
            Authorized by Academic Affairs Office • MoM distributed via Gmail API
          </p>
        </div>

        <div class="p-4 rounded-2xl bg-ivory-50 border border-ivory-200 space-y-2">
          <h4 class="text-xs font-bold text-bordeaux-900 uppercase tracking-wider">Executive Outcomes</h4>
          <p class="text-xs text-bordeaux-800 leading-relaxed">
            Approved allocation for on-premise NVIDIA RTX 4090 GPU node to host local speech models for data sovereignty.
          </p>
        </div>

        <div class="flex items-center justify-between text-xs text-bordeaux-700 pt-2 border-t border-ivory-200">
          <span>SUS Evaluation Score: 86.8/100</span>
          <span class="text-green-700 font-semibold">Docs & Sheets Synced</span>
        </div>

        <div class="flex items-center space-x-3 pt-2">
          <a
            href="https://docs.google.com"
            target="_blank"
            class="flex-1 py-2.5 rounded-xl bg-white border border-ivory-300 hover:bg-ivory-100 text-bordeaux-950 font-bold text-xs text-center flex items-center justify-center space-x-1 transition-all"
          >
            <span>Open Google Doc MoM</span>
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
          <NuxtLink
            to="/meetings/demo-meeting-01/review"
            class="py-2.5 px-4 rounded-xl bg-ivory-200 hover:bg-ivory-300 text-bordeaux-900 font-semibold text-xs transition-all"
          >
            Inspect Audit Trail
          </NuxtLink>
        </div>
      </div>
    </div>
  </div>
</template>
