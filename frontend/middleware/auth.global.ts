export default defineNuxtRouteMiddleware((to) => {
  const token = useCookie<string | null>('aub_access_token')

  if (to.path === '/login') {
    if (token.value) return navigateTo('/')
    return
  }

  if (!token.value) {
    return navigateTo('/login')
  }
})
