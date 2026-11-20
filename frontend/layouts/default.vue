<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Menu } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Sheet, SheetContent } from '~/components/ui/sheet'
import AppSidebar from '~/components/workspace/AppSidebar.vue'
import { useAuth } from '~/composables/useAuth'

const mobileOpen = ref(false)
const { user, fetchMe } = useAuth()

onMounted(() => {
  if (!user.value) fetchMe()
})
</script>

<template>
  <div class="min-h-screen bg-background text-foreground">
    <div class="flex min-h-screen">
      <aside class="hidden w-[240px] shrink-0 border-r lg:block">
        <div class="sticky top-0 h-screen">
          <AppSidebar />
        </div>
      </aside>

      <div class="flex min-w-0 flex-1 flex-col">
        <header class="sticky top-0 z-30 flex h-12 items-center gap-3 border-b bg-background px-4 lg:hidden">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Open navigation"
            @click="mobileOpen = true"
          >
            <Menu class="h-4 w-4" />
          </Button>
          <Sheet v-model:open="mobileOpen">
            <SheetContent data-testid="mobile-nav">
              <AppSidebar @navigate="mobileOpen = false" />
            </SheetContent>
          </Sheet>
          <div class="flex min-w-0 items-center gap-2">
            <img src="/aub-logo.png" alt="" class="h-6 w-6 shrink-0 object-contain" />
            <span class="truncate text-sm font-semibold">ACLEDA University</span>
          </div>
        </header>

        <main class="flex-1">
          <div class="mx-auto w-full max-w-[1280px] px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
            <slot />
          </div>
        </main>
      </div>
    </div>
  </div>
</template>
