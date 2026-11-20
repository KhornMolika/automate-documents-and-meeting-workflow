import type { AuthUser, LoginResponse } from '~/types/api'
import { ACCESS_COOKIE, REFRESH_COOKIE, isTokenExpired } from '~/lib/auth'

let refreshInFlight: Promise<boolean> | null = null

export function useSession() {
  const config = useRuntimeConfig()
  const user = useState<AuthUser | null>('auth.user', () => null)
  const accessToken = useCookie<string | null>(ACCESS_COOKIE, {
    maxAge: 60 * 60,
    sameSite: 'lax',
    secure: !import.meta.dev,
  })
  const refreshToken = useCookie<string | null>(REFRESH_COOKIE, {
    maxAge: 60 * 60 * 24 * 7,
    sameSite: 'lax',
    secure: !import.meta.dev,
  })

  function setSession(data: LoginResponse) {
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token ?? null
    user.value = data.user
  }

  function clearSession() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
  }

  function hasSession() {
    return Boolean(accessToken.value || refreshToken.value)
  }

  function accessTokenNeedsRefresh(skewSeconds = 30) {
    return !accessToken.value || isTokenExpired(accessToken.value, skewSeconds)
  }

  async function refreshSession(): Promise<boolean> {
    if (!refreshToken.value) return false
    if (refreshInFlight) return refreshInFlight

    refreshInFlight = (async () => {
      try {
        const data = await $fetch<LoginResponse>(`${config.public.apiBase}/auth/refresh`, {
          method: 'POST',
          body: { refresh_token: refreshToken.value },
        })
        setSession(data)
        return true
      } catch {
        clearSession()
        return false
      } finally {
        refreshInFlight = null
      }
    })()

    return refreshInFlight
  }

  async function ensureAccessToken(): Promise<string | null> {
    if (accessToken.value && !accessTokenNeedsRefresh()) {
      return accessToken.value
    }
    if (refreshToken.value && await refreshSession()) {
      return accessToken.value
    }
    return accessToken.value && !accessTokenNeedsRefresh() ? accessToken.value : null
  }

  return {
    user,
    accessToken,
    refreshToken,
    hasSession,
    setSession,
    clearSession,
    refreshSession,
    ensureAccessToken,
  }
}
