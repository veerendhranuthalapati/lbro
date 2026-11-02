import '@testing-library/jest-dom'
import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import AttackLibraryPage from '@/pages/AttackLibraryPage'
import { render as rtlRender } from '@/test/utils'
import { server } from '@/mocks/server'

describe('AttackLibraryPage', () => {
  it('shows loading then list', async () => {
    server.use(
      http.get('/api/v1/knowledge/attacks', async () => {
        await new Promise(r => setTimeout(r, 30))
        return HttpResponse.json({
          disclaimer: 'Unreviewed content.',
          items: [{ class_id: 'ddos', title: 'DDoS', summary_plain: 'Volume flood.' }],
        })
      }),
    )
    rtlRender(<AttackLibraryPage />)
    expect(screen.getByText(/loading attack library/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('DDoS')).toBeInTheDocument())
    expect(screen.getByText(/unreviewed content/i)).toBeInTheDocument()
  })

  it('shows error with retry', async () => {
    server.use(
      http.get('/api/v1/knowledge/attacks', () =>
        HttpResponse.json({ detail: 'Not found' }, { status: 404 }),
      ),
    )
    rtlRender(<AttackLibraryPage />)
    expect(await screen.findByText(/could not load attack library/i, {}, { timeout: 10000 })).toBeInTheDocument()
  })
})
