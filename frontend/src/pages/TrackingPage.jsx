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

function badgeBySocketState(state) {
  if (state === 'connected') return 'success'
  if (state === 'error' || state === 'closed') return 'danger'
  if (state === 'connecting') return 'warning'
  return 'info'
}

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

  const liveHeadline = useMemo(() => liveShipmentId || '-', [liveShipmentId])

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
        setLiveEvents((prev) => [payload, ...prev].slice(0, 40))
      },
    })
    wsRef.current = socket
    return () => {
      socket.close()
      if (wsRef.current === socket) wsRef.current = null
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
      const payload = { status: form.status, event_type: form.event_type }
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
      setPickupValidation(
        res.valid
          ? 'Code valide'
          : `${res.message}${res.error_code ? ` (${res.error_code})` : ''}`,
      )
    } catch (err) {
      setError(err.message)
    }
  }

  async function onConfirmPickup() {
    setError('')
    setPickupConfirmation('')
    try {
      const payload = {
        code: pickupForm.code,
        event_type: 'shipment_delivered_to_receiver',
      }
      if (pickupForm.relay_id) payload.relay_id = pickupForm.relay_id
      const res = await confirmPickupCode(token, pickupForm.shipment_id, payload)
      setPickupConfirmation(
        res.confirmed
          ? `Remise confirmee. Statut: ${res.status || 'delivered'}`
          : `${res.message}${res.error_code ? ` (${res.error_code})` : ''}`,
      )
      if (res.confirmed) {
        setSocketInput((prev) => prev || pickupForm.shipment_id)
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
    <section className="page-grid">
      <article className="page-banner">
        <p className="eyebrow">Ops Cockpit</p>
        <h2>Tracking live, workflow statut et remise</h2>
        <p>
          Console terrain pour executer les scans metier, verifier les codes de retrait et monitorer les
          evenements temps reel.
        </p>
      </article>

      <section className="kpi-grid">
        <article className="kpi-card">
          <p>API Health</p>
          <h3>{health}</h3>
          <p className="kpi-subline">Ping service principal</p>
        </article>
        <article className="kpi-card">
          <p>Socket state</p>
          <h3>{socketState}</h3>
          <p className="kpi-subline">
            <span className={`badge ${badgeBySocketState(socketState)}`}>{socketState}</span>
          </p>
        </article>
        <article className="kpi-card">
          <p>Shipment live</p>
          <h3 className="mono">{liveHeadline}</h3>
          <p className="kpi-subline">Canal en ecoute</p>
        </article>
        <article className="kpi-card">
          <p>Events recents</p>
          <h3>{liveEvents.length}</h3>
          <p className="kpi-subline">Fenetre glissante x40</p>
        </article>
      </section>

      <section className="page-grid two-cols ops-grid">
        <article className="panel">
          <h3>Statut colis</h3>
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
              <select value={form.status} onChange={(e) => setForm((s) => ({ ...s, status: e.target.value }))}>
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
            <div className="ops-actions">
              <button type="submit" disabled={!token}>
                Mettre a jour
              </button>
              <button type="button" className="button-secondary" onClick={onHealth}>
                Verifier API
              </button>
            </div>
          </form>
          <div className="surface-soft" style={{ marginTop: 10 }}>
            <p>
              Resultat: <strong>{result || '-'}</strong>
            </p>
          </div>
        </article>

        <article className="panel">
          <h3>Remise avec code pickup</h3>
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
                Verifier
              </button>
              <button type="button" onClick={onConfirmPickup} disabled={!token}>
                Confirmer remise
              </button>
            </div>
          </form>
          <div className="stack-compact" style={{ marginTop: 10 }}>
            <div className="data-row">
              <span>Validation</span>
              <strong>{pickupValidation || '-'}</strong>
            </div>
            <div className="data-row">
              <span>Confirmation</span>
              <strong>{pickupConfirmation || '-'}</strong>
            </div>
          </div>
        </article>
      </section>

      <section className="page-grid two-cols ops-grid">
        <article className="panel">
          <h3>Flux live WebSocket</h3>
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
              <button type="button" className="button-secondary" onClick={onDisconnectLive}>
                Deconnecter
              </button>
            </div>
          </form>
          <div className="relay-list list-scroll" style={{ marginTop: 10 }}>
            {liveEvents.length === 0 ? <p>Aucun evenement live pour le moment.</p> : null}
            {liveEvents.map((event, index) => (
              <div key={`${event.timestamp || 'no-ts'}-${index}`} className="relay-item">
                <p className="mono">[{event.timestamp || '-'}]</p>
                <p>
                  <strong>{event.event_type || event.kind || 'event'}</strong>
                </p>
                <p>status: {event.status || '-'}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h3>ETA livraison</h3>
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
            <div className="stack-compact" style={{ marginTop: 10 }}>
              <div className="data-row">
                <span>Colis</span>
                <strong className="mono">{eta.shipment_no || eta.shipment_id}</strong>
              </div>
              <div className="data-row">
                <span>Status / confidence</span>
                <strong>
                  {eta.status} / {eta.confidence}
                </strong>
              </div>
              <div className="data-row">
                <span>ETA</span>
                <strong>{eta.remaining_hours}h</strong>
              </div>
              <div className="data-row">
                <span>Base + penalties</span>
                <strong>
                  {eta.base_remaining_hours ?? eta.remaining_hours}h + {eta.penalty_hours || 0}h
                </strong>
              </div>
              <div className="surface-soft">
                <p className="mono">estimated_delivery_at: {eta.estimated_delivery_at}</p>
              </div>
              {Array.isArray(eta.factors) && eta.factors.length > 0 ? (
                <div className="stack-compact">
                  {eta.factors.map((factor) => (
                    <div key={factor.code} className="data-row">
                      <span>{factor.label}</span>
                      <strong>+{factor.hours}h</strong>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <p>Aucune estimation calculee.</p>
          )}
        </article>
      </section>

      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
