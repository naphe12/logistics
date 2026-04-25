import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const navByRole = {
  client: [
    { to: '/dashboard', label: 'Accueil client' },
    { to: '/shipments', label: 'Envoyer colis' },
    { to: '/shipment-schedules', label: 'Envois programmes' },
    { to: '/tracking', label: 'Suivi colis' },
    { to: '/incidents', label: 'Reclamations' },
    { to: '/payments', label: 'Paiements' },
  ],
  agent: [
    { to: '/dashboard', label: 'Espace agent' },
    { to: '/tracking', label: 'Operations terrain' },
    { to: '/transport', label: 'Trips & scans' },
    { to: '/shipments', label: 'Creation colis' },
    { to: '/shipment-schedules', label: 'Envois programmes' },
    { to: '/relays', label: 'Relais' },
    { to: '/incidents', label: 'Incidents' },
  ],
  admin: [
    { to: '/dashboard', label: 'Pilotage global' },
    { to: '/backoffice', label: 'Backoffice' },
    { to: '/shipments', label: 'Colis' },
    { to: '/shipment-schedules', label: 'Envois programmes' },
    { to: '/tracking', label: 'Tracking live' },
    { to: '/transport', label: 'Transport' },
    { to: '/relays', label: 'Reseau relais' },
    { to: '/payments', label: 'Paiements' },
    { to: '/incidents', label: 'Incidents & claims' },
    { to: '/ussd-simulator', label: 'USSD' },
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
              {item.label}
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
