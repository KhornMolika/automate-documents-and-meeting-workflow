<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Eye, EyeOff } from 'lucide-vue-next'
import { useAuth } from '~/composables/useAuth'
import { Button } from '~/components/ui/button'
import { Card } from '~/components/ui/card'
import { Input } from '~/components/ui/input'
import { Label } from '~/components/ui/label'
import { safeRedirectPath } from '~/lib/auth'

definePageMeta({ layout: false })
useHead({ title: 'Sign in · ACLEDA University' })

const route = useRoute()
const isDev = import.meta.dev
const email = ref(isDev ? 'admin@aub.edu.kh' : '')
const password = ref(isDev ? 'Admin@AUB2026' : '')
const pending = ref(false)
const error = ref('')
const copied = ref(false)
const showPassword = ref(false)
const capsLock = ref(false)
const config = useRuntimeConfig()
const { login } = useAuth()

const sessionExpired = computed(() => route.query.reason === 'session-expired')
const redirectTarget = computed(() => safeRedirectPath(route.query.redirect))

function updateCapsLock(event: KeyboardEvent) {
  capsLock.value = event.getModifierState?.('CapsLock') ?? false
}

async function copyCredentials() {
  await navigator.clipboard.writeText('admin@aub.edu.kh / Admin@AUB2026')
  copied.value = true
  window.setTimeout(() => { copied.value = false }, 1600)
}

async function submit() {
  pending.value = true
  error.value = ''
  try {
    await login(email.value, password.value)
    await navigateTo(redirectTarget.value, { replace: true })
  } catch (err: any) {
    error.value = err?.data?.detail ?? 'Unable to sign in. Check your email and password.'
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-background px-4 py-10">
    <div class="w-full max-w-[400px]">
      <div class="mb-6 flex flex-col items-center text-center">
        <img src="/aub-logo.png" alt="ACLEDA University" class="h-10 w-auto" />
        <h1 class="mt-4 text-[24px] font-semibold tracking-[-0.025em]">Sign in</h1>
        <p class="mt-1 text-sm text-muted-foreground">
          Document and meeting workspace for ACLEDA University.
        </p>
      </div>

      <div
        v-if="sessionExpired"
        class="mb-4 rounded-md border border-warning/20 bg-warning-soft px-4 py-3 text-[13px] leading-relaxed text-warning"
        role="status"
      >
        Your session expired. Sign in again to continue where you left off.
      </div>

      <Card class="p-6">
        <form class="space-y-4" @submit.prevent="submit">
          <div class="space-y-1.5">
            <Label for="email">Email</Label>
            <Input
              id="email"
              v-model="email"
              type="email"
              autocomplete="username"
              inputmode="email"
              autofocus
              required
              placeholder="name@aub.edu.kh"
              :aria-invalid="Boolean(error)"
            />
          </div>
          <div class="space-y-1.5">
            <Label for="password">Password</Label>
            <div class="relative">
              <Input
                id="password"
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="current-password"
                required
                placeholder="Your password"
                class="pr-10"
                :aria-invalid="Boolean(error)"
                @keydown="updateCapsLock"
                @keyup="updateCapsLock"
              />
              <button
                type="button"
                class="absolute right-1 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                :aria-label="showPassword ? 'Hide password' : 'Show password'"
                @click="showPassword = !showPassword"
              >
                <EyeOff v-if="showPassword" class="h-4 w-4" />
                <Eye v-else class="h-4 w-4" />
              </button>
            </div>
            <p v-if="capsLock" class="text-[12px] text-warning" role="status">Caps Lock is on.</p>
          </div>

          <p
            v-if="error"
            class="rounded-md border border-negative/20 bg-negative-soft px-3 py-2 text-[13px] text-negative"
            role="alert"
            aria-live="polite"
          >
            {{ error }}
          </p>

          <Button type="submit" class="w-full" :disabled="pending">
            <span v-if="pending" class="h-3 w-3 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
            {{ pending ? 'Signing in…' : 'Sign in' }}
          </Button>

          <p class="text-center text-[12px] text-muted-foreground">
            Accounts are created by an administrator.
          </p>
        </form>
      </Card>

      <p v-if="config.public.apiBase" class="mt-4 text-center text-[11px] text-muted-foreground">
        API: {{ config.public.apiBase }}
      </p>
      <div v-if="isDev" class="mt-3 rounded-md border bg-card px-4 py-3 text-center">
        <p class="text-[13px] font-medium">Development credentials</p>
        <p class="mt-1 text-[13px] text-muted-foreground">admin@aub.edu.kh</p>
        <p class="text-[13px] text-muted-foreground">Admin@AUB2026</p>
        <Button variant="outline" size="sm" class="mt-2" @click="copyCredentials">
          {{ copied ? 'Copied' : 'Copy credentials' }}
        </Button>
      </div>
    </div>
  </div>
</template>
