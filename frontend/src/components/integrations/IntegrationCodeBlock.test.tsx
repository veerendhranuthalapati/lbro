import '@testing-library/jest-dom'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CopyCodeButton, IntegrationCodeBlock } from './IntegrationCodeBlock'

describe('CopyCodeButton', () => {
  it('shows copied feedback after click', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    const user = userEvent.setup()
    render(<CopyCodeButton text="secret-value" label="Copy API key" />)
    await user.click(screen.getByRole('button', { name: /copy api key/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /copied/i })).toBeInTheDocument()
    })
  })
})

describe('IntegrationCodeBlock', () => {
  it('renders code and copy control', () => {
    render(<IntegrationCodeBlock code="print('hi')" lang="python" />)
    expect(screen.getByText(/print\('hi'\)/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /copy code/i })).toBeInTheDocument()
  })

  it('toggle wrap calls handler', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    render(
      <IntegrationCodeBlock
        code={'line-one\nline-two'}
        wrap={false}
        onToggleWrap={onToggle}
      />,
    )
    await user.click(screen.getByRole('button', { name: /^wrap$/i }))
    expect(onToggle).toHaveBeenCalled()
  })
})
