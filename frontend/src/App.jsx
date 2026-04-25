import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Sidebar from './components/Sidebar'
import AuthPage from './pages/AuthPage'
import BackofficePage from './pages/BackofficePage'
import HomePage from './pages/HomePage'
import IncidentsPage from './pages/IncidentsPage'
import PaymentsPage from './pages/PaymentsPage'
import RelaysPage from './pages/RelaysPage'
import ShipmentsPage from './pages/ShipmentsPage'
import TrackingPage from './pages/TrackingPage'
import TransportPage from './pages/TransportPage'
import UssdSimulatorPage from './pages/UssdSimulatorPage'
import './styles.css'

export default function App() {
  const { dashboardRole, userProfile } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const isAuthPage = location.pathname === '/auth'
  const isPublicHome = location.pathname === '/'
  const hideShell = isAuthPage || isPublicHome

  const topbarByRole = {
    client: {
      eyebrow: 'Espace Client',
      title: 'Logix Customer Desk',
    },
    agent: {
      eyebrow: 'Espace Agent',
      title: 'Logix Field Operations',
    },
    admin: {
      eyebrow: 'Backoffice Admin',
      title: 'Logix Control Tower',
    },
  }
  const topbar = topbarByRole[dashboardRole] || topbarByRole.client
  const displayName = [userProfile?.first_name, userProfile?.last_name].filter(Boolean).join(' ').trim()

  useEffect(() => {
    function onSessionExpired() {
      navigate('/auth', { replace: true })
    }

    window.addEventListener('logix-session-expired', onSessionExpired)
    return () => window.removeEventListener('logix-session-expired', onSessionExpired)
  }, [navigate])

  return (
    <main className={isAuthPage ? 'auth-app' : isPublicHome ? 'public-app' : 'app-shell'}>
      {hideShell ? null : <Sidebar />}
      <div className={isAuthPage ? 'auth-content' : isPublicHome ? 'public-content' : 'content-area'}>
        {!hideShell ? (
          <header className="dashboard-topbar">
            <div className="topbar-grid">
              <div>
                <p className="eyebrow">{topbar.eyebrow}</p>
                <h1>{topbar.title}</h1>
              </div>
              <div className="topbar-user">
                <p>{displayName || 'Utilisateur connecte'}</p>
                <span>{userProfile?.phone_e164 || '-'}</span>
              </div>
            </div>
          </header>
        ) : null}

        <Routes>
          <Route path="/" element={<HomePage />} />
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
            path="/relays"
            element={
              <ProtectedRoute>
                <RelaysPage />
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
          <Route
            path="/transport"
            element={
              <ProtectedRoute>
                <TransportPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/payments"
            element={
              <ProtectedRoute>
                <PaymentsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/incidents"
            element={
              <ProtectedRoute>
                <IncidentsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/backoffice"
            element={
              <ProtectedRoute>
                <BackofficePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/ussd-simulator"
            element={
              <ProtectedRoute>
                <UssdSimulatorPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </main>
  )
}
