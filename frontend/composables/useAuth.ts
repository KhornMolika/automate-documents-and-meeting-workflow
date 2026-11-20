import type { AuthUser, LoginResponse } from '~/types/api'

export function useAuth() {
  const config = useRuntimeConfig()
  const session = useSession()
  const api = useApi()

  async function login(email: string, password: string) {
    const body = new URLSearchParams({
      username: email.trim().toLowerCase(),
      password,
    })
    const data = await $fetch<LoginResponse>(`${config.public.apiBase}/auth/login`, {
      method: 'POST',
      body,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    session.setSession(data)
    return data.user
  }

  async function fetchMe() {
    if (!session.hasSession()) {
      session.user.value = null
      return null
    }
    try {
      const user = await api<AuthUser>('/auth/me')
      session.user.value = user
      return user
    } catch {
      // useApi clears the session and redirects only on a real 401.
      return null
    }
  }

  async function logout() {
    session.clearSession()
    await navigateTo('/login', { replace: true })
  }

  return {
    user: session.user,
    token: session.accessToken,
    login,
    fetchMe,
    logout,
  }
}
