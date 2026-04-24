import { useEffect, useMemo, useState } from 'react'
import {
  addShipmentToManifest,
  autoAssignPriorityToTrip,
  completeTrip,
  createTrip,
  getTransportGroupingSuggestions,
  getTransportPrioritySuggestions,
  getTripManifest,
  listTrips,
  removeShipmentFromManifest,
  scanTripArrival,
  scanTripDeparture,
  updateTrip,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'

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

export default function TransportPage() {
  const { token } = useAuth()
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

  const selectedTrip = useMemo(
    () => trips.find((trip) => trip.id === selectedTripId) || null,
    [trips, selectedTripId],
  )

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

  useEffect(() => {
    loadTrips().catch((err) => setError(err.message))
    loadGrouping().catch((err) => setError(err.message))
    loadPriorityQueue().catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    loadManifest(selectedTripId).catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTripId, token])

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

  async function onApplySuggestion(suggestion) {
    setError('')
    setMessage('')
    if (!selectedTripId) return
    try {
      let added = 0
      for (const item of suggestion.shipments || []) {
        try {
          await addShipmentToManifest(token, selectedTripId, item.shipment_id)
          added += 1
        } catch {
          // Skip duplicates or invalid items and continue with the batch.
        }
      }
      setMessage(`Lot applique au trip: ${added} colis ajoutes`)
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
              Route ID (optionnel)
              <input
                value={tripForm.route_id}
                onChange={(e) => setTripForm((s) => ({ ...s, route_id: e.target.value }))}
                placeholder="UUID route"
              />
            </label>
            <label>
              Vehicle ID (optionnel)
              <input
                value={tripForm.vehicle_id}
                onChange={(e) => setTripForm((s) => ({ ...s, vehicle_id: e.target.value }))}
                placeholder="UUID vehicle"
              />
            </label>
            <label>
              Statut
              <select
                value={tripForm.status}
                onChange={(e) => setTripForm((s) => ({ ...s, status: e.target.value }))}
              >
                <option value="planned">planned</option>
                <option value="in_progress">in_progress</option>
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
          <div className="relay-list">
            {trips.length === 0 ? <p>Aucun trip</p> : null}
            {trips.map((trip) => (
              <div key={trip.id} className="relay-item">
                <p>
                  <strong>{trip.id}</strong>
                </p>
                <p>
                  status: {trip.status || '-'} | route: {trip.route_id || '-'} | vehicle:{' '}
                  {trip.vehicle_id || '-'}
                </p>
                <div className="ops-actions">
                  <button type="button" onClick={() => setSelectedTripId(trip.id)}>
                    Selectionner
                  </button>
                  <button type="button" className="button-secondary" onClick={() => onEditTrip(trip)}>
                    Editer
                  </button>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Manifest du trip</h3>
          <p>
            Trip selectionne: <strong>{selectedTrip ? selectedTrip.id : '-'}</strong>
          </p>
          <form className="form" onSubmit={onAddShipmentToManifest}>
            <label>
              Shipment ID
              <input
                value={shipmentIdInput}
                onChange={(e) => setShipmentIdInput(e.target.value)}
                placeholder="UUID shipment"
                required
              />
            </label>
            <button type="submit" disabled={!selectedTripId}>
              Ajouter au manifest
            </button>
          </form>
          <div className="relay-list">
            {!manifestView || manifestView.shipments.length === 0 ? <p>Aucun colis</p> : null}
            {manifestView?.shipments.map((shipment) => (
              <div key={shipment.id} className="relay-item">
                <p>
                  <strong>{shipment.shipment_no}</strong> ({shipment.id})
                </p>
                <p>
                  statut: {shipment.status || '-'} | destinataire: {shipment.receiver_name || '-'}
                </p>
                <button type="button" onClick={() => onRemoveShipment(shipment.id)}>
                  Retirer
                </button>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h3>Scans depart / arrivee</h3>
          <label>
            Relay ID (optionnel)
            <input
              value={scanRelayId}
              onChange={(e) => setScanRelayId(e.target.value)}
              placeholder="UUID relay"
            />
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

      <article className="panel">
        <p className="eyebrow">Optimizer</p>
        <h3>Propositions de regroupement colis</h3>
        <p>
          Candidats: <strong>{grouping?.total_candidates ?? '-'}</strong> | Groupes:{' '}
          <strong>{grouping?.total_groups ?? '-'}</strong> | Taille lot: <strong>{grouping?.max_group_size ?? '-'}</strong>
        </p>
        <div className="relay-list">
          {!grouping || grouping.suggestions.length === 0 ? <p>Aucun regroupement propose</p> : null}
          {grouping?.suggestions?.slice(0, 20).map((suggestion) => (
            <div key={suggestion.key} className="relay-item">
              <p>
                <strong>{suggestion.key}</strong> | count: {suggestion.candidate_count}
              </p>
              <p>
                origin: {suggestion.origin || '-'} | destination: {suggestion.destination || '-'}
              </p>
              <p>
                colis: {(suggestion.shipments || []).map((x) => x.shipment_no || x.shipment_id).join(', ')}
              </p>
              <button type="button" disabled={!selectedTripId} onClick={() => onApplySuggestion(suggestion)}>
                Appliquer au trip selectionne
              </button>
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
                status: {item.status || '-'} | origin: {item.origin || '-'} | destination:{' '}
                {item.destination || '-'}
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
