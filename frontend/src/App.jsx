import { useEffect } from 'react'
import { Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import AuthPage from './pages/AuthPage'
import ShipmentsPage from './pages/ShipmentsPage'
import TrackingPage from './pages/TrackingPage'
import './styles.css'

export default function App() {
  const { token, logout } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    function onSessionExpired() {
      navigate('/auth', { replace: true })
    }

    window.addEventListener('logix-session-expired', onSessionExpired)
    return () => window.removeEventListener('logix-session-expired', onSessionExpired)
  }, [navigate])

  return (
    <main className="app">
      <header className="topbar">
        <div>
          <h1>Logix Frontend</h1>
          <p>Base React + Vite branchée au backend FastAPI.</p>
        </div>
        <nav className="nav">
          <Link to="/auth">Auth</Link>
          <Link to="/shipments">Shipments</Link>
          <Link to="/tracking">Tracking</Link>
          <button onClick={logout} disabled={!token}>
            Logout
          </button>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<Navigate to={token ? '/shipments' : '/auth'} replace />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route
          path="/shipments"
          element={
            <ProtectedRoute>
              <ShipmentsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tracking"
          element={
            <ProtectedRoute>
              <TrackingPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </main>
  )
}
