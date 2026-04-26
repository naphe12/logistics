import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const navByRole = {
  client: [
    { to: '/dashboard', label: 'Accueil client', icon: '🏠' },
    { to: '/shipments', label: 'Envoyer colis', icon: '📦' },
    { to: '/shipment-schedules', label: 'Envois programmes', icon: '🗓️' },
    { to: '/tracking', label: 'Suivi colis', icon: '🛰️' },
    { to: '/incidents', label: 'Reclamations', icon: '🛟' },
    { to: '/payments', label: 'Paiements', icon: '💳' },
  ],
  agent: [
    { to: '/dashboard', label: 'Espace agent', icon: '🏠' },
    { to: '/tracking', label: 'Operations terrain', icon: '🧭' },
    { to: '/transport', label: 'Trips & scans', icon: '🚚' },
    { to: '/shipments', label: 'Creation colis', icon: '📦' },
    { to: '/shipment-schedules', label: 'Envois programmes', icon: '🗓️' },
    { to: '/relays', label: 'Relais', icon: '🏪' },
    { to: '/incidents', label: 'Incidents', icon: '⚠️' },
  ],
  admin: [
    { to: '/dashboard', label: 'Pilotage global', icon: '🏠' },
    { to: '/backoffice', label: 'Backoffice', icon: '📊' },
    { to: '/shipments', label: 'Colis', icon: '📦' },
    { to: '/shipment-schedules', label: 'Envois programmes', icon: '🗓️' },
    { to: '/tracking', label: 'Tracking live', icon: '🛰️' },
    { to: '/transport', label: 'Transport', icon: '🚚' },
    { to: '/relays', label: 'Reseau relais', icon: '🏪' },
    { to: '/payments', label: 'Paiements', icon: '💳' },
    { to: '/incidents', label: 'Incidents & claims', icon: '⚠️' },
    { to: '/ussd-simulator', label: 'USSD', icon: '📱' },
  ],
}

const roleLabels = {
  client: 'Client',
  agent: 'Agent',
  admin: 'Admin',
}

export default function Sidebar() {
  const { logout, dashboardRole, userProfile } = useAuth()
  const navigate = useNavigate()
  const items = navByRole[dashboardRole] || navByRole.client
  const displayName = [userProfile?.first_name, userProfile?.last_name].filter(Boolean).join(' ').trim()
  const phone = userProfile?.phone_e164 || ''

  function onLogout() {
    logout()
    navigate('/', { replace: true })
  }

  return (
    <aside className="sidebar">
      <div>
        <div className="brand">
          <span className="brand-mark">L</span>
          <div>
            <p className="brand-title">Logix</p>
            <p className="brand-subtitle">Operations {roleLabels[dashboardRole] || 'Client'}</p>
          </div>
        </div>

        <div className="sidebar-role">
          <span className={`role-pill role-${dashboardRole}`}>{roleLabels[dashboardRole] || 'Client'}</span>
          {displayName ? <p className="sidebar-user">{displayName}</p> : null}
          {phone ? <p className="sidebar-phone">{phone}</p> : null}
        </div>

        <nav className="sidebar-nav">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/dashboard'}
              className={({ isActive }) => (isActive ? 'sidebar-link active' : 'sidebar-link')}
            >
              <span className="sidebar-link-inner">
                <span className="sidebar-link-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </span>
            </NavLink>
          ))}
        </nav>
      </div>

      <button type="button" className="logout-btn" onClick={onLogout}>
        Deconnexion
      </button>
    </aside>
  )
}
