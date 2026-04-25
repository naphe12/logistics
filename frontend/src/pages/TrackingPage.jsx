import { useEffect, useMemo, useRef, useState } from 'react'
import {
  checkHealth,
  confirmPickupCode,
  createShipmentDeliveryProof,
  getShipmentEta,
  getRelayPickupForecast,
  getShipmentTimeline,
  getShipmentTrackingSummary,
  listShipments,
  openShipmentTrackingSocket,
  updateShipmentPickupSlot,
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

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function formatDateTime(value) {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return String(value)
  return dt.toLocaleString()
}

export default function TrackingPage() {
  const { token, dashboardRole } = useAuth()
  const wsRef = useRef(null)
  const isOpsRole = dashboardRole === 'agent' || dashboardRole === 'admin'
  const isClientRole = dashboardRole === 'client'

  const [health, setHealth] = useState('idle')
  const [error, setError] = useState('')
  const [result, setResult] = useState('')
  const [lookupInput, setLookupInput] = useState('')
  const [lookupMatches, setLookupMatches] = useState([])
  const [trackingSummary, setTrackingSummary] = useState(null)
  const [trackingTimeline, setTrackingTimeline] = useState([])
  const [trackingLoading, setTrackingLoading] = useState(false)
  const [trackedShipment, setTrackedShipment] = useState(null)
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
  const [pickupSlotForm, setPickupSlotForm] = useState({
    shipment_id: '',
    starts_at: '',
    ends_at: '',
    note: '',
  })
  const [pickupSlotResult, setPickupSlotResult] = useState('')
  const [proofForm, setProofForm] = useState({
    shipment_id: '',
    receiver_name: '',
    signature: '',
    geo_lat: '',
    geo_lng: '',
  })
  const [proofResult, setProofResult] = useState('')
  const [forecastRelayId, setForecastRelayId] = useState('')
  const [forecastHours, setForecastHours] = useState(24)
  const [pickupForecast, setPickupForecast] = useState([])

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

  async function loadTrackingDetails(shipmentId) {
    setTrackingLoading(true)
    try {
      const [summary, timeline, etaData] = await Promise.all([
        getShipmentTrackingSummary(token, shipmentId),
        getShipmentTimeline(token, shipmentId),
        getShipmentEta(token, shipmentId),
      ])
      setTrackingSummary(summary || null)
      setTrackingTimeline(Array.isArray(timeline) ? timeline : [])
      setEta(etaData || null)
      setEtaShipmentId(shipmentId)
      setSocketInput((prev) => prev || shipmentId)
    } finally {
      setTrackingLoading(false)
    }
  }

  async function onLookupShipment(e) {
    e.preventDefault()
    setError('')
    setLookupMatches([])
    setTrackingSummary(null)
    setTrackingTimeline([])
    setTrackedShipment(null)

    const query = lookupInput.trim()
    if (!query) return

    try {
      if (UUID_RE.test(query)) {
        setTrackedShipment({ id: query, shipment_no: query, status: '-' })
        await loadTrackingDetails(query)
        return
      }

      const matches = await listShipments(token, {
        shipment_no: query,
        limit: 5,
        sort: 'created_at_desc',
      })
      const rows = Array.isArray(matches) ? matches : []
      if (rows.length === 0) {
        setError('Aucun colis trouve pour ce numero.')
        return
      }

      setLookupMatches(rows)
      setTrackedShipment(rows[0])
      await loadTrackingDetails(rows[0].id)
    } catch (err) {
      setError(err.message)
    }
  }

  async function onSelectMatch(shipment) {
    setError('')
    setTrackedShipment(shipment)
    try {
      await loadTrackingDetails(shipment.id)
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

  async function onSavePickupSlot(e) {
    e.preventDefault()
    setError('')
    setPickupSlotResult('')
    try {
      const res = await updateShipmentPickupSlot(token, pickupSlotForm.shipment_id.trim(), {
        starts_at: pickupSlotForm.starts_at,
        ends_at: pickupSlotForm.ends_at,
        note: pickupSlotForm.note || null,
      })
      setPickupSlotResult(`Creneau enregistre pour ${res.shipment_no}`)
    } catch (err) {
      setError(err.message)
    }
  }

  async function onCaptureDeliveryProof(e) {
    e.preventDefault()
    setError('')
    setProofResult('')
    try {
      const res = await createShipmentDeliveryProof(token, proofForm.shipment_id.trim(), {
        receiver_name: proofForm.receiver_name,
        signature: proofForm.signature,
        geo_lat: proofForm.geo_lat === '' ? null : Number(proofForm.geo_lat),
        geo_lng: proofForm.geo_lng === '' ? null : Number(proofForm.geo_lng),
      })
      setProofResult(`Preuve capturee. Statut: ${res.status || 'delivered'}`)
    } catch (err) {
      setError(err.message)
    }
  }

  async function onLoadRelayForecast(e) {
    e.preventDefault()
    setError('')
    try {
      const res = await getRelayPickupForecast(token, forecastRelayId.trim(), Number(forecastHours || 24))
      setPickupForecast(Array.isArray(res?.items) ? res.items : [])
    } catch (err) {
      setError(err.message)
      setPickupForecast([])
    }
  }

  return (
    <section className="page-grid">
      <article className="page-banner">
        <p className="eyebrow">Ops Cockpit</p>
        <h2>Tracking live, workflow statut et suivi client</h2>
        <p>
          Suivi transport avec recherche colis, ETA dynamique, timeline et operations terrain temps reel.
        </p>
      </article>

      <section className="page-grid two-cols ops-grid">
        <article className="panel">
          <h3>Recherche colis (style DHL)</h3>
          <form className="form" onSubmit={onLookupShipment}>
            <label>
              Numero colis ou Shipment ID
              <input
                placeholder="Ex: SHP-2026-000123 ou UUID"
                value={lookupInput}
                onChange={(e) => setLookupInput(e.target.value)}
                required
              />
            </label>
            <button type="submit" disabled={!token || trackingLoading}>
              {trackingLoading ? 'Recherche...' : 'Rechercher'}
            </button>
          </form>

          {trackedShipment ? (
            <div className="stack-compact" style={{ marginTop: 10 }}>
              <div className="data-row">
                <span>Numero</span>
                <strong className="mono">{trackedShipment.shipment_no || '-'}</strong>
              </div>
              <div className="data-row">
                <span>Shipment ID</span>
                <strong className="mono">{trackedShipment.id}</strong>
              </div>
              <div className="data-row">
                <span>Statut</span>
                <span className="badge info">{trackedShipment.status || '-'}</span>
              </div>
            </div>
          ) : (
            <p style={{ marginTop: 10 }}>Aucun colis charge.</p>
          )}

          {lookupMatches.length > 1 ? (
            <div className="relay-list" style={{ marginTop: 10 }}>
              {lookupMatches.map((row) => (
                <div key={row.id} className="relay-item">
                  <p>
                    <strong>{row.shipment_no}</strong> | {row.status || '-'}
                  </p>
                  <button type="button" className="button-secondary" onClick={() => onSelectMatch(row)}>
                    Ouvrir ce colis
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </article>

        <article className="panel">
          <h3>Resume de tracking</h3>
          {trackingSummary ? (
            <div className="stack-compact">
              <div className="data-row">
                <span>SLA</span>
                <strong>{trackingSummary.sla_state}</strong>
              </div>
              <div className="data-row">
                <span>Heures restantes SLA</span>
                <strong>{trackingSummary.remaining_sla_hours}h</strong>
              </div>
              <div className="data-row">
                <span>Incidents ouverts</span>
                <strong>{trackingSummary.open_incidents}</strong>
              </div>
              <div className="surface-soft">
                <p className="mono">ETA: {formatDateTime(trackingSummary.estimated_delivery_at)}</p>
              </div>
              {Array.isArray(trackingSummary.risk_reasons) && trackingSummary.risk_reasons.length > 0 ? (
                <div className="relay-list">
                  {trackingSummary.risk_reasons.map((reason, idx) => (
                    <div key={`${reason}-${idx}`} className="relay-item">
                      <p>{reason}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <p>Aucun resume charge.</p>
          )}
        </article>
      </section>

      <article className="panel">
        <h3>Timeline colis</h3>
        <div className="relay-list list-scroll">
          {trackingTimeline.length === 0 ? <p>Aucun evenement pour ce colis.</p> : null}
          {trackingTimeline.map((item, index) => (
            <div key={`${item.occurred_at || 'no-ts'}-${item.code || index}`} className="relay-item">
              <p>
                <strong>{item.message || item.code || item.kind || 'event'}</strong>
              </p>
              <p>{formatDateTime(item.occurred_at)}</p>
              <p>status: {item.status || '-'}</p>
              <p className="mono">relay: {item.relay_id || '-'}</p>
            </div>
          ))}
        </div>
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

      {isOpsRole ? (
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
      ) : null}

      {isClientRole ? (
        <article className="panel">
          <h3>Choisir un creneau de retrait</h3>
          <form className="form" onSubmit={onSavePickupSlot}>
            <label>
              Shipment ID
              <input
                placeholder="UUID"
                value={pickupSlotForm.shipment_id}
                onChange={(e) => setPickupSlotForm((s) => ({ ...s, shipment_id: e.target.value }))}
                required
              />
            </label>
            <label>
              Debut creneau
              <input
                type="datetime-local"
                value={pickupSlotForm.starts_at}
                onChange={(e) => setPickupSlotForm((s) => ({ ...s, starts_at: e.target.value }))}
                required
              />
            </label>
            <label>
              Fin creneau
              <input
                type="datetime-local"
                value={pickupSlotForm.ends_at}
                onChange={(e) => setPickupSlotForm((s) => ({ ...s, ends_at: e.target.value }))}
                required
              />
            </label>
            <label>
              Note
              <input
                value={pickupSlotForm.note}
                onChange={(e) => setPickupSlotForm((s) => ({ ...s, note: e.target.value }))}
                placeholder="Ex: entre 17h et 18h"
              />
            </label>
            <button type="submit" disabled={!token}>
              Enregistrer creneau
            </button>
          </form>
          {pickupSlotResult ? <p className="status-line">{pickupSlotResult}</p> : null}
        </article>
      ) : null}

      {isOpsRole ? (
        <section className="page-grid two-cols ops-grid">
          <article className="panel">
            <h3>Preuve de remise digitale</h3>
            <form className="form" onSubmit={onCaptureDeliveryProof}>
              <label>
                Shipment ID
                <input
                  placeholder="UUID"
                  value={proofForm.shipment_id}
                  onChange={(e) => setProofForm((s) => ({ ...s, shipment_id: e.target.value }))}
                  required
                />
              </label>
              <label>
                Nom receveur
                <input
                  value={proofForm.receiver_name}
                  onChange={(e) => setProofForm((s) => ({ ...s, receiver_name: e.target.value }))}
                  required
                />
              </label>
              <label>
                Signature (texte)
                <input
                  value={proofForm.signature}
                  onChange={(e) => setProofForm((s) => ({ ...s, signature: e.target.value }))}
                  required
                />
              </label>
              <label>
                Geo lat
                <input
                  value={proofForm.geo_lat}
                  onChange={(e) => setProofForm((s) => ({ ...s, geo_lat: e.target.value }))}
                  placeholder="-3.38"
                />
              </label>
              <label>
                Geo lng
                <input
                  value={proofForm.geo_lng}
                  onChange={(e) => setProofForm((s) => ({ ...s, geo_lng: e.target.value }))}
                  placeholder="29.36"
                />
              </label>
              <button type="submit" disabled={!token}>
                Capturer preuve
              </button>
            </form>
            {proofResult ? <p className="status-line">{proofResult}</p> : null}
          </article>

          <article className="panel">
            <h3>Forecast retraits relais</h3>
            <form className="form" onSubmit={onLoadRelayForecast}>
              <label>
                Relay ID
                <input
                  placeholder="UUID relay"
                  value={forecastRelayId}
                  onChange={(e) => setForecastRelayId(e.target.value)}
                  required
                />
              </label>
              <label>
                Horizon (heures)
                <input
                  type="number"
                  min="1"
                  max="168"
                  value={forecastHours}
                  onChange={(e) => setForecastHours(e.target.value)}
                  required
                />
              </label>
              <button type="submit" disabled={!token}>
                Charger forecast
              </button>
            </form>
            <div className="relay-list" style={{ marginTop: 10 }}>
              {pickupForecast.length === 0 ? <p>Aucun retrait planifie.</p> : null}
              {pickupForecast.map((item) => (
                <div key={item.slot_hour} className="relay-item">
                  <p className="mono">{item.slot_hour}</p>
                  <p>
                    <strong>{item.planned_pickups}</strong> retraits
                  </p>
                </div>
              ))}
            </div>
          </article>
        </section>
      ) : null}

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
