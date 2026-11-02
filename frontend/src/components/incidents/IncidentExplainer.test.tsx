import '@testing-library/jest-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IncidentExplainer } from '@/components/incidents/IncidentExplainer'

const mockExplain = vi.fn()
const mockGuide = vi.fn()

vi.mock('@/hooks/useApi', () => ({
  useIncidentExplanation: (id: string) => mockExplain(id),
  useIncidentAttackExplanation: (id: string, audience: string) => mockGuide(id, audience),
}))

const baseExplain = {
  plain_english: 'Analyst narrative body.',
  context: '10.0.0.1:443',
  business_impact: 'Revenue risk.',
  technical_impact: 'Credential exposure.',
  likelihood: 'Medium',
  owasp: 'A07:2021',
  mitre_attack: ['T1110'],
  recommended_fixes: ['Reset passwords'],
  learn_more_url: 'https://attack.mitre.org/techniques/T1110/',
}

const baseGuide = {
  disclaimer: 'Decision support only — verify before acting.',
  uncertainty_banner: { title: 'Provisional detection', body: 'Heuristic or low confidence.' },
  why_flagged: ['Multiple failed logins'],
  guide: {
    summary_plain: 'Executive summary text.',
    immediate_actions: ['Enable MFA'],
    prevention: { people: ['Train staff'], process: ['Lockout policy'], technology: ['WAF'] },
    references: ['https://attack.mitre.org/'],
  },
}

beforeEach(() => {
  mockExplain.mockReturnValue({ data: undefined, isLoading: false, isError: false })
  mockGuide.mockReturnValue({ data: undefined, isLoading: false })
})

describe('IncidentExplainer', () => {
  it('shows loading skeleton when open and loading', async () => {
    mockExplain.mockReturnValue({ data: undefined, isLoading: true, isError: false })
    mockGuide.mockReturnValue({ data: undefined, isLoading: true })
    const user = userEvent.setup()
    render(<IncidentExplainer incidentId="inc-1" />)
    await user.click(screen.getByRole('button', { name: /understand this attack/i }))
    expect(document.querySelectorAll('[style*="height: 12px"]').length).toBeGreaterThan(0)
  })

  it('shows error when explain fails', async () => {
    mockExplain.mockReturnValue({ data: undefined, isLoading: false, isError: true })
    const user = userEvent.setup()
    render(<IncidentExplainer incidentId="inc-1" />)
    await user.click(screen.getByRole('button', { name: /understand this attack/i }))
    expect(screen.getByText(/could not load explanation/i)).toBeInTheDocument()
  })

  it('renders disclaimer and section tabs with content', async () => {
    mockExplain.mockReturnValue({ data: baseExplain, isLoading: false, isError: false })
    mockGuide.mockReturnValue({ data: baseGuide, isLoading: false })
    const user = userEvent.setup()
    render(<IncidentExplainer incidentId="inc-1" />)
    await user.click(screen.getByRole('button', { name: /understand this attack/i }))
    expect(screen.getByText(/decision support only/i)).toBeInTheDocument()
    expect(screen.getByText(/provisional detection/i)).toBeInTheDocument()
    expect(screen.getByText('Analyst narrative body.')).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: /why we flagged it/i }))
    expect(screen.getByText('Multiple failed logins')).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: /what to do now/i }))
    expect(screen.getByText('Enable MFA')).toBeInTheDocument()
  })

  it('executive toggle switches summary on What happened', async () => {
    mockExplain.mockReturnValue({ data: baseExplain, isLoading: false, isError: false })
    mockGuide.mockReturnValue({ data: baseGuide, isLoading: false })
    const user = userEvent.setup()
    render(<IncidentExplainer incidentId="inc-1" />)
    await user.click(screen.getByRole('button', { name: /understand this attack/i }))
    await user.click(screen.getByRole('tab', { name: /^executive$/i }))
    expect(screen.getByText('Executive summary text.')).toBeInTheDocument()
    expect(screen.queryByText('Analyst narrative body.')).not.toBeInTheDocument()
  })
})
