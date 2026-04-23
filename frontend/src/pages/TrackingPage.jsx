import { useState } from 'react'
import { checkHealth, updateShipmentStatus } from '../api/client'
import { useAuth } from '../auth/AuthContext'

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
    <section className="grid-two">
      <article className="card">
        <h2>API Health</h2>
        <button onClick={onHealth}>Tester /health</button>
        <p>Etat: {health}</p>
      </article>

      <article className="card">
        <h2>Mettre à jour un statut</h2>
        <form className="form" onSubmit={onUpdate}>
          <input
            placeholder="shipment_id (UUID)"
            value={form.shipment_id}
            onChange={(e) => setForm((s) => ({ ...s, shipment_id: e.target.value }))}
            required
          />
          <select
            value={form.status}
            onChange={(e) => setForm((s) => ({ ...s, status: e.target.value }))}
          >
            <option value="in_transit">in_transit</option>
            <option value="delivered">delivered</option>
            <option value="created">created</option>
          </select>
          <input
            placeholder="event_type"
            value={form.event_type}
            onChange={(e) => setForm((s) => ({ ...s, event_type: e.target.value }))}
            required
          />
          <input
            placeholder="relay_id (optionnel)"
            value={form.relay_id}
            onChange={(e) => setForm((s) => ({ ...s, relay_id: e.target.value }))}
          />
          <button type="submit" disabled={!token}>
            Mettre à jour
          </button>
        </form>
        <p>Résultat: {result || '-'}</p>
      </article>

      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
