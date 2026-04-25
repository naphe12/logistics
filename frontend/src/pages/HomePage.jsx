import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { checkHealth } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import logisticsHero from '../assets/logistics-hero.svg'
import logisticsNetwork from '../assets/logistics-network.svg'

const kpis = [
  { label: 'Colis en transit', value: '128' },
  { label: 'Relais actifs', value: '24' },
  { label: 'Livraisons jour', value: '73' },
]

const workflow = [
  {
    title: 'Collecte',
    text: 'Enregistrement digital rapide du colis avec numero unique et controle de conformite.',
  },
  {
    title: 'Transit inter-relais',
    text: 'Acheminement securise entre hubs et relais partenaires avec mise a jour evenementielle.',
  },
  {
    title: 'Retrait final',
    text: 'Validation OTP ou code pickup pour garantir une remise fiable au destinataire.',
  },
]

export default function HomePage() {
  const { dashboardRole, isAuthenticated } = useAuth()
  const location = useLocation()
  const [health, setHealth] = useState('unknown')
  const [error, setError] = useState('')
  const isPublicLanding = location.pathname === '/' && !isAuthenticated

  const homeByRole = {
    client: {
      eyebrow: 'Client Experience',
      title: 'Envoyer et suivre vos colis en confiance',
      description:
        'Creation rapide, assurance optionnelle, suivi temps reel et reclamations pilotees avec SLA.',
      actions: [
        { to: '/shipments', label: 'Creer un envoi' },
        { to: '/tracking', label: 'Suivre un colis' },
      ],
      priorities: ['Creation envoi', 'Suivi live', 'Reclamations assurees'],
    },
    agent: {
      eyebrow: 'Field Ops',
      title: 'Operations terrain et remise securisee',
      description:
        'Mise a jour statuts, scans de remise, verification codes et coordination transport en temps reel.',
      actions: [
        { to: '/tracking', label: 'Operations live' },
        { to: '/transport', label: 'Gestion transport' },
      ],
      priorities: ['Scan & statut', 'Livraison terrain', 'Coordination hubs'],
    },
    admin: {
      eyebrow: 'Control Tower',
      title: 'Pilotage reseau, SLA et performance',
      description:
        'Vue globale operations, alerting, performance claims, finance assurance et orchestration des equipes.',
      actions: [
        { to: '/backoffice', label: 'Ouvrir backoffice' },
        { to: '/incidents', label: 'SLA incidents/claims' },
      ],
      priorities: ['SLA & escalades', 'Fraude claims', 'Marge assurance'],
    },
  }
  const roleHome = homeByRole[dashboardRole] || homeByRole.client

  async function runHealthCheck() {
    setError('')
    try {
      const res = await checkHealth()
      setHealth(res.status || 'ok')
    } catch (err) {
      setError(err.message)
      setHealth('down')
    }
  }

  if (isPublicLanding) {
    return (
      <section className="public-home">
        <article className="public-home-banner">
          <div className="public-home-brand">
            <h1>LOGIX</h1>
            <div className="public-home-actions">
              <Link to="/auth" className="button-link">
                Connexion
              </Link>
            </div>
          </div>
        </article>
      </section>
    )
  }

  return (
    <section className="dashboard-home">
      <article className="hero-card">
        <div className="hero-grid">
          <div>
            <p className="eyebrow hero-eyebrow">{roleHome.eyebrow}</p>
            <h2>{roleHome.title}</h2>
            <p>{roleHome.description}</p>
            <div className="hero-actions">
              <Link to={roleHome.actions[0].to} className="button-link">
                {roleHome.actions[0].label}
              </Link>
              <Link to={roleHome.actions[1].to} className="button-link button-ghost">
                {roleHome.actions[1].label}
              </Link>
              <button type="button" className="button-secondary" onClick={runHealthCheck}>
                Verifier API
              </button>
            </div>
          </div>
          <img
            src={logisticsHero}
            alt="Illustration operations logistiques"
            className="hero-image"
            loading="lazy"
          />
        </div>
        <p className="status-line">
          API Health: <strong>{health}</strong>
        </p>
        {error ? <p className="error">{error}</p> : null}
      </article>

      <section className="kpi-grid">
        {kpis.map((kpi) => (
          <article className="kpi-card" key={kpi.label}>
            <p>{kpi.label}</p>
            <h3>{kpi.value}</h3>
          </article>
        ))}
      </section>

      <section className="home-row">
        <article className="panel">
          <p className="eyebrow">Priorites Role</p>
          <h3>Plan de travail {dashboardRole || 'client'}</h3>
          <div className="preset-row">
            {roleHome.priorities.map((priority) => (
              <span key={priority} className="role-focus-chip">
                {priority}
              </span>
            ))}
          </div>
          <h3 style={{ marginTop: '12px' }}>Cycle complet d un colis</h3>
          <div className="steps-grid">
            {workflow.map((step, index) => (
              <article className="step-card" key={step.title}>
                <span>{index + 1}</span>
                <h4>{step.title}</h4>
                <p>{step.text}</p>
              </article>
            ))}
          </div>
        </article>

        <article className="panel">
          <p className="eyebrow">Reseau & Couverture</p>
          <h3>Vue de la chaine logistique</h3>
          <img
            src={logisticsNetwork}
            alt="Schema reseau logistique entre relais"
            className="network-image"
            loading="lazy"
          />
          <p className="network-caption">
            Hubs, relais et livraison finale synchronises via evenements temps reel.
          </p>
        </article>
      </section>
    </section>
  )
}
