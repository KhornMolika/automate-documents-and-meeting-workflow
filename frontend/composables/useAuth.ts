import type { AuthUser, LoginResponse } from '~/types/api'

export function useAuth() {
  const config = useRuntimeConfig()
  const user = useState<AuthUser | null>('auth.user', () => null)
  const token = useCookie<string | null>('aub_access_token', {
    maxAge: 60 * 60 * 8,
    sameSite: 'lax',
  })
  const api = useApi()

  async function login(email: string, password: string) {
    const body = new URLSearchParams({ username: email, password })
    const data = await $fetch<LoginResponse>('/auth/login', {
      baseURL: config.public.apiBase,
      method: 'POST',
      body,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    token.value = data.access_token
    user.value = data.user
    return data.user
  }

  async function fetchMe() {
    if (!token.value) return null
    try {
      user.value = await api<AuthUser>('/auth/me')
      return user.value
    } catch {
      token.value = null
      user.value = null
      return null
    }
  }

  async function logout() {
    token.value = null
    user.value = null
    await navigateTo('/login', { replace: true })
  }

  return { user, token, login, fetchMe, logout }
}
