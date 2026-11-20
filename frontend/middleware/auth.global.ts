import { ACCESS_COOKIE, REFRESH_COOKIE, isTokenExpired, safeRedirectPath } from '~/lib/auth'

export default defineNuxtRouteMiddleware((to) => {
  const access = useCookie<string | null>(ACCESS_COOKIE)
  const refresh = useCookie<string | null>(REFRESH_COOKIE)
  const accessIsValid = Boolean(access.value) && !isTokenExpired(access.value, 5)
  const canRefresh = Boolean(refresh.value)

  if (to.path === '/login') {
    if (accessIsValid || canRefresh) {
      return navigateTo(safeRedirectPath(to.query.redirect))
    }
    return
  }

  if (!accessIsValid && !canRefresh) {
    return navigateTo({
      path: '/login',
      query: { redirect: to.fullPath },
    })
  }
})
