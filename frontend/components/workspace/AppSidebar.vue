<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { BookOpen, ExternalLink, FileText, LayoutDashboard, LogOut, Video } from 'lucide-vue-next'
import { Avatar, AvatarFallback } from '~/components/ui/avatar'
import { Button } from '~/components/ui/button'
import { useAuth } from '~/composables/useAuth'
import { initials } from '~/lib/format'

const emit = defineEmits<{ navigate: [] }>()
const route = useRoute()
const config = useRuntimeConfig()
const { user, logout } = useAuth()

const apiDocsUrl = computed(() => `${String(config.public.apiBase).replace(/\/api\/v1\/?$/, '')}/docs`)
const departmentName = computed(() => user.value?.department?.name ?? 'No department assigned')
const roleName = computed(() => {
  if (user.value?.roles?.length) return user.value.roles.map(role => role.role_name).join(', ')
  return user.value?.is_superuser ? 'System administrator' : 'Staff'
})
const displayName = computed(() => user.value?.full_name ?? 'Loading account…')
const avatarLabel = computed(() => initials(user.value?.full_name))

const navItems = [
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'Documents', to: '/documents', icon: FileText },
  { label: 'Meetings', to: '/meetings', icon: Video },
]

function isActive(to: string) {
  return to === '/' ? route.path === '/' : route.path.startsWith(to)
}
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex items-center gap-2.5 px-5 pb-4 pt-5">
      <img src="/aub-logo.png" alt="ACLEDA University" class="h-9 w-auto max-w-[180px] shrink-0 object-contain" />
    </div>
    <div class="px-5 pb-1">
      <p class="text-[13px] text-muted-foreground">Document & Meeting AI</p>
    </div>

    <div class="px-3 pt-4">
      <div class="rounded-md border bg-card px-3 py-2.5">
        <p class="text-[13px] text-muted-foreground">Workspace</p>
        <p class="mt-0.5 text-[13px] font-medium leading-snug">{{ departmentName }}</p>
      </div>
    </div>

    <nav class="flex-1 px-3 py-6" aria-label="Main">
      <p class="px-3 pb-2 text-[13px] text-muted-foreground">Workspace</p>
      <div class="space-y-0.5">
        <NuxtLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="group flex h-[34px] items-center gap-2.5 rounded-md px-3 text-sm transition-colors"
          :class="
            isActive(item.to)
              ? 'bg-secondary font-medium text-foreground'
              : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground'
          "
          @click="emit('navigate')"
        >
          <component :is="item.icon" class="h-4 w-4 shrink-0 text-muted-foreground" />
          <span>{{ item.label }}</span>
        </NuxtLink>
      </div>

      <p class="px-3 pb-2 pt-8 text-[13px] text-muted-foreground">Resources</p>
      <a
        :href="apiDocsUrl"
        target="_blank"
        rel="noreferrer"
        class="group flex h-[34px] items-center gap-2.5 rounded-md px-3 text-sm text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground"
      >
        <BookOpen class="h-4 w-4 shrink-0" />
        <span>API reference</span>
        <ExternalLink class="ml-auto h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
      </a>
    </nav>

    <div class="border-t p-3">
      <div class="flex items-center gap-2.5 rounded-md px-2 py-2">
        <Avatar class="h-8 w-8">
          <AvatarFallback>{{ avatarLabel }}</AvatarFallback>
        </Avatar>
        <div class="min-w-0 flex-1">
          <p class="truncate text-[13px] font-medium">{{ displayName }}</p>
          <p class="truncate text-[13px] text-muted-foreground">{{ roleName }}</p>
        </div>
        <Button variant="ghost" size="icon-sm" aria-label="Sign out" @click="logout">
          <LogOut class="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  </div>
</template>
