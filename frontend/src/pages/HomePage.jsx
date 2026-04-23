import { useState } from 'react'
import { Link } from 'react-router-dom'
import { checkHealth } from '../api/client'

const kpis = [
  { label: 'Colis en transit', value: '128' },
  { label: 'Relais actifs', value: '24' },
  { label: 'Livraisons jour', value: '73' },
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
        <p className="eyebrow">Logistics Command</p>
        <h2>Pilotage operationnel des expeditions</h2>
        <p>
          Vue consolidée pour creation colis, suivi statuts, et verification rapide de la sante API.
        </p>
        <div className="hero-actions">
          <Link to="/shipments" className="button-link">
            Nouveau colis
          </Link>
          <button type="button" className="button-secondary" onClick={runHealthCheck}>
            Verifier API
          </button>
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
    </section>
  )
}
