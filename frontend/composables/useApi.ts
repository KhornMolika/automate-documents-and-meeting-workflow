export function useApi() {
  const config = useRuntimeConfig()
  const token = useCookie<string | null>('aub_access_token')

  return $fetch.create({
    baseURL: config.public.apiBase,
    onRequest({ options }) {
      if (!token.value) return
      const headers = new Headers(options.headers as HeadersInit)
      headers.set('Authorization', `Bearer ${token.value}`)
      options.headers = headers
    },
    onResponseError({ response }) {
      if (response.status === 401) {
        token.value = null
        if (import.meta.client) {
          navigateTo('/login', { replace: true })
        }
      }
    },
  })
}
