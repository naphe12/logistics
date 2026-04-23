import { createContext, useContext, useEffect, useMemo, useState } from 'react'

const TOKEN_KEY = 'logix_token'
const REFRESH_TOKEN_KEY = 'logix_refresh_token'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || '')
  const [refreshToken, setRefreshToken] = useState(() => localStorage.getItem(REFRESH_TOKEN_KEY) || '')

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
    window.dispatchEvent(new Event('logix-auth-updated'))
  }

  const value = useMemo(
    () => ({
      token,
      refreshToken,
      isAuthenticated: Boolean(token),
      saveTokens,
      logout,
    }),
    [token, refreshToken],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
