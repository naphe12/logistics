import { useEffect, useMemo, useState } from 'react'
import {
  addShipmentToManifest,
  completeTrip,
  createTrip,
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

  useEffect(() => {
    loadTrips().catch((err) => setError(err.message))
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

      {message ? <p className="status-line">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
