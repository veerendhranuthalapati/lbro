import '@testing-library/jest-dom'
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router-dom'
import IntegrationsPage from '@/pages/IntegrationsPage'
import { render as rtlRender } from '@/test/utils'
import { server } from '@/mocks/server'
import { storeProjectApiKey, clearProjectApiKey } from '@/lib/projectApiKeys'

const PROJECT_ID = '00000000-0000-4000-a000-000000000099'

const baseProject = {
  id: PROJECT_ID,
  name: 'Demo Project',
  slug: 'demo',
  description: null,
  environment: 'development',
  status: 'active',
  owner_id: '00000000-0000-4000-a000-000000000001',
  api_key_prefix: 'proj_abcd',
  my_role: 'admin' as const,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

function renderIntegrations() {
  return rtlRender(
    <Routes>
      <Route path="/projects/:projectId/integrations" element={<IntegrationsPage />} />
    </Routes>,
    { initialEntries: [`/projects/${PROJECT_ID}/integrations`] },
  )
}

beforeEach(() => {
  clearProjectApiKey(PROJECT_ID)
  sessionStorage.clear()
})

describe('IntegrationsPage', () => {
  it('shows empty state when no project id in route', () => {
    rtlRender(<IntegrationsPage />)
    expect(screen.getByText(/no project selected/i)).toBeInTheDocument()
  })

  it('shows loading then content', async () => {
    server.use(
      http.get(`/api/v1/projects/${PROJECT_ID}`, async () => {
        await new Promise(r => setTimeout(r, 50))
        return HttpResponse.json(baseProject)
      }),
    )
    renderIntegrations()
    expect(screen.getByText(/loading integrations/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText(/project api key/i)).toBeInTheDocument()
    })
  })

  it('shows error state with retry', async () => {
    server.use(
      http.get(`/api/v1/projects/${PROJECT_ID}`, () =>
        HttpResponse.json({ detail: 'Not found' }, { status: 404 }),
      ),
    )
    renderIntegrations()
    expect(await screen.findByText(/could not load project/i, {}, { timeout: 10000 })).toBeInTheDocument()
  })

  it('masks session key until reveal', async () => {
    storeProjectApiKey(PROJECT_ID, 'proj_full_secret_key_value_12345')
    server.use(http.get(`/api/v1/projects/${PROJECT_ID}`, () => HttpResponse.json(baseProject)))
    const user = userEvent.setup()
    renderIntegrations()
    await waitFor(() => expect(screen.getByText(/project api key/i)).toBeInTheDocument())
    expect(screen.queryByText('proj_full_secret_key_value_12345')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /reveal api key/i }))
    expect(screen.getByText('proj_full_secret_key_value_12345')).toBeInTheDocument()
  })

  it('hides regenerate for viewers', async () => {
    server.use(
      http.get(`/api/v1/projects/${PROJECT_ID}`, () =>
        HttpResponse.json({ ...baseProject, my_role: 'viewer' }),
      ),
    )
    renderIntegrations()
    await waitFor(() => expect(screen.getByText(/project api key/i)).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /regenerate api key/i })).not.toBeInTheDocument()
  })

  it('shows regenerate for project admins', async () => {
    server.use(http.get(`/api/v1/projects/${PROJECT_ID}`, () => HttpResponse.json(baseProject)))
    renderIntegrations()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /regenerate api key/i })).toBeInTheDocument()
    })
  })
})
