export function useApi() {
  const config = useRuntimeConfig()
  const session = useSession()
  const redirecting = useState<boolean>('auth.redirecting', () => false)

  return $fetch.create({
    baseURL: config.public.apiBase,
    async onRequest({ options }) {
      const token = await session.ensureAccessToken()
      if (!token) return
      const headers = new Headers(options.headers as HeadersInit)
      headers.set('Authorization', `Bearer ${token}`)
      options.headers = headers
    },
    onResponseError({ response }) {
      if (response.status !== 401) return
      if (response.url.includes('/auth/login') || response.url.includes('/auth/refresh')) return

      session.clearSession()
      if (!import.meta.client || redirecting.value) return
      if (window.location.pathname === '/login') return

      redirecting.value = true
      const redirect = `${window.location.pathname}${window.location.search}`
      navigateTo(
        { path: '/login', query: { reason: 'session-expired', redirect } },
        { replace: true },
      ).finally(() => {
        redirecting.value = false
      })
    },
  })
}
