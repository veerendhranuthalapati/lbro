import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DataMapPage from '@/pages/DataMapPage'

describe('DataMapPage', () => {
  it('prompts to select a project when none active', () => {
    const qc = new QueryClient()
    render(
      <QueryClientProvider client={qc}>
        <DataMapPage />
      </QueryClientProvider>,
    )
    expect(screen.getByText(/Select a project/i)).toBeTruthy()
  })
})
