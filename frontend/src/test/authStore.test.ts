/**
 * Unit tests for the Zustand auth store.
 * No rendering required — we drive the store directly.
 *
 * Notes:
 * - Access / refresh tokens live in module-level variables (_accessTokenMemory,
 *   _refreshTokenMemory), not inside Zustand state. We must call logout() in
 *   beforeEach to wipe them along with the Zustand slice.
 * - sessionStorage is available in jsdom; no stub needed for these pure-logic tests.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAuthStore, getAccessToken, getRefreshToken } from '@/store/authStore'
import type { AuthUser } from '@/types'
import type { Role } from '@/types/rbac'

// Stub sessionStorage so persist middleware doesn't bleed between tests
const storageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = v },
    removeItem: (k: string) => { delete store[k] },
    clear: () => { store = {} },
  }
})()
Object.defineProperty(window, 'sessionStorage', { value: storageMock, writable: true })

function makeUser(overrides?: Partial<AuthUser>): AuthUser {
  return {
    id: '00000000-0000-4000-a000-000000000001' as AuthUser['id'],
    name: 'Arjun Mehta',
    email: 'admin@lbro.dev',
    role: 'admin' as Role,
    permissions: [],
    last_login: null,
    ...overrides,
  }
}

describe('authStore', () => {
  beforeEach(() => {
    // logout() clears module-level token variables AND sets isAuthenticated=false
    useAuthStore.getState().logout()
    // Reset attempt counters not touched by logout()
    useAuthStore.setState({ loginAttempts: 0, lockedUntil: null })
    storageMock.clear()
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('starts unauthenticated', () => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false)
      expect(useAuthStore.getState().user).toBeNull()
    })

    it('getAccessToken returns null before login', () => {
      expect(getAccessToken()).toBeNull()
    })

    it('getRefreshToken returns null before login', () => {
      expect(getRefreshToken()).toBeNull()
    })
  })

  describe('login()', () => {
    it('sets isAuthenticated and user', () => {
      const user = makeUser()
      useAuthStore.getState().login('tok_access', 'tok_refresh', user)
      expect(useAuthStore.getState().isAuthenticated).toBe(true)
      expect(useAuthStore.getState().user?.email).toBe('admin@lbro.dev')
    })

    it('stores access token in module memory (getAccessToken)', () => {
      const user = makeUser()
      useAuthStore.getState().login('access_abc', 'refresh_xyz', user)
      expect(getAccessToken()).toBe('access_abc')
    })

    it('stores refresh token in module memory (getRefreshToken)', () => {
      const user = makeUser()
      useAuthStore.getState().login('a', 'refresh_xyz', user)
      expect(getRefreshToken()).toBe('refresh_xyz')
    })

    it('sets sessionExpiresAt to a future timestamp', () => {
      const before = Date.now()
      useAuthStore.getState().login('t', 'r', makeUser())
      const { sessionExpiresAt } = useAuthStore.getState()
      expect(sessionExpiresAt).not.toBeNull()
      expect(sessionExpiresAt!).toBeGreaterThan(before)
    })

    it('resets loginAttempts to 0 on login', () => {
      // Simulate some failed attempts before a successful login
      useAuthStore.setState({ loginAttempts: 3 })
      useAuthStore.getState().login('t', 'r', makeUser())
      expect(useAuthStore.getState().loginAttempts).toBe(0)
    })
  })

  describe('logout()', () => {
    it('clears isAuthenticated and user', () => {
      useAuthStore.getState().login('t', 'r', makeUser())
      useAuthStore.getState().logout()
      expect(useAuthStore.getState().isAuthenticated).toBe(false)
      expect(useAuthStore.getState().user).toBeNull()
    })

    it('clears access token from module memory', () => {
      useAuthStore.getState().login('tok', 'ref', makeUser())
      useAuthStore.getState().logout()
      expect(getAccessToken()).toBeNull()
    })

    it('clears refresh token from module memory', () => {
      useAuthStore.getState().login('tok', 'ref', makeUser())
      useAuthStore.getState().logout()
      expect(getRefreshToken()).toBeNull()
    })
  })

  describe('lockout logic', () => {
    it('isLocked() returns false initially', () => {
      expect(useAuthStore.getState().isLocked()).toBe(false)
    })

    it('is not locked after fewer than max attempts', () => {
      const store = useAuthStore.getState()
      for (let i = 0; i < 4; i++) store.incrementLoginAttempts()
      expect(useAuthStore.getState().isLocked()).toBe(false)
    })

    it('locks after reaching LOGIN_MAX_ATTEMPTS (5)', () => {
      const store = useAuthStore.getState()
      for (let i = 0; i < 5; i++) store.incrementLoginAttempts()
      expect(useAuthStore.getState().isLocked()).toBe(true)
    })

    it('sets lockedUntil to a future timestamp when locked', () => {
      const store = useAuthStore.getState()
      for (let i = 0; i < 5; i++) store.incrementLoginAttempts()
      const { lockedUntil } = useAuthStore.getState()
      expect(lockedUntil).not.toBeNull()
      expect(lockedUntil!).toBeGreaterThan(Date.now())
    })

    it('resetLoginAttempts clears attempt count and lockout', () => {
      const store = useAuthStore.getState()
      for (let i = 0; i < 5; i++) store.incrementLoginAttempts()
      expect(useAuthStore.getState().isLocked()).toBe(true)
      useAuthStore.getState().resetLoginAttempts()
      expect(useAuthStore.getState().loginAttempts).toBe(0)
      expect(useAuthStore.getState().lockedUntil).toBeNull()
      expect(useAuthStore.getState().isLocked()).toBe(false)
    })

    it('isLocked() auto-clears an expired lockout', () => {
      // Force a lockout in the past
      useAuthStore.setState({ loginAttempts: 5, lockedUntil: Date.now() - 1000 })
      // isLocked() should detect the expiry and self-clear
      expect(useAuthStore.getState().isLocked()).toBe(false)
      expect(useAuthStore.getState().lockedUntil).toBeNull()
    })
  })

  describe('setUser()', () => {
    it('updates the user without affecting auth status', () => {
      useAuthStore.getState().login('t', 'r', makeUser())
      useAuthStore.getState().setUser(makeUser({ name: 'Updated Name' }))
      expect(useAuthStore.getState().user?.name).toBe('Updated Name')
      expect(useAuthStore.getState().isAuthenticated).toBe(true)
    })
  })
})
