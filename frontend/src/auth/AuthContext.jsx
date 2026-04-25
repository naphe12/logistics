import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { getCurrentUser } from '../api/client'

const TOKEN_KEY = 'logix_token'
const REFRESH_TOKEN_KEY = 'logix_refresh_token'
const USER_TYPE_KEY = 'logix_user_type'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || '')
  const [refreshToken, setRefreshToken] = useState(() => localStorage.getItem(REFRESH_TOKEN_KEY) || '')
  const [userProfile, setUserProfile] = useState(null)
  const [profileLoaded, setProfileLoaded] = useState(false)

  useEffect(() => {
    function syncTokens() {
      setToken(localStorage.getItem(TOKEN_KEY) || '')
      setRefreshToken(localStorage.getItem(REFRESH_TOKEN_KEY) || '')
    }

    window.addEventListener('storage', syncTokens)
    window.addEventListener('logix-auth-updated', syncTokens)
    return () => {
      window.removeEventListener('storage', syncTokens)
      window.removeEventListener('logix-auth-updated', syncTokens)
    }
  }, [])

  function saveTokens(nextToken, nextRefreshToken = '') {
    setToken(nextToken)
    localStorage.setItem(TOKEN_KEY, nextToken)
    setRefreshToken(nextRefreshToken)
    if (nextRefreshToken) {
      localStorage.setItem(REFRESH_TOKEN_KEY, nextRefreshToken)
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY)
    }
    window.dispatchEvent(new Event('logix-auth-updated'))
  }

  function logout() {
    setToken('')
    setRefreshToken('')
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    localStorage.removeItem(USER_TYPE_KEY)
    setUserProfile(null)
    setProfileLoaded(false)
    window.dispatchEvent(new Event('logix-auth-updated'))
  }

  useEffect(() => {
    let cancelled = false

    async function loadProfile() {
      if (!token) {
        setUserProfile(null)
        setProfileLoaded(true)
        localStorage.removeItem(USER_TYPE_KEY)
        return
      }
      try {
        const profile = await getCurrentUser(token)
        if (cancelled) return
        setUserProfile(profile)
        setProfileLoaded(true)
        if (profile?.user_type) {
          localStorage.setItem(USER_TYPE_KEY, String(profile.user_type))
        }
      } catch (_err) {
        if (cancelled) return
        setUserProfile(null)
        setProfileLoaded(true)
      }
    }

    setProfileLoaded(false)
    loadProfile()
    return () => {
      cancelled = true
    }
  }, [token])

  const userType = (userProfile?.user_type || localStorage.getItem(USER_TYPE_KEY) || '').toLowerCase()
  const dashboardRole =
    userType === 'admin'
      ? 'admin'
      : ['agent', 'driver', 'hub'].includes(userType)
        ? 'agent'
        : 'client'

  const value = useMemo(
    () => ({
      token,
      refreshToken,
      isAuthenticated: Boolean(token),
      userProfile,
      userType,
      dashboardRole,
      profileLoaded,
      saveTokens,
      logout,
    }),
    [token, refreshToken, userProfile, userType, dashboardRole, profileLoaded],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
