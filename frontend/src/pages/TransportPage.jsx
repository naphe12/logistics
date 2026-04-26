import { useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import {
  addShipmentToManifest,
  autoAssignPriorityToTrip,
  completeTrip,
  createTrip,
  getTransportGroupingSuggestions,
  getTransportPrioritySuggestions,
  getTripManifest,
  listPublicRelays,
  listShipments,
  listTransportRoutes,
  listTransportVehicles,
  listTrips,
  removeShipmentFromManifest,
  scanTripArrival,
  scanTripDeparture,
  updateTrip,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { humanizeStatus, relayDisplayName } from '../utils/display'

const defaultTripForm = {
  route_id: '',
  vehicle_id: '',
  status: 'planned',
}

const defaultAutoAssignForm = {
  targetManifestSize: 20,
  maxAdd: 10,
  candidateLimit: 500,
  vehicleCapacity: '',
}

function shortId(value) {
  if (!value) return '-'
  const text = String(value)
  return text.length > 8 ? text.slice(0, 8).toUpperCase() : text.toUpperCase()
}

function tripDisplayLabel(trip) {
  if (!trip) return '-'
  const fromExtra = trip.extra?.trip_no || trip.extra?.code || trip.extra?.trip_code
  if (fromExtra) return String(fromExtra)
  return `TRIP-${shortId(trip.id)}`
}

function shipmentOptionLabel(shipment, relayNameById = {}) {
  if (!shipment) return '-'
  const no = shipment.shipment_no || shortId(shipment.id)
  const status = humanizeStatus(shipment.status || '-')
  const receiver = shipment.receiver_name || shipment.receiver_phone || '-'
  const destinationId = shipment.destination || shipment.destination_relay_id
  const destination = relayDisplayName(destinationId, relayNameById)
  return `${no} | ${status} | ${receiver} -> ${destination}`
}

export default function TransportPage() {
  const { token } = useAuth()
  const location = useLocation()
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [trips, setTrips] = useState([])
  const [selectedTripId, setSelectedTripId] = useState('')
  const [manifestView, setManifestView] = useState(null)
  const [tripForm, setTripForm] = useState(defaultTripForm)
  const [editingTripId, setEditingTripId] = useState('')
  const [shipmentIdInput, setShipmentIdInput] = useState('')
  const [scanRelayId, setScanRelayId] = useState('')
  const [grouping, setGrouping] = useState(null)
  const [priorityQueue, setPriorityQueue] = useState(null)
  const [autoAssignForm, setAutoAssignForm] = useState(defaultAutoAssignForm)
  const [autoAssignResult, setAutoAssignResult] = useState(null)
  const [relayNameById, setRelayNameById] = useState({})
  const [routes, setRoutes] = useState([])
  const [vehicles, setVehicles] = useState([])
  const [shipments, setShipments] = useState([])
  const [relayOptions, setRelayOptions] = useState([])

  const selectedTrip = useMemo(
    () => trips.find((trip) => trip.id === selectedTripId) || null,
    [trips, selectedTripId],
  )
  const routeById = useMemo(() => {
    const map = {}
    for (const row of routes) map[row.id] = row
    return map
  }, [routes])
  const vehicleById = useMemo(() => {
    const map = {}
    for (const row of vehicles) map[row.id] = row
    return map
  }, [vehicles])
  const manifestShipmentIds = useMemo(
    () => new Set((manifestView?.shipments || []).map((item) => item.id)),
    [manifestView],
  )
  const assignableShipments = useMemo(
    () => shipments.filter((item) => item?.id && !manifestShipmentIds.has(item.id)),
    [shipments, manifestShipmentIds],
  )

  function routeLabel(routeId) {
    if (!routeId) return '-'
    const route = routeById[routeId]
    if (!route) return `Route ${shortId(routeId)}`
    const origin = route.origin_name || route.origin_code || relayNameById[route.origin] || shortId(route.origin)
    const destination =
      route.destination_name || route.destination_code || relayNameById[route.destination] || shortId(route.destination)
    return `${origin || '-'} -> ${destination || '-'}`
  }

  function vehicleLabel(vehicleId) {
    if (!vehicleId) return '-'
    const vehicle = vehicleById[vehicleId]
    if (!vehicle) return `Vehicule ${shortId(vehicleId)}`
    const plate = vehicle.plate || shortId(vehicle.id)
    const partner = vehicle.partner_name ? ` (${vehicle.partner_name})` : ''
    return `${plate}${partner}`
  }

  async function loadTrips() {
    if (!token) return
    const data = await listTrips(token)
    setTrips(data)
    if (!selectedTripId && data.length > 0) setSelectedTripId(data[0].id)
  }

  async function loadManifest(tripId) {
    if (!token || !tripId) return
    const data = await getTripManifest(token, tripId)
    setManifestView(data)
  }

  async function loadGrouping() {
    if (!token) return
    const data = await getTransportGroupingSuggestions(token, { maxGroupSize: 8, limit: 200 })
    setGrouping(data)
  }

  async function loadPriorityQueue() {
    if (!token) return
    const data = await getTransportPrioritySuggestions(token, { maxResults: 30, limit: 500 })
    setPriorityQueue(data)
  }

  async function loadShipmentsCatalog() {
    if (!token) return
    const data = await listShipments(token, { limit: 400, sort: 'created_at_desc' })
    setShipments(Array.isArray(data) ? data : [])
  }

  useEffect(() => {
    loadTrips().catch((err) => setError(err.message))
    loadGrouping().catch((err) => setError(err.message))
    loadPriorityQueue().catch((err) => setError(err.message))
    loadShipmentsCatalog().catch((err) => setError(err.message))
    listTransportRoutes(token)
      .then((rows) => setRoutes(Array.isArray(rows) ? rows : []))
      .catch(() => setRoutes([]))
    listTransportVehicles(token)
      .then((rows) => setVehicles(Array.isArray(rows) ? rows : []))
      .catch(() => setVehicles([]))
    listPublicRelays()
      .then((rows) => {
        setRelayOptions(Array.isArray(rows) ? rows : [])
        const map = {}
        for (const row of Array.isArray(rows) ? rows : []) {
          if (row?.id) map[row.id] = row.name || row.id
        }
        setRelayNameById(map)
      })
      .catch(() => {
        setRelayOptions([])
        setRelayNameById({})
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    loadManifest(selectedTripId).catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTripId, token])

  useEffect(() => {
    const hash = (location.hash || '').replace(/^#/, '')
    if (!hash) return
    const node = document.getElementById(hash)
    if (!node) return
    node.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [location.hash])

  function resetTripForm() {
    setTripForm(defaultTripForm)
    setEditingTripId('')
  }

  async function onCreateOrUpdateTrip(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      const payload = {
        route_id: tripForm.route_id || null,
        vehicle_id: tripForm.vehicle_id || null,
        status: tripForm.status,
      }
      if (editingTripId) {
        await updateTrip(token, editingTripId, payload)
        setMessage('Trip mis a jour')
      } else {
        await createTrip(token, payload)
        setMessage('Trip cree')
      }
      resetTripForm()
      await loadTrips()
    } catch (err) {
      setError(err.message)
    }
  }

  function onEditTrip(trip) {
    setEditingTripId(trip.id)
    setTripForm({
      route_id: trip.route_id || '',
      vehicle_id: trip.vehicle_id || '',
      status: trip.status || 'planned',
    })
  }

  async function onAddShipmentToManifest(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (!selectedTripId) return
    try {
      await addShipmentToManifest(token, selectedTripId, shipmentIdInput)
      setShipmentIdInput('')
      setMessage('Colis ajoute au manifest')
      await loadManifest(selectedTripId)
      await loadGrouping()
      await loadPriorityQueue()
      await loadShipmentsCatalog()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onRemoveShipment(shipmentId) {
    setError('')
    setMessage('')
    if (!selectedTripId) return
    try {
      await removeShipmentFromManifest(token, selectedTripId, shipmentId)
      setMessage('Colis retire du manifest')
      await loadManifest(selectedTripId)
      await loadGrouping()
      await loadPriorityQueue()
      await loadShipmentsCatalog()
    } catch (err) {
      setError(err.message)
    }
  }

  async function runScan(fn, successLabel) {
    setError('')
    setMessage('')
    if (!selectedTripId) return
    try {
      const payload = scanRelayId ? { relay_id: scanRelayId } : {}
      const res = await fn(token, selectedTripId, payload)
      setMessage(`${successLabel}: ${res.updated_shipments} colis`)
      await loadTrips()
      await loadManifest(selectedTripId)
    } catch (err) {
      setError(err.message)
    }
  }

  async function onCompleteTrip() {
    setError('')
    setMessage('')
    if (!selectedTripId) return
    try {
      await completeTrip(token, selectedTripId)
      setMessage('Trip complete')
      await loadTrips()
      await loadManifest(selectedTripId)
      await loadGrouping()
      await loadPriorityQueue()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onAutoAssignPriority(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setAutoAssignResult(null)
    if (!selectedTripId) return
    try {
      const res = await autoAssignPriorityToTrip(token, selectedTripId, autoAssignForm)
      setAutoAssignResult(res)
      setMessage(
        `Auto-assign: ${res.added_count} ajoutes, ${res.rejected_count} rejetes (manifest ${res.before_count} -> ${res.after_count})`,
      )
      await loadManifest(selectedTripId)
      await loadGrouping()
      await loadPriorityQueue()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="page-grid">
      <article className="panel">
        <p className="eyebrow">Transport</p>
        <h2>Trips et manifests</h2>
        <p>Planifier les trips, affecter les colis, puis scanner depart/arrivee.</p>
      </article>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>{editingTripId ? 'Modifier trip' : 'Nouveau trip'}</h3>
          <form className="form" onSubmit={onCreateOrUpdateTrip}>
            <label>
              Route (optionnel)
              <select
                value={tripForm.route_id}
                onChange={(e) => setTripForm((s) => ({ ...s, route_id: e.target.value }))}
              >
                <option value="">Aucune route</option>
                {routes.map((route) => (
                  <option key={route.id} value={route.id}>
                    {routeLabel(route.id)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Vehicule (optionnel)
              <select
                value={tripForm.vehicle_id}
                onChange={(e) => setTripForm((s) => ({ ...s, vehicle_id: e.target.value }))}
              >
                <option value="">Aucun vehicule</option>
                {vehicles.map((vehicle) => (
                  <option key={vehicle.id} value={vehicle.id}>
                    {vehicleLabel(vehicle.id)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Statut
              <select
                value={tripForm.status}
                onChange={(e) => setTripForm((s) => ({ ...s, status: e.target.value }))}
              >
                <option value="planned">planned</option>
                <option value="in_progress">in progress</option>
                <option value="arrived">arrived</option>
                <option value="completed">completed</option>
                <option value="cancelled">cancelled</option>
              </select>
            </label>
            <div className="ops-actions">
              <button type="submit">{editingTripId ? 'Mettre a jour' : 'Creer trip'}</button>
              {editingTripId ? (
                <button type="button" className="button-secondary" onClick={resetTripForm}>
                  Annuler edition
                </button>
              ) : null}
            </div>
          </form>
        </article>

        <article className="panel">
          <h3>Liste trips</h3>
          <div className="premium-table-wrap">
            {trips.length === 0 ? (
              <p>Aucun trip</p>
            ) : (
              <table className="premium-table">
                <thead>
                  <tr>
                    <th>Trip</th>
                    <th>Statut</th>
                    <th>Route</th>
                    <th>Vehicule</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {trips.map((trip) => (
                    <tr key={trip.id}>
                      <td>
                        <strong>{tripDisplayLabel(trip)}</strong>
                      </td>
                      <td>
                        <span className="badge info">{humanizeStatus(trip.status)}</span>
                      </td>
                      <td>{routeLabel(trip.route_id)}</td>
                      <td>{vehicleLabel(trip.vehicle_id)}</td>
                      <td>
                        <div className="table-actions">
                          <button type="button" onClick={() => setSelectedTripId(trip.id)}>
                            Selectionner
                          </button>
                          <button type="button" className="button-secondary" onClick={() => onEditTrip(trip)}>
                            Editer
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Manifest du trip</h3>
          <p>
            Trip selectionne: <strong>{selectedTrip ? tripDisplayLabel(selectedTrip) : '-'}</strong>
          </p>
          <form className="form" onSubmit={onAddShipmentToManifest}>
            <label>
              Colis a ajouter
              <select
                value={shipmentIdInput}
                onChange={(e) => setShipmentIdInput(e.target.value)}
                required
              >
                <option value="">Selectionner un colis</option>
                {assignableShipments.map((shipment) => (
                  <option key={shipment.id} value={shipment.id}>
                    {shipmentOptionLabel(shipment, relayNameById)}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={!selectedTripId || !shipmentIdInput}>
              Ajouter au manifest
            </button>
          </form>
          <div className="premium-table-wrap">
            {!manifestView || manifestView.shipments.length === 0 ? (
              <p>Aucun colis</p>
            ) : (
              <table className="premium-table">
                <thead>
                  <tr>
                    <th>Colis</th>
                    <th>Statut</th>
                    <th>Destinataire</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {manifestView.shipments.map((shipment) => (
                    <tr key={shipment.id}>
                      <td>
                        <strong>{shipment.shipment_no || '-'}</strong>
                        <br />
                        <span className="mono">{String(shipment.id).slice(0, 8).toUpperCase()}</span>
                      </td>
                      <td>
                        <span className="badge info">{humanizeStatus(shipment.status)}</span>
                      </td>
                      <td>{shipment.receiver_name || shipment.receiver_phone || '-'}</td>
                      <td>
                        <div className="table-actions">
                          <button type="button" onClick={() => onRemoveShipment(shipment.id)}>
                            Retirer
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </article>

        <article className="panel">
          <h3>Scans depart / arrivee</h3>
          <label>
            Relais de scan (optionnel)
            <select
              value={scanRelayId}
              onChange={(e) => setScanRelayId(e.target.value)}
            >
              <option value="">Auto (selon route/trip)</option>
              {relayOptions.map((relay) => (
                <option key={relay.id} value={relay.id}>
                  {(relay.name || relay.relay_code || shortId(relay.id)) +
                    (relay.relay_code ? ` (${relay.relay_code})` : '')}
                </option>
              ))}
            </select>
          </label>
          <div className="ops-actions">
            <button type="button" disabled={!selectedTripId} onClick={() => runScan(scanTripDeparture, 'Depart valide')}>
              Scanner depart
            </button>
            <button type="button" disabled={!selectedTripId} onClick={() => runScan(scanTripArrival, 'Arrivee validee')}>
              Scanner arrivee
            </button>
            <button type="button" disabled={!selectedTripId} onClick={onCompleteTrip}>
              Cloturer trip
            </button>
          </div>
        </article>
      </section>

      <article id="grouping-suggestions" className="panel">
        <p className="eyebrow">Optimizer</p>
        <h3>Propositions de regroupement colis</h3>
        <p>
          Candidats: <strong>{grouping?.total_candidates ?? '-'}</strong> | Groupes:{' '}
          <strong>{grouping?.total_groups ?? '-'}</strong> | Taille lot: <strong>{grouping?.max_group_size ?? '-'}</strong>
        </p>
        <div className="relay-list">
          {!grouping || grouping.suggestions.length === 0 ? <p>Aucun regroupement propose</p> : null}
          {grouping?.suggestions?.slice(0, 20).map((suggestion, index) => (
            <div key={suggestion.key} className="relay-item">
              <p>
                <strong>Groupe {index + 1}</strong> | count: {suggestion.candidate_count}
              </p>
              <p>
                origin: {relayDisplayName(suggestion.origin, relayNameById)} | destination:{' '}
                {relayDisplayName(suggestion.destination, relayNameById)}
              </p>
              <p>
                colis: {(suggestion.shipments || []).map((x) => x.shipment_no || x.shipment_id).join(', ')}
              </p>
            </div>
          ))}
        </div>
      </article>

      <article className="panel">
        <p className="eyebrow">Priority Queue</p>
        <h3>Colis a traiter en priorite</h3>
        <p>
          Candidats: <strong>{priorityQueue?.total_candidates ?? '-'}</strong> | Top:{' '}
          <strong>{priorityQueue?.max_results ?? '-'}</strong>
        </p>
        <div className="relay-list">
          {!priorityQueue || priorityQueue.suggestions.length === 0 ? <p>Aucune priorite calculee</p> : null}
          {priorityQueue?.suggestions?.slice(0, 15).map((item) => (
            <div key={item.shipment_id} className="relay-item">
              <p>
                <strong>{item.shipment_no || item.shipment_id}</strong> | score: {item.priority_score}
              </p>
              <p>
                status: {humanizeStatus(item.status)} | origin: {relayDisplayName(item.origin, relayNameById)} |
                destination: {relayDisplayName(item.destination, relayNameById)}
              </p>
              <p>reasons: {(item.reasons || []).join(' | ') || '-'}</p>
              <button
                type="button"
                disabled={!selectedTripId}
                onClick={async () => {
                  try {
                    setError('')
                    setMessage('')
                    await addShipmentToManifest(token, selectedTripId, item.shipment_id)
                    setMessage('Colis prioritaire ajoute au manifest')
                    await loadManifest(selectedTripId)
                    await loadGrouping()
                    await loadPriorityQueue()
                  } catch (err) {
                    setError(err.message)
                  }
                }}
              >
                Ajouter au trip selectionne
              </button>
            </div>
          ))}
        </div>
        <form className="form" onSubmit={onAutoAssignPriority}>
          <label>
            Taille cible manifest
            <input
              type="number"
              min={1}
              max={500}
              value={autoAssignForm.targetManifestSize}
              onChange={(e) =>
                setAutoAssignForm((s) => ({ ...s, targetManifestSize: Number(e.target.value || 0) }))
              }
              required
            />
          </label>
          <label>
            Max a ajouter
            <input
              type="number"
              min={1}
              max={200}
              value={autoAssignForm.maxAdd}
              onChange={(e) => setAutoAssignForm((s) => ({ ...s, maxAdd: Number(e.target.value || 0) }))}
              required
            />
          </label>
          <label>
            Volume candidats
            <input
              type="number"
              min={1}
              max={1000}
              value={autoAssignForm.candidateLimit}
              onChange={(e) =>
                setAutoAssignForm((s) => ({ ...s, candidateLimit: Number(e.target.value || 0) }))
              }
              required
            />
          </label>
          <label>
            Capacite vehicule (optionnel)
            <input
              type="number"
              min={1}
              max={1000}
              value={autoAssignForm.vehicleCapacity}
              onChange={(e) => setAutoAssignForm((s) => ({ ...s, vehicleCapacity: e.target.value }))}
              placeholder="ex: 40"
            />
          </label>
          <button type="submit" disabled={!selectedTripId}>
            Auto-affecter top priorites
          </button>
        </form>
        {autoAssignResult?.rejected_count > 0 ? (
          <div className="relay-list">
            {autoAssignResult.rejected.slice(0, 8).map((item) => (
              <div key={`rej-${item.shipment_id}`} className="relay-item">
                <p>
                  <strong>{item.shipment_no || item.shipment_id}</strong> | score: {item.priority_score}
                </p>
                <p>rejete: {(item.reasons || []).join(', ')}</p>
              </div>
            ))}
          </div>
        ) : null}
      </article>

      {message ? <p className="status-line">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
