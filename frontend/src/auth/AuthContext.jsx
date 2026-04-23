import { createContext, useContext, useMemo, useState } from 'react'

const TOKEN_KEY = 'logix_token'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || '')

  function saveToken(nextToken) {
    setToken(nextToken)
    localStorage.setItem(TOKEN_KEY, nextToken)
  }

  function logout() {
    setToken('')
    localStorage.removeItem(TOKEN_KEY)
  }

  const value = useMemo(
    () => ({
      token,
      isAuthenticated: Boolean(token),
      saveToken,
      logout,
    }),
    [token],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
