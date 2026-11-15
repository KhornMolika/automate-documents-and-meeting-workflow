<template>
  <div class="min-h-screen flex bg-ivory-50 text-bordeaux-950">
    <!-- 30% Secondary Structure: Night Bordeaux Left Sidebar -->
    <aside class="w-64 bg-bordeaux-900 text-ivory-100 flex flex-col flex-shrink-0 shadow-xl border-r border-bordeaux-950/20">
      <!-- University Branding Header -->
      <div class="p-6 border-b border-bordeaux-800/60 flex items-center space-x-3">
        <div class="h-10 w-10 rounded-xl bg-ivory-100 flex items-center justify-center shadow-md">
          <span class="text-bordeaux-900 font-extrabold text-lg">AUB</span>
        </div>
        <div>
          <h1 class="font-bold text-sm leading-tight text-white tracking-wide">ACLEDA UNIVERSITY</h1>
          <p class="text-xs text-ivory-300">Document & Meeting AI</p>
        </div>
      </div>

      <!-- Navigation Links -->
      <nav class="flex-1 px-3 py-6 space-y-1.5">
        <NuxtLink
          to="/"
          class="flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition-all group"
          :class="$route.path === '/' ? 'bg-bordeaux-950 text-white border-l-4 border-horizon-500 font-semibold shadow-inner' : 'text-ivory-200 hover:bg-bordeaux-800/50 hover:text-white'"
        >
          <svg class="w-5 h-5 transition-colors" :class="$route.path === '/' ? 'text-horizon-500' : 'text-ivory-300 group-hover:text-horizon-400'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          <span>Dashboard</span>
        </NuxtLink>

        <NuxtLink
          to="/documents"
          class="flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition-all group"
          :class="$route.path.startsWith('/documents') ? 'bg-bordeaux-950 text-white border-l-4 border-horizon-500 font-semibold shadow-inner' : 'text-ivory-200 hover:bg-bordeaux-800/50 hover:text-white'"
        >
          <svg class="w-5 h-5 transition-colors" :class="$route.path.startsWith('/documents') ? 'text-horizon-500' : 'text-ivory-300 group-hover:text-horizon-400'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>Documents</span>
        </NuxtLink>

        <NuxtLink
          to="/meetings"
          class="flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition-all group"
          :class="$route.path.startsWith('/meetings') ? 'bg-bordeaux-950 text-white border-l-4 border-horizon-500 font-semibold shadow-inner' : 'text-ivory-200 hover:bg-bordeaux-800/50 hover:text-white'"
        >
          <svg class="w-5 h-5 transition-colors" :class="$route.path.startsWith('/meetings') ? 'text-horizon-500' : 'text-ivory-300 group-hover:text-horizon-400'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <span>Meetings & MoM</span>
        </NuxtLink>
      </nav>

      <!-- Department & User Badge in Sidebar Footer -->
      <div class="p-4 bg-bordeaux-950/60 border-t border-bordeaux-800/40">
        <div class="flex items-center space-x-3">
          <div class="h-9 w-9 rounded-full bg-horizon-500/20 border border-horizon-400 text-horizon-300 font-semibold flex items-center justify-center text-xs">
            AUB
          </div>
          <div class="truncate">
            <p class="text-xs font-semibold text-white truncate">Computer Science & Eng.</p>
            <p class="text-[11px] text-ivory-300">Staff / Coordinator</p>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main Viewport (60% Dominant Canvas: Ivory Mist) -->
    <div class="flex-1 flex flex-col min-w-0 overflow-y-auto">
      <!-- Top Navbar -->
      <header class="h-16 bg-ivory-100/90 backdrop-blur-md border-b border-ivory-200 px-8 flex items-center justify-between sticky top-0 z-20">
        <div class="flex items-center space-x-3">
          <span class="text-xs font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md bg-bordeaux-100 text-bordeaux-900 border border-bordeaux-200">
            Academic Year 2024–2027
          </span>
          <span class="text-xs text-bordeaux-700">Design Science Research Platform</span>
        </div>

        <div class="flex items-center space-x-4">
          <!-- Live Audio Indicator Badge (10% Accent) -->
          <div class="flex items-center space-x-2 px-3 py-1 bg-horizon-100 border border-horizon-300 rounded-full text-xs font-medium text-bordeaux-950">
            <span class="relative flex h-2 w-2">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-horizon-500 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2 w-2 bg-horizon-600"></span>
            </span>
            <span>Gemini 1.5 Pro Active</span>
          </div>

          <!-- Chrome Ext Status -->
          <div class="text-xs font-semibold px-2.5 py-1 rounded-md bg-ivory-200 text-bordeaux-900">
            Chrome Ingress v1.0
          </div>
        </div>
      </header>

      <!-- Main Slot -->
      <main class="flex-1 p-8">
        <slot />
      </main>
    </div>
  </div>
</template>
