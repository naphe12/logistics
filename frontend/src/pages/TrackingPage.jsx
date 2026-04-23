import { useState } from 'react'
import { checkHealth, updateShipmentStatus } from '../api/client'
import { useAuth } from '../auth/AuthContext'

const statusOptions = [
  'created',
  'ready_for_pickup',
  'picked_up',
  'in_transit',
  'arrived_at_relay',
  'delivered',
]

export default function TrackingPage() {
  const { token } = useAuth()
  const [health, setHealth] = useState('idle')
  const [error, setError] = useState('')
  const [result, setResult] = useState('')
  const [form, setForm] = useState({
    shipment_id: '',
    status: 'in_transit',
    event_type: 'shipment_in_transit',
    relay_id: '',
  })

  async function onHealth() {
    setError('')
    try {
      const res = await checkHealth()
      setHealth(res.status || 'ok')
    } catch (err) {
      setError(err.message)
    }
  }

  async function onUpdate(e) {
    e.preventDefault()
    setError('')
    setResult('')
    try {
      const payload = {
        status: form.status,
        event_type: form.event_type,
      }
      if (form.relay_id) payload.relay_id = form.relay_id

      const updated = await updateShipmentStatus(token, form.shipment_id, payload)
      setResult(updated.status || 'updated')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="page-grid two-cols">
      <article className="panel">
        <p className="eyebrow">Monitoring</p>
        <h2>Sante de l API</h2>
        <button type="button" onClick={onHealth}>
          Verifier /health
        </button>
        <p>
          Etat actuel: <strong>{health}</strong>
        </p>
      </article>

      <article className="panel">
        <p className="eyebrow">Tracking</p>
        <h2>Mise a jour de statut</h2>
        <form className="form" onSubmit={onUpdate}>
          <label>
            Shipment ID
            <input
              placeholder="UUID"
              value={form.shipment_id}
              onChange={(e) => setForm((s) => ({ ...s, shipment_id: e.target.value }))}
              required
            />
          </label>
          <label>
            Nouveau statut
            <select
              value={form.status}
              onChange={(e) => setForm((s) => ({ ...s, status: e.target.value }))}
            >
              {statusOptions.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>
          <label>
            Event type
            <input
              placeholder="shipment_in_transit"
              value={form.event_type}
              onChange={(e) => setForm((s) => ({ ...s, event_type: e.target.value }))}
              required
            />
          </label>
          <label>
            Relay ID (optionnel)
            <input
              placeholder="UUID relay"
              value={form.relay_id}
              onChange={(e) => setForm((s) => ({ ...s, relay_id: e.target.value }))}
            />
          </label>
          <button type="submit" disabled={!token}>
            Mettre a jour
          </button>
        </form>
        <p>
          Resultat: <strong>{result || '-'}</strong>
        </p>
      </article>

      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
