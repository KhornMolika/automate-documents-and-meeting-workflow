export const ACCESS_COOKIE = 'aub_access_token'
export const REFRESH_COOKIE = 'aub_refresh_token'

export function decodeTokenExpiry(token?: string | null): number | null {
  if (!token) return null
  const payload = token.split('.')[1]
  if (!payload) return null
  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    const data = JSON.parse(atob(padded))
    return typeof data.exp === 'number' ? data.exp * 1000 : null
  } catch {
    return null
  }
}

export function isTokenExpired(token?: string | null, skewSeconds = 0): boolean {
  const expiry = decodeTokenExpiry(token)
  if (!expiry) return true
  return expiry <= Date.now() + skewSeconds * 1000
}

export function safeRedirectPath(value: unknown, fallback = '/'): string {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) {
    return fallback
  }
  if (value.startsWith('/login')) return fallback
  return value
}
