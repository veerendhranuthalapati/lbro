/**
 * Integration tests for LoginPage.
 *
 * Key DOM facts (LoginPage.tsx):
 *   - Email input:    id="email", label htmlFor="email" text "Email"
 *   - Password input: id="password", label htmlFor="password" text "Password"
 *     PLUS a sibling <button aria-label="Show password"> -- getByLabelText(/password/i)
 *     matches BOTH. Use getByLabelText('Password', { selector: 'input' }) for the input.
 *   - Submit button:  text "Authenticate" (ShieldCheck icon + text node)
 *   - Error div:      id="login-error", role="alert"
 *
 * MSW valid credentials: admin@lbro.dev / password123
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { render } from './utils'
import LoginPage from '@/pages/LoginPage'
import { useAuthStore } from '@/store/authStore'
import { server } from '../mocks/server'

const getPasswordInput = () => screen.getByLabelText('Password', { selector: 'input' })
const getEmailInput    = () => screen.getByLabelText('Email',    { selector: 'input' })
const getSubmitButton  = () => screen.getByRole('button', { name: /authenticate/i })

/** No-delay handler overrides for the successful-login suite */
const fastHandlers = [
  http.post('/api/v1/auth/login', () =>
    HttpResponse.json({
      access_token:
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwMDAwMDAwMC0wMDAwLTQwMDAtYTAwMC0wMDAwMDAwMDAwMDEiLCJlbWFpbCI6ImFkbWluQGxicm8uZGV2Iiwicm9sZSI6ImFkbWluIiwicGVybWlzc2lvbnMiOltdLCJleHAiOjk5OTk5OTk5OTl9.mock',
      token_type: 'bearer',
    }),
  ),
  http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      id: '00000000-0000-4000-a000-000000000001',
      email: 'admin@lbro.dev',
      full_name: 'Arjun Mehta',
      role: 'admin',
      is_active: true,
      created_at: new Date().toISOString(),
    }),
  ),
]

beforeEach(() => {
  useAuthStore.getState().logout()
  useAuthStore.setState({ loginAttempts: 0, lockedUntil: null })
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

describe('LoginPage', () => {
  describe('rendering', () => {
    it('shows the email input', () => {
      render(<LoginPage />)
      expect(getEmailInput()).toBeInTheDocument()
    })

    it('shows the password input', () => {
      render(<LoginPage />)
      expect(getPasswordInput()).toBeInTheDocument()
    })

    it('shows the Authenticate button', () => {
      render(<LoginPage />)
      expect(getSubmitButton()).toBeInTheDocument()
    })

    it('submit button is disabled when fields are empty', () => {
      render(<LoginPage />)
      expect(getSubmitButton()).toBeDisabled()
    })

    it('shows a link to the forgot-password page', () => {
      render(<LoginPage />)
      expect(screen.getByText(/forgot password/i)).toBeInTheDocument()
    })

    it('shows a link to the register page', () => {
      render(<LoginPage />)
      expect(screen.getByText(/create one/i)).toBeInTheDocument()
    })

    it('shows/hides password via the toggle button', async () => {
      const user = userEvent.setup()
      render(<LoginPage />)
      const passwordInput = getPasswordInput()
      expect(passwordInput).toHaveAttribute('type', 'password')
      await user.click(screen.getByLabelText('Show password'))
      expect(passwordInput).toHaveAttribute('type', 'text')
      await user.click(screen.getByLabelText('Hide password'))
      expect(passwordInput).toHaveAttribute('type', 'password')
    })
  })

  describe('validation', () => {
    it('button stays disabled with only a password (no email)', async () => {
      const user = userEvent.setup()
      render(<LoginPage />)
      await user.type(getPasswordInput(), 'pass')
      expect(getSubmitButton()).toBeDisabled()
    })

    it('button stays disabled with only an email (no password)', async () => {
      const user = userEvent.setup()
      render(<LoginPage />)
      await user.type(getEmailInput(), 'admin@lbro.dev')
      expect(getSubmitButton()).toBeDisabled()
    })

    it('enables the button when both fields are filled', async () => {
      const user = userEvent.setup()
      render(<LoginPage />)
      await user.type(getEmailInput(), 'admin@lbro.dev')
      await user.type(getPasswordInput(), 'password123')
      expect(getSubmitButton()).not.toBeDisabled()
    })
  })

  describe('failed login', () => {
    it('shows an error on invalid credentials', async () => {
      const user = userEvent.setup()
      render(<LoginPage />)
      await user.type(getEmailInput(), 'wrong@example.com')
      await user.type(getPasswordInput(), 'wrongpassword')
      await user.click(getSubmitButton())
      await waitFor(() => {
        expect(screen.getByRole('alert')).toHaveTextContent(/invalid|incorrect|attempt/i)
      }, { timeout: 5000 })
    })

    it('increments the login attempt counter on failure', async () => {
      const user = userEvent.setup()
      render(<LoginPage />)
      await user.type(getEmailInput(), 'bad@bad.com')
      await user.type(getPasswordInput(), 'badpass')
      await user.click(getSubmitButton())
      await waitFor(() => {
        expect(useAuthStore.getState().loginAttempts).toBeGreaterThan(0)
      }, { timeout: 5000 })
    })
  })

  describe('loading state', () => {
    it('shows loading indicator while request is in flight', async () => {
      // Use default MSW handlers (400 ms delay) so loading state is visible
      const user = userEvent.setup()
      render(<LoginPage />)
      await user.type(getEmailInput(), 'admin@lbro.dev')
      await user.type(getPasswordInput(), 'password123')
      // Do NOT await click -- start the submit but observe mid-flight state
      user.click(getSubmitButton())
      await waitFor(() => {
        expect(screen.getByText(/authenticating/i)).toBeInTheDocument()
      }, { timeout: 2000 })
    })
  })

  describe('successful login', () => {
    beforeEach(() => { server.use(...fastHandlers) })

    it('sets isAuthenticated after successful login', async () => {
      const user = userEvent.setup()
      render(<LoginPage />)
      await user.type(getEmailInput(), 'admin@lbro.dev')
      await user.type(getPasswordInput(), 'password123')
      await user.click(getSubmitButton())
      await waitFor(() => {
        expect(useAuthStore.getState().isAuthenticated).toBe(true)
      }, { timeout: 5000 })
    })

    it('stores user email in the store after login', async () => {
      const user = userEvent.setup()
      render(<LoginPage />)
      await user.type(getEmailInput(), 'admin@lbro.dev')
      await user.type(getPasswordInput(), 'password123')
      await user.click(getSubmitButton())
      await waitFor(() => {
        expect(useAuthStore.getState().user?.email).toBe('admin@lbro.dev')
      }, { timeout: 5000 })
    })
  })

  describe('lockout', () => {
    it('shows lockout banner when store is locked', () => {
      useAuthStore.setState({ loginAttempts: 5, lockedUntil: Date.now() + 15 * 60 * 1000 })
      render(<LoginPage />)
      expect(screen.getByText(/account temporarily locked/i)).toBeInTheDocument()
    })

    it('disables submit button when locked', () => {
      useAuthStore.setState({ loginAttempts: 5, lockedUntil: Date.now() + 15 * 60 * 1000 })
      render(<LoginPage />)
      expect(getSubmitButton()).toBeDisabled()
    })
  })
})
