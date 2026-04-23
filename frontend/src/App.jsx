import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Sidebar from './components/Sidebar'
import AuthPage from './pages/AuthPage'
import HomePage from './pages/HomePage'
import ShipmentsPage from './pages/ShipmentsPage'
import TrackingPage from './pages/TrackingPage'
import './styles.css'

export default function App() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const isAuthPage = location.pathname === '/auth'

  useEffect(() => {
    function onSessionExpired() {
      navigate('/auth', { replace: true })
    }

    window.addEventListener('logix-session-expired', onSessionExpired)
    return () => window.removeEventListener('logix-session-expired', onSessionExpired)
  }, [navigate])

  return (
    <main className={isAuthPage ? 'auth-app' : 'app-shell'}>
      {isAuthPage ? null : <Sidebar />}
      <div className={isAuthPage ? 'auth-content' : 'content-area'}>
        {!isAuthPage ? (
          <header className="dashboard-topbar">
            <div>
              <p className="eyebrow">Backoffice</p>
              <h1>Logix Operations</h1>
            </div>
          </header>
        ) : null}

        <Routes>
          <Route path="/" element={<Navigate to={token ? '/dashboard' : '/auth'} replace />} />
          <Route path="/auth" element={<AuthPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <HomePage />
              </ProtectedRoute>
            }
          />
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
          <Route path="*" element={<Navigate to={token ? '/dashboard' : '/auth'} replace />} />
        </Routes>
      </div>
    </main>
  )
}
