/**
 * MSW browser setup.
 * Import and call `startMockServiceWorker()` in main.tsx (dev-only).
 *
 * Login credentials for mock mode:
 *   Email:    any user from MOCK_USERS (e.g. admin@lbro.dev)
 *   Password: password123
 */
import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

export const worker = setupWorker(...handlers)

export async function startMockServiceWorker() {
  await worker.start({
    onUnhandledRequest: 'warn',
    serviceWorker: { url: '/mockServiceWorker.js' },
  })
  console.info(
    '%c[MSW] Mock Service Worker active — all API calls are intercepted.',
    'color: #e54e1b; font-weight: bold;',
  )
  console.info('%c[MSW] Login with any email from the seed data and password: password123', 'color: #6b6560;')
}
