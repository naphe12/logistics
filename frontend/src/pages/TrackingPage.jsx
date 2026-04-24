import { useState } from 'react'
import { checkHealth, confirmPickupCode, updateShipmentStatus, validatePickupCode } from '../api/client'
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
  const [pickupValidation, setPickupValidation] = useState('')
  const [pickupConfirmation, setPickupConfirmation] = useState('')
  const [form, setForm] = useState({
    shipment_id: '',
    status: 'in_transit',
    event_type: 'shipment_in_transit',
    relay_id: '',
  })
  const [pickupForm, setPickupForm] = useState({
    shipment_id: '',
    code: '',
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

  async function onValidatePickupCode(e) {
    e.preventDefault()
    setError('')
    setPickupValidation('')
    setPickupConfirmation('')
    try {
      const res = await validatePickupCode(token, pickupForm.shipment_id, pickupForm.code)
      if (res.valid) {
        setPickupValidation('Code valide')
      } else {
        setPickupValidation(`${res.message}${res.error_code ? ` (${res.error_code})` : ''}`)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  async function onConfirmPickup(e) {
    e.preventDefault()
    setError('')
    setPickupConfirmation('')
    try {
      const payload = {
        code: pickupForm.code,
        event_type: 'shipment_delivered_to_receiver',
      }
      if (pickupForm.relay_id) payload.relay_id = pickupForm.relay_id
      const res = await confirmPickupCode(token, pickupForm.shipment_id, payload)
      if (res.confirmed) {
        setPickupConfirmation(`Remise confirmee. Statut: ${res.status || 'delivered'}`)
      } else {
        setPickupConfirmation(`${res.message}${res.error_code ? ` (${res.error_code})` : ''}`)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="page-grid two-cols ops-grid">
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

      <article className="panel">
        <p className="eyebrow">Retrait Agent</p>
        <h2>Validation code et remise</h2>
        <form className="form" onSubmit={onValidatePickupCode}>
          <label>
            Shipment ID
            <input
              placeholder="UUID"
              value={pickupForm.shipment_id}
              onChange={(e) => setPickupForm((s) => ({ ...s, shipment_id: e.target.value }))}
              required
            />
          </label>
          <label>
            Code retrait
            <input
              placeholder="4 chiffres"
              value={pickupForm.code}
              onChange={(e) => setPickupForm((s) => ({ ...s, code: e.target.value }))}
              minLength={4}
              maxLength={8}
              required
            />
          </label>
          <label>
            Relay ID (optionnel)
            <input
              placeholder="UUID relay"
              value={pickupForm.relay_id}
              onChange={(e) => setPickupForm((s) => ({ ...s, relay_id: e.target.value }))}
            />
          </label>
          <div className="ops-actions">
            <button type="submit" disabled={!token}>
              Verifier le code
            </button>
            <button type="button" disabled={!token} onClick={onConfirmPickup}>
              Confirmer la remise
            </button>
          </div>
        </form>
        <p>
          Validation: <strong>{pickupValidation || '-'}</strong>
        </p>
        <p>
          Confirmation: <strong>{pickupConfirmation || '-'}</strong>
        </p>
      </article>

      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
