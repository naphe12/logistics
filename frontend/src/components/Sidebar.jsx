import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const navByRole = {
  client: {
    groups: [
      {
        title: 'Pilotage',
        items: [{ to: '/dashboard', label: 'Accueil client', icon: 'AC' }],
      },
      {
        title: 'Expedition',
        items: [
          { to: '/shipments', label: 'Envoyer colis', icon: 'EX' },
          { to: '/shipment-schedules', label: 'Envois programmes', icon: 'PR' },
        ],
      },
      {
        title: 'Suivi & support',
        items: [
          { to: '/tracking', label: 'Suivi colis', icon: 'SU' },
          { to: '/incidents', label: 'Reclamations', icon: 'RE' },
          { to: '/payments', label: 'Paiements', icon: 'PA' },
        ],
      },
    ],
    quickActions: [
      { to: '/shipments', label: 'Nouveau colis' },
      { to: '/tracking', label: 'Recherche tracking' },
    ],
  },
  agent: {
    groups: [
      {
        title: 'Pilotage',
        items: [{ to: '/dashboard', label: 'Espace agent', icon: 'AG' }],
      },
      {
        title: 'Operations',
        items: [
          { to: '/tracking', label: 'Operations terrain', icon: 'OP' },
          { to: '/transport', label: 'Trips & scans', icon: 'TR' },
          { to: '/transport#grouping-suggestions', label: 'Propositions systeme', icon: 'PS' },
        ],
      },
      {
        title: 'Execution',
        items: [
          { to: '/shipments', label: 'Creation colis', icon: 'CO' },
          { to: '/shipment-schedules', label: 'Envois programmes', icon: 'EP' },
          { to: '/relays', label: 'Relais', icon: 'RL' },
          { to: '/incidents', label: 'Incidents', icon: 'IN' },
        ],
      },
    ],
    quickActions: [
      { to: '/tracking', label: 'Scan rapide' },
      { to: '/transport', label: 'Nouveau trip' },
    ],
  },
  admin: {
    groups: [
      {
        title: 'Control Tower',
        items: [
          { to: '/dashboard', label: 'Pilotage global', icon: 'PG' },
          { to: '/backoffice', label: 'Backoffice', icon: 'BO' },
        ],
      },
      {
        title: 'Operations',
        items: [
          { to: '/tracking', label: 'Tracking live', icon: 'TL' },
          { to: '/transport', label: 'Transport', icon: 'TP' },
          { to: '/transport#grouping-suggestions', label: 'Propositions systeme', icon: 'PS' },
          { to: '/relays', label: 'Reseau relais', icon: 'RR' },
        ],
      },
      {
        title: 'Business',
        items: [
          { to: '/shipments', label: 'Colis', icon: 'CL' },
          { to: '/shipment-schedules', label: 'Envois programmes', icon: 'EP' },
          { to: '/payments', label: 'Paiements', icon: 'PM' },
          { to: '/incidents', label: 'Incidents & claims', icon: 'IC' },
          { to: '/ussd-simulator', label: 'USSD', icon: 'US' },
        ],
      },
    ],
    quickActions: [
      { to: '/backoffice', label: 'Vue S1 backoffice' },
      { to: '/incidents', label: 'SLA claims' },
    ],
  },
}

const roleLabels = {
  client: 'Client',
  agent: 'Agent',
  admin: 'Admin',
}

export default function Sidebar() {
  const { logout, dashboardRole, userProfile } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const navConfig = navByRole[dashboardRole] || navByRole.client
  const groups = navConfig.groups || []
  const quickActions = navConfig.quickActions || []
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

        <div className="sidebar-nav-group-list">
          {groups.map((group) => (
            <section key={group.title} className="sidebar-nav-section">
              <p className="sidebar-group-title">{group.title}</p>
              <nav className="sidebar-nav">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/dashboard'}
                    className={({ isActive }) => {
                      const [path, hash] = item.to.split('#')
                      if (hash) {
                        const activeHash = (location.hash || '').replace(/^#/, '')
                        const isHashActive = location.pathname === path && activeHash === hash
                        return isHashActive ? 'sidebar-link active' : 'sidebar-link'
                      }
                      return isActive ? 'sidebar-link active' : 'sidebar-link'
                    }}
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
            </section>
          ))}
        </div>

        <section className="sidebar-quick-actions">
          <p className="sidebar-group-title">Actions rapides</p>
          <div className="sidebar-quick-grid">
            {quickActions.map((item) => (
              <NavLink key={item.to} to={item.to} className="sidebar-quick-link">
                {item.label}
              </NavLink>
            ))}
          </div>
        </section>
      </div>

      <button type="button" className="logout-btn" onClick={onLogout}>
        Deconnexion
      </button>
    </aside>
  )
}
