/**
 * LBRO Auth Store -- JWT-based, Zustand with session-scoped persistence.
 *
 * Security:
 * - Access token kept ONLY in module-level memory (_accessTokenMemory).
 *   It is NEVER written into Zustand state (avoids the getter-override bug
 *   where Zustand persist spread converts a getter to a null data property).
 * - getAccessToken() is the single source of truth for the Axios interceptor.
 * - Refresh token persisted to sessionStorage (tab-scoped, cleared on close).
 * - Session timeout enforced client-side; JWT exp enforced server-side.
 */
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { AuthUser } from '@/types'
import { LOGIN_MAX_ATTEMPTS, LOGIN_LOCKOUT_MS, SESSION_TIMEOUT_MS } from '@/constants'

// ---- Token memory (module-level, NOT in Zustand state) ----------------------
// This avoids the Zustand persist bug: spreading state into a new object
// converts a getter to a null data property, making the interceptor blind.
let _accessTokenMemory: string | null = null
let _refreshTokenMemory: string | null = null

/** Read the current access token synchronously (for the Axios interceptor). */
export function getAccessToken(): string | null {
  return _accessTokenMemory
}

/** Read the current refresh token synchronously. */
export function getRefreshToken(): string | null {
  return _refreshTokenMemory
}

// ---- Persisted slice shape --------------------------------------------------
interface PersistedSlice {
  refreshToken: string | null
  sessionExpiresAt: number | null
  loginAttempts: number
  lockedUntil: number | null
  user: AuthUser | null
}

// ---- Store interface --------------------------------------------------------
export interface AuthStoreState {
  user: AuthUser | null
  isAuthenticated: boolean
  sessionExpiresAt: number | null
  loginAttempts: number
  lockedUntil: number | null

  login: (accessToken: string, refreshToken: string | null, user: AuthUser) => void
  logout: () => void
  setUser: (user: AuthUser) => void
  incrementLoginAttempts: () => void
  resetLoginAttempts: () => void
  isLocked: () => boolean
}

export const useAuthStore = create<AuthStoreState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      sessionExpiresAt: null,
      loginAttempts: 0,
      lockedUntil: null,

      login: (accessToken, refreshToken, user) => {
        _accessTokenMemory = accessToken
        _refreshTokenMemory = refreshToken
        set({
          isAuthenticated: true,
          user,
          sessionExpiresAt: Date.now() + SESSION_TIMEOUT_MS,
          loginAttempts: 0,
          lockedUntil: null,
        })
      },

      logout: () => {
        _accessTokenMemory = null
        _refreshTokenMemory = null
        set({
          isAuthenticated: false,
          user: null,
          sessionExpiresAt: null,
        })
      },

      setUser: (user) => set({ user }),

      incrementLoginAttempts: () => {
        const attempts = get().loginAttempts + 1
        set({
          loginAttempts: attempts,
          lockedUntil: attempts >= LOGIN_MAX_ATTEMPTS
            ? Date.now() + LOGIN_LOCKOUT_MS
            : null,
        })
      },

      resetLoginAttempts: () => set({ loginAttempts: 0, lockedUntil: null }),

      isLocked: () => {
        const { lockedUntil } = get()
        if (!lockedUntil) return false
        if (Date.now() > lockedUntil) {
          set({ lockedUntil: null, loginAttempts: 0 })
          return false
        }
        return true
      },
    }),
    {
      name: 'lbro-auth',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state): PersistedSlice => ({
        refreshToken: _refreshTokenMemory,
        sessionExpiresAt: state.sessionExpiresAt,
        loginAttempts: state.loginAttempts,
        lockedUntil: state.lockedUntil,
        user: state.user,
      }),
      onRehydrateStorage: () => (state) => {
        if (!state) return
        const s = state as unknown as PersistedSlice & AuthStoreState
        const now = Date.now()
        const { refreshToken, sessionExpiresAt, user } = s as unknown as PersistedSlice

        if (refreshToken && sessionExpiresAt && now < sessionExpiresAt) {
          // Valid session: restore refresh token to memory.
          // Access token is gone (not persisted for security); the request
          // interceptor will proactively refresh it before the first API call.
          _refreshTokenMemory = refreshToken
          // Set synchronously — NOT via setTimeout — so ProtectedRoute sees
          // isAuthenticated = true on the very first render and does not flash
          // the login page on every browser refresh.
          useAuthStore.setState({ isAuthenticated: true, user: user ?? null })
        } else if (sessionExpiresAt && now > sessionExpiresAt) {
          _accessTokenMemory = null
          _refreshTokenMemory = null
          useAuthStore.setState({
            isAuthenticated: false,
            user: null,
            sessionExpiresAt: null,
          })
        }
      },
    }
  )
)

/** Client-side session validity check. */
export function isSessionValid(): boolean {
  const { sessionExpiresAt } = useAuthStore.getState()
  return !!sessionExpiresAt && Date.now() < sessionExpiresAt
}
