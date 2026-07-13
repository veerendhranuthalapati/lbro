import { setupServer } from 'msw/node'
import { handlers } from './handlers'

// Node-environment MSW server used in Vitest.
// The browser counterpart lives in browser.ts (uses setupWorker instead).
export const server = setupServer(...handlers)
