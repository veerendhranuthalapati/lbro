/**
 * LBRO Application Entry Point
 *
 * Phase 3: Session validity check on app boot
 * Phase 5: QueryClient configured for production performance
 * Phase 7: Global error handler
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppRouter } from '@/routes/AppRouter'
import { logger } from '@/lib/logger'
import { isSessionValid } from '@/store/authStore'
import { MAX_RETRIES } from '@/constants'
import '@/styles/globals.css'

// ---- Global unhandled error capture ----------------------------------------------------------------------------------------
window.addEventListener('unhandledrejection', (event) => {
  logger.error('Unhandled promise rejection', event.reason, { source: 'window.unhandledrejection' })
})

window.addEventListener('error', (event) => {
  logger.error('Uncaught error', event.error, {
    source: 'window.onerror',
    filename: event.filename,
    lineno: event.lineno,
  })
})

// ---- Session check on boot ----------------------------------------------------------------------------------------------------------
if (!isSessionValid()) {
  // Clear any stale auth state without triggering a redirect
  // The ProtectedRoute will handle the redirect
  logger.info('Session expired or not found on boot')
}

// ---- React Query client ----------------------------------------------------------------------------------------------------------------
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error: unknown) => {
        // Don't retry on 401 or 403
        const status = (error as { response?: { status?: number } })?.response?.status
        if (status === 401 || status === 403) return false
        return failureCount < MAX_RETRIES
      },
      staleTime: 10_000,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: false, // Don't retry mutations -- they may not be idempotent
    },
  },
})

// ---- Render ----------------------------------------------------------------------------------------------------------------------------------------
const root = document.getElementById('root')
if (!root) throw new Error('Root element #root not found in DOM')

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
)
