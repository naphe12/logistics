import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const items = [
  { to: '/dashboard', label: 'Accueil' },
  { to: '/shipments', label: 'Creer colis' },
  { to: '/tracking', label: 'Operations' },
]

export default function Sidebar() {
  const { logout } = useAuth()

  return (
    <aside className="sidebar">
      <div>
        <div className="brand">
          <span className="brand-mark">L</span>
          <div>
            <p className="brand-title">Logix</p>
            <p className="brand-subtitle">Operations Console</p>
          </div>
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

      <button type="button" className="logout-btn" onClick={logout}>
        Deconnexion
      </button>
    </aside>
  )
}
