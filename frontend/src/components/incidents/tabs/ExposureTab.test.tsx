import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ExposureTab } from '@/components/incidents/tabs/ExposureTab'

vi.mock('@/api/client', () => ({
  exposureApi: {
    get: vi.fn().mockRejectedValue(new Error('not found')),
    recompute: vi.fn(),
  },
}))

describe('ExposureTab', () => {
  it('shows empty state when assessment missing', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <ExposureTab incidentId="00000000-0000-0000-0000-000000000001" />
      </QueryClientProvider>,
    )
    expect(await screen.findByText(/No exposure assessment/i)).toBeTruthy()
  })
})
