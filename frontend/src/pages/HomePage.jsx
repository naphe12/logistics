import { useState } from 'react'
import { Link } from 'react-router-dom'
import { checkHealth } from '../api/client'
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
  const [health, setHealth] = useState('unknown')
  const [error, setError] = useState('')

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

  return (
    <section className="dashboard-home">
      <article className="hero-card">
        <div className="hero-grid">
          <div>
            <p className="eyebrow hero-eyebrow">Logistics Command</p>
            <h2>Pilotage operationnel des expeditions Burundi</h2>
            <p>
              Plateforme unifiee pour orchestrer creation, tracking et remise des colis avec un niveau
              de service type DHL / Mondial Relay adapte au terrain local.
            </p>
            <div className="hero-actions">
              <Link to="/shipments" className="button-link">
                Nouveau colis
              </Link>
              <Link to="/auth" className="button-link button-ghost">
                Connexion
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
          <p className="eyebrow">Workflow Metier</p>
          <h3>Cycle complet d un colis</h3>
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
