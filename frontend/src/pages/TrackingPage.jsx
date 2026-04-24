import { useEffect, useMemo, useRef, useState } from 'react'
import {
  checkHealth,
  confirmPickupCode,
  getShipmentEta,
  openShipmentTrackingSocket,
  updateShipmentStatus,
  validatePickupCode,
} from '../api/client'
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
  const wsRef = useRef(null)
  const [health, setHealth] = useState('idle')
  const [error, setError] = useState('')
  const [result, setResult] = useState('')
  const [pickupValidation, setPickupValidation] = useState('')
  const [pickupConfirmation, setPickupConfirmation] = useState('')
  const [eta, setEta] = useState(null)
  const [etaShipmentId, setEtaShipmentId] = useState('')
  const [socketState, setSocketState] = useState('idle')
  const [liveShipmentId, setLiveShipmentId] = useState('')
  const [socketInput, setSocketInput] = useState('')
  const [liveEvents, setLiveEvents] = useState([])
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
  const liveHeadline = useMemo(() => {
    if (!liveShipmentId) return '-'
    return liveShipmentId
  }, [liveShipmentId])

  useEffect(() => {
    if (!token || !liveShipmentId) {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setSocketState('idle')
      return undefined
    }

    setSocketState('connecting')
    const socket = openShipmentTrackingSocket(token, liveShipmentId, {
      onOpen: () => setSocketState('connected'),
      onClose: () => setSocketState('closed'),
      onError: () => setSocketState('error'),
      onMessage: (payload) => {
        setLiveEvents((prev) => [payload, ...prev].slice(0, 30))
      },
    })
    wsRef.current = socket
    return () => {
      socket.close()
      if (wsRef.current === socket) {
        wsRef.current = null
      }
    }
  }, [token, liveShipmentId])

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
      setSocketInput((prev) => prev || form.shipment_id)
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
        setSocketInput((prev) => prev || pickupForm.shipment_id)
      } else {
        setPickupConfirmation(`${res.message}${res.error_code ? ` (${res.error_code})` : ''}`)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  function onConnectLive(e) {
    e.preventDefault()
    setError('')
    setLiveEvents([])
    setLiveShipmentId(socketInput.trim())
  }

  function onDisconnectLive() {
    setLiveShipmentId('')
    setLiveEvents([])
    setSocketState('idle')
  }

  async function onFetchEta(e) {
    e.preventDefault()
    setError('')
    setEta(null)
    try {
      const data = await getShipmentEta(token, etaShipmentId.trim())
      setEta(data)
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

      <article className="panel">
        <p className="eyebrow">Live Tracking</p>
        <h2>WebSocket colis</h2>
        <form className="form" onSubmit={onConnectLive}>
          <label>
            Shipment ID a ecouter
            <input
              placeholder="UUID"
              value={socketInput}
              onChange={(e) => setSocketInput(e.target.value)}
              required
            />
          </label>
          <div className="ops-actions">
            <button type="submit" disabled={!token}>
              Connecter
            </button>
            <button type="button" onClick={onDisconnectLive} disabled={!liveShipmentId}>
              Deconnecter
            </button>
          </div>
        </form>
        <p>
          Socket: <strong>{socketState}</strong>
        </p>
        <p>
          Shipment live: <strong>{liveHeadline}</strong>
        </p>
        <div>
          {liveEvents.length === 0 ? (
            <p>Aucun evenement live pour le moment.</p>
          ) : (
            liveEvents.map((event, index) => (
              <p key={`${event.timestamp || 'no-ts'}-${index}`}>
                [{event.timestamp || '-'}] {event.event_type || event.kind || 'event'} - {event.status || '-'}
              </p>
            ))
          )}
        </div>
      </article>

      <article className="panel">
        <p className="eyebrow">ETA</p>
        <h2>Estimation delai livraison</h2>
        <form className="form" onSubmit={onFetchEta}>
          <label>
            Shipment ID
            <input
              placeholder="UUID"
              value={etaShipmentId}
              onChange={(e) => setEtaShipmentId(e.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={!token}>
            Calculer ETA
          </button>
        </form>
        {eta ? (
          <div className="relay-item">
            <p>
              <strong>{eta.shipment_no || eta.shipment_id}</strong>
            </p>
            <p>
              status: {eta.status} | ETA: {eta.remaining_hours}h | confidence: {eta.confidence}
            </p>
            <p>
              base: {eta.base_remaining_hours ?? eta.remaining_hours}h | penalties: {eta.penalty_hours || 0}h
            </p>
            <p>estimated_delivery_at: {eta.estimated_delivery_at}</p>
            <p>model: {eta.basis}</p>
            {eta.historical_samples ? (
              <p>
                history: {eta.historical_samples} shipments | median: {eta.historical_median_hours}h
              </p>
            ) : null}
            {Array.isArray(eta.factors) && eta.factors.length > 0 ? (
              <div>
                {eta.factors.map((factor) => (
                  <p key={factor.code}>
                    risk: {factor.label} (+{factor.hours}h)
                  </p>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <p>Aucune estimation calculee.</p>
        )}
      </article>

      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
