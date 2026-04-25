import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { listPublicRelays, publicEstimateShipment } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function HomePage() {
  const { dashboardRole, isAuthenticated } = useAuth()
  const location = useLocation()
  const isPublicLanding = location.pathname === '/' && !isAuthenticated
  const [publicRelays, setPublicRelays] = useState([])
  const [estimateError, setEstimateError] = useState('')
  const [estimateResult, setEstimateResult] = useState(null)
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

  useEffect(() => {
    if (!isPublicLanding) return
    listPublicRelays()
      .then((rows) => setPublicRelays(Array.isArray(rows) ? rows : []))
      .catch(() => setPublicRelays([]))
  }, [isPublicLanding])

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

  return (
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
        <h3>Navigation principale</h3>
        <div className="home-simple-links">
          <Link to={roleHome.actions[0].to} className="button-link">
            {roleHome.actions[0].label}
          </Link>
          <Link to={roleHome.actions[1].to} className="button-link button-ghost">
            {roleHome.actions[1].label}
          </Link>
          {dashboardRole === 'admin' ? (
            <Link to="/backoffice" className="button-link button-ghost">
              Backoffice
            </Link>
          ) : null}
        </div>
      </article>
    </section>
  )
}
