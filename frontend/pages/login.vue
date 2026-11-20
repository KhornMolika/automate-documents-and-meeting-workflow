<script setup lang="ts">
import { ref } from 'vue'
import { useAuth } from '~/composables/useAuth'
import { Button } from '~/components/ui/button'
import { Card } from '~/components/ui/card'
import { Input } from '~/components/ui/input'
import { Label } from '~/components/ui/label'

definePageMeta({ layout: false })
useHead({ title: 'Sign in · ACLEDA University' })

const email = ref('admin@aub.edu.kh')
const password = ref(import.meta.dev ? 'Admin@AUB2026' : '')
const pending = ref(false)
const error = ref('')
const isDev = import.meta.dev
const copied = ref(false)
const config = useRuntimeConfig()
const { login } = useAuth()

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
    await navigateTo('/', { replace: true })
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

      <Card class="p-6">
        <form class="space-y-4" @submit.prevent="submit">
          <div class="space-y-1.5">
            <Label for="email">Email</Label>
            <Input
              id="email"
              v-model="email"
              type="email"
              autocomplete="username"
              required
              placeholder="name@aub.edu.kh"
            />
          </div>
          <div class="space-y-1.5">
            <Label for="password">Password</Label>
            <Input
              id="password"
              v-model="password"
              type="password"
              autocomplete="current-password"
              required
              placeholder="Your password"
            />
          </div>

          <p v-if="error" class="rounded-md border border-negative/20 bg-negative-soft px-3 py-2 text-[13px] text-negative">
            {{ error }}
          </p>

          <Button type="submit" class="w-full" :disabled="pending">
            {{ pending ? 'Signing in…' : 'Sign in' }}
          </Button>
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
