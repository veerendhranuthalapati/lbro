/**
 * Resolve the public API origin for snippets and docs.
 * In production nginx proxies /api; snippets should use the browser origin.
 */
export function getPublicApiOrigin(): string {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin
  }
  const fromEnv = import.meta.env.VITE_API_URL
  if (typeof fromEnv === 'string' && fromEnv.startsWith('http')) {
    return fromEnv.replace(/\/api\/v1\/?$/, '').replace(/\/$/, '')
  }
  return 'https://your-lbro-instance.com'
}
