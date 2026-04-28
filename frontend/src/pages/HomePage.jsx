import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { getBackofficeS1OpsKpis, listPublicRelays, publicEstimateShipment } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function HomePage() {
  const { dashboardRole, isAuthenticated, token, userType } = useAuth()
  const location = useLocation()
  const isPublicLanding = location.pathname === '/' && !isAuthenticated
  const [publicRelays, setPublicRelays] = useState([])
  const [estimateError, setEstimateError] = useState('')
  const [estimateResult, setEstimateResult] = useState(null)
  const [s1Kpis, setS1Kpis] = useState(null)
  const [estimateForm, setEstimateForm] = useState({
    origin_relay_id: '',
    destination_relay_id: '',
    declared_value: '',
    insurance_opt_in: false,
  })

  const homeByRole = {
    client: {
      eyebrow: 'Client Experience',
      title: "Connecter vos envois a tout le pays",
      description:
        "Envoyez, suivez et gerez vos colis en toute transparence avec une experience moderne inspiree des meilleurs standards digitaux.",
      actions: [
        { to: '/shipments', label: 'Creer un envoi' },
        { to: '/tracking', label: 'Suivre un colis' },
      ],
    },
    agent: {
      eyebrow: 'Field Ops',
      title: 'Piloter chaque livraison avec precision',
      description:
        "Centralisez vos operations terrain, fluidifiez la remise et gardez une visibilite totale sur chaque etape.",
      actions: [
        { to: '/tracking', label: 'Operations live' },
        { to: '/transport', label: 'Gestion transport' },
      ],
    },
    admin: {
      eyebrow: 'Control Tower',
      title: 'Orchestrer le reseau logistique en confiance',
      description:
        "Supervisez votre reseau, votre qualite de service et vos equipes depuis une interface claire, rapide et orientee impact.",
      actions: [
        { to: '/backoffice', label: 'Ouvrir backoffice' },
        { to: '/incidents', label: 'SLA incidents/claims' },
      ],
    },
  }
  const roleHome = homeByRole[dashboardRole] || homeByRole.client
  const quickActionGroupsByRole = {
    client: [
      {
        title: 'Expedition',
        actions: [
          { to: '/shipments', label: 'Nouveau colis' },
          { to: '/shipment-schedules', label: 'Programmer un envoi' },
        ],
      },
      {
        title: 'Suivi',
        actions: [
          { to: '/tracking', label: 'Suivre mes colis' },
          { to: '/incidents', label: 'Creer reclamation' },
        ],
      },
      {
        title: 'Paiement',
        actions: [{ to: '/payments', label: 'Voir paiements' }],
      },
    ],
    agent: [
      {
        title: 'Operations live',
        actions: [
          { to: '/tracking', label: 'Operations terrain' },
          { to: '/transport', label: 'Trips & scans' },
        ],
      },
      {
        title: 'Execution',
        actions: [
          { to: '/shipments', label: 'Creation colis' },
          { to: '/shipment-schedules', label: 'Envois programmes' },
        ],
      },
      {
        title: 'Support',
        actions: [
          { to: '/relays', label: 'Reseau relais' },
          { to: '/incidents', label: 'Incidents' },
        ],
      },
    ],
    admin: [
      {
        title: 'Control Tower',
        actions: [
          { to: '/backoffice', label: 'Backoffice S1' },
          { to: '/dashboard', label: 'Vue globale' },
        ],
      },
      {
        title: 'Operations',
        actions: [
          { to: '/tracking', label: 'Tracking live' },
          { to: '/transport', label: 'Transport' },
          { to: '/relays', label: 'Reseau relais' },
        ],
      },
      {
        title: 'Business',
        actions: [
          { to: '/shipments', label: 'Colis' },
          { to: '/payments', label: 'Paiements' },
          { to: '/incidents', label: 'Incidents & claims' },
        ],
      },
    ],
  }
  const quickActionGroups = quickActionGroupsByRole[dashboardRole] || quickActionGroupsByRole.client

  function pct(value) {
    if (typeof value !== 'number' || Number.isNaN(value)) return '--'
    return `${value.toFixed(2)}%`
  }

  const kpis = [
    {
      label: 'On-time Rate',
      value: pct(s1Kpis?.on_time_rate),
      delta: 'S1',
      tone: 'up',
      icon: '⏱️',
    },
    {
      label: 'Incident Rate',
      value: pct(s1Kpis?.incident_rate),
      delta: 'S1',
      tone: 'down',
      icon: '🚨',
    },
    {
      label: 'Scan Compliance',
      value: pct(s1Kpis?.scan_compliance),
      delta: 'S1',
      tone: 'up',
      icon: '✅',
    },
    {
      label: 'Shipments (window)',
      value: typeof s1Kpis?.shipments_created === 'number' ? String(s1Kpis.shipments_created) : '--',
      delta: `${s1Kpis?.window_hours || 168}h`,
      tone: 'up',
      icon: '📦',
    },
    {
      label: 'Incidents (window)',
      value: typeof s1Kpis?.incident_count === 'number' ? String(s1Kpis.incident_count) : '--',
      delta: `${s1Kpis?.window_hours || 168}h`,
      tone: 'down',
      icon: '🧯',
    },
  ]
  const monthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const monthlyTime = [320, 410, 360, 540, 430, 610, 470, 630, 500, 300, 700, 580]
  const monthlyRoute = [280, 340, 290, 320, 520, 410, 550, 470, 560, 530, 460, 490]
  const lineByCountry = [
    { name: 'Burundi', values: [110, 90, 130, 124, 118, 140, 126, 134, 129, 120, 112, 127], color: '#28a36a' },
    { name: 'Rwanda', values: [130, 101, 142, 139, 126, 131, 137, 128, 133, 141, 119, 149], color: '#2b70c9' },
    { name: 'Tanzania', values: [123, 115, 136, 147, 143, 132, 139, 135, 127, 138, 124, 146], color: '#d49a23' },
    { name: 'Kenya', values: [116, 88, 129, 121, 108, 125, 111, 126, 130, 142, 118, 151], color: '#2f3d8d' },
  ]
  const chartMax = Math.max(...monthlyTime, ...monthlyRoute, 1)
  const lineMax = Math.max(...lineByCountry.flatMap((s) => s.values), 1)
  const timePoints = monthlyTime
    .map((v, i) => {
      const x = (i / (monthlyTime.length - 1)) * 100
      const y = 100 - (v / chartMax) * 100
      return `${x},${y}`
    })
    .join(' ')
  const routePoints = monthlyRoute
    .map((v, i) => {
      const x = (i / (monthlyRoute.length - 1)) * 100
      const y = 100 - (v / chartMax) * 100
      return `${x},${y}`
    })
    .join(' ')
  const countryPoints = lineByCountry.map((series) =>
    series.values
      .map((v, i) => {
        const x = (i / (series.values.length - 1)) * 100
        const y = 100 - (v / lineMax) * 100
        return `${x},${y}`
      })
      .join(' ')
  )
  const ongoingDeliveries = [
    {
      shipmentNo: '#001234ABCD',
      from: '87 Wern Du Lane',
      to: '15 Vicar Lane',
      status: 'On the way',
      eta: '15 min',
      active: true,
    },
    {
      shipmentNo: '#001234ABCE',
      from: '40 Broomfield Place',
      to: '44 Helland Bridge',
      status: 'Checkpoint',
      eta: '32 min',
      active: false,
    },
    {
      shipmentNo: '#001234ABCF',
      from: '19 Norfield Town',
      to: '8 Newmarket Street',
      status: 'Preparing',
      eta: '54 min',
      active: false,
    },
  ]
  const trackingRows = [
    { id: 'TRK-1092', category: 'Electronic', distance: '60.41 km', eta: '1h 20m' },
    { id: 'TRK-1093', category: 'Fashion', distance: '22.04 km', eta: '45m' },
    { id: 'TRK-1094', category: 'Retail', distance: '11.16 km', eta: '19m' },
  ]

  useEffect(() => {
    if (!isPublicLanding) return
    listPublicRelays()
      .then((rows) => setPublicRelays(Array.isArray(rows) ? rows : []))
      .catch(() => setPublicRelays([]))
  }, [isPublicLanding])

  useEffect(() => {
    if (location.pathname !== '/dashboard') return
    if (!token) return
    const isOpsAdmin = userType === 'admin' || userType === 'hub'
    if (!isOpsAdmin) {
      setS1Kpis(null)
      return
    }

    getBackofficeS1OpsKpis(token, 168)
      .then((rows) => setS1Kpis(rows || null))
      .catch(() => setS1Kpis(null))
  }, [location.pathname, token, userType])

  async function onEstimateSubmit(e) {
    e.preventDefault()
    setEstimateError('')
    try {
      const res = await publicEstimateShipment({
        originRelayId: estimateForm.origin_relay_id,
        destinationRelayId: estimateForm.destination_relay_id,
        declaredValue: estimateForm.declared_value === '' ? null : Number(estimateForm.declared_value),
        insuranceOptIn: estimateForm.insurance_opt_in,
      })
      setEstimateResult(res)
    } catch (err) {
      setEstimateError(err.message)
      setEstimateResult(null)
    }
  }

  if (isPublicLanding) {
    return (
      <section className="public-home">
        <article className="home-spotlight">
          <div className="home-logo-row">
            <img src="/favicon.svg" alt="Logix" className="home-logo spin-slow" />
            <h1 className="home-title">LOGIX</h1>
          </div>
          <p className="home-subtitle">
            Rapprochez vos proches, vos clients et vos operations avec une logistique fiable, simple et
            humaine.
          </p>
          <div className="home-cta-row">
            <Link to="/register" className="button-link">
              Creer un compte
            </Link>
            <Link to="/track" className="button-link button-ghost">
              Suivre un colis
            </Link>
            <Link to="/auth" className="button-link button-ghost">
              Connexion
            </Link>
          </div>

          <div className="panel" style={{ marginTop: 16, textAlign: 'left' }}>
            <p className="eyebrow">Simulateur DHL-style</p>
            <h3>Estimation prix avant inscription</h3>
            <form className="form" onSubmit={onEstimateSubmit}>
              <label>
                Relais origine
                <select
                  value={estimateForm.origin_relay_id}
                  onChange={(e) => setEstimateForm((s) => ({ ...s, origin_relay_id: e.target.value }))}
                  required
                >
                  <option value="">Selectionner</option>
                  {publicRelays.map((relay) => (
                    <option key={relay.id} value={relay.id}>
                      {relay.name} ({relay.relay_code})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Relais destination
                <select
                  value={estimateForm.destination_relay_id}
                  onChange={(e) => setEstimateForm((s) => ({ ...s, destination_relay_id: e.target.value }))}
                  required
                >
                  <option value="">Selectionner</option>
                  {publicRelays.map((relay) => (
                    <option key={relay.id} value={relay.id}>
                      {relay.name} ({relay.relay_code})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Valeur declaree (BIF)
                <input
                  type="number"
                  min="0"
                  value={estimateForm.declared_value}
                  onChange={(e) => setEstimateForm((s) => ({ ...s, declared_value: e.target.value }))}
                  placeholder="100000"
                />
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={estimateForm.insurance_opt_in}
                  onChange={(e) => setEstimateForm((s) => ({ ...s, insurance_opt_in: e.target.checked }))}
                />
                Inclure assurance
              </label>
              <button type="submit">Estimer maintenant</button>
            </form>
            {estimateResult ? (
              <div className="data-row" style={{ marginTop: 10 }}>
                <span>Total estime</span>
                <strong>{estimateResult.total_estimated_bif} BIF</strong>
              </div>
            ) : null}
            {estimateError ? <p className="error">{estimateError}</p> : null}
          </div>
        </article>
      </section>
    )
  }

  return location.pathname === '/dashboard' ? (
    <section className="pro-dashboard">
      <article className="pro-head">
        <div>
          <p className="eyebrow">Operations Dashboard</p>
          <h2>Control Tower</h2>
        </div>
        <div className="pro-switch">
          <button type="button" className="active">
            Overview
          </button>
          <button type="button">Tracking</button>
        </div>
      </article>

      <section className="pro-kpis">
        {kpis.map((kpi) => (
          <article key={kpi.label} className="pro-kpi">
            <p className="pro-kpi-label">
              <span>{kpi.label}</span>
              <span className="pro-kpi-icon" aria-hidden="true">
                {kpi.icon}
              </span>
            </p>
            <h3>{kpi.value}</h3>
            <span className={kpi.tone === 'up' ? 'delta up' : 'delta down'}>Than last month {kpi.delta}</span>
          </article>
        ))}
      </section>

      <section className="pro-analytics-grid">
        <article className="pro-chart-card">
          <header>
            <h3>Avg Delivery Time (hours) & Route (km)</h3>
            <div className="legend-inline">
              <span className="legend-dot legend-time">Time</span>
              <span className="legend-dot legend-route">Route</span>
            </div>
          </header>
          <div className="multi-line-chart dual-line-chart">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <polyline className="time-line" points={timePoints} />
              <polyline className="route-line" points={routePoints} />
            </svg>
            <div className="month-strip">
              {monthLabels.map((m) => (
                <small key={m}>{m}</small>
              ))}
            </div>
          </div>
        </article>

        <article className="pro-fleet-card">
          <h3>Fleet Status</h3>
          <div className="fleet-gauge-wrap">
            <div className="fleet-gauge">
              <span>96.6%</span>
            </div>
          </div>
          <p className="fleet-caption">Fleet Efficiency</p>
          <div className="fleet-stats">
            <div className="fleet-row">
              <span>Total Fleet</span>
              <strong>64</strong>
            </div>
            <div className="fleet-row">
              <span>On the Move</span>
              <strong>62</strong>
            </div>
            <div className="fleet-row">
              <span>In Maintenance</span>
              <strong>4</strong>
            </div>
          </div>
        </article>
      </section>

      <section className="pro-analytics-grid">
        <article className="pro-chart-card">
          <header>
            <h3>Avg Delivery Time (hours) & Route (km)</h3>
            <div className="legend-inline legend-wide">
              {lineByCountry.map((series) => (
                <span key={series.name} className="legend-dot" style={{ '--dot': series.color }}>
                  {series.name}
                </span>
              ))}
            </div>
          </header>
          <div className="multi-line-chart">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              {countryPoints.map((points, idx) => (
                <polyline key={lineByCountry[idx].name} points={points} style={{ '--line': lineByCountry[idx].color }} />
              ))}
            </svg>
            <div className="month-strip">
              {monthLabels.map((m) => (
                <small key={m}>{m}</small>
              ))}
            </div>
          </div>
        </article>

        <aside className="pro-side-metrics">
          <article className="side-metric">
            <div className="metric-icon clock" />
            <div>
              <strong>25 Min</strong>
              <p>Avg Loading Time</p>
            </div>
          </article>
          <article className="side-metric">
            <div className="metric-icon weight" />
            <div>
              <strong>10 tons</strong>
              <p>Avg Loading Weight</p>
            </div>
          </article>
        </aside>
      </section>

      <section className="pro-main-grid">
        <article className="pro-ongoing">
          <header>
            <h3>Ongoing delivery</h3>
            <button type="button" className="button-secondary">
              Filter
            </button>
          </header>
          <div className="pro-ongoing-list">
            {ongoingDeliveries.map((item) => (
              <div key={item.shipmentNo} className={item.active ? 'delivery-card active' : 'delivery-card'}>
                <div>
                  <p className="mono">{item.shipmentNo}</p>
                  <small>
                    {item.from} to {item.to}
                  </small>
                </div>
                <div className="delivery-meta">
                  <span className="badge info">{item.status}</span>
                  <strong>{item.eta}</strong>
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="pro-route">
          <h3>On the way</h3>
          <div className="route-canvas">
            <span className="dot a" />
            <span className="dot b" />
            <span className="dot c" />
            <svg viewBox="0 0 260 160" aria-hidden="true">
              <polyline points="24,120 92,48 144,98 232,38" />
            </svg>
          </div>
          <div className="route-stats">
            <div>
              <p>Category</p>
              <strong>Electronic</strong>
            </div>
            <div>
              <p>Distance</p>
              <strong>60.41 km</strong>
            </div>
            <div>
              <p>ETA</p>
              <strong>1h 20m</strong>
            </div>
          </div>
        </article>
      </section>

      <article className="pro-tracking">
        <header>
          <h3>Tracking Order</h3>
          <input placeholder="Search tracking id..." />
        </header>
        <div className="pro-table">
          {trackingRows.map((row) => (
            <div key={row.id} className="pro-row">
              <span className="mono">{row.id}</span>
              <span>{row.category}</span>
              <span>{row.distance}</span>
              <span>{row.eta}</span>
            </div>
          ))}
        </div>
      </article>
    </section>
  ) : (
    <section className="dashboard-home">
      <article className="home-spotlight">
        <div className="home-logo-row">
          <img src="/favicon.svg" alt="Logix" className="home-logo spin-slow" />
          <h1 className="home-title">LOGIX</h1>
        </div>
        <p className="eyebrow hero-eyebrow">{roleHome.eyebrow}</p>
        <h2>{roleHome.title}</h2>
        <p className="home-subtitle">{roleHome.description}</p>
        <div className="home-cta-row">
          <Link to={roleHome.actions[0].to} className="button-link">
            {roleHome.actions[0].label}
          </Link>
          <Link to={roleHome.actions[1].to} className="button-link button-ghost">
            {roleHome.actions[1].label}
          </Link>
        </div>
      </article>

      <article className="panel home-simple-card">
        <p className="eyebrow">Acces Rapide</p>
        <h3>Menus et actions rapides</h3>
        <div className="quick-groups-grid">
          {quickActionGroups.map((group) => (
            <section key={group.title} className="quick-group-card">
              <p className="quick-group-title">{group.title}</p>
              <div className="home-simple-links">
                {group.actions.map((action) => (
                  <Link key={action.to} to={action.to} className="button-link button-ghost">
                    {action.label}
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      </article>
    </section>
  )
}
