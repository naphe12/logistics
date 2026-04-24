import { useEffect, useState } from 'react'
import {
  addIncidentUpdate,
  createClaim,
  createIncident,
  listClaims,
  listIncidentStatuses,
  listIncidentUpdates,
  listIncidents,
  updateClaimStatus,
  updateIncidentStatus,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'

const incidentTypes = ['lost', 'damaged', 'delayed', 'claim']
const claimStatuses = ['submitted', 'reviewing', 'approved', 'rejected', 'paid']

export default function IncidentsPage() {
  const { token } = useAuth()
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [statuses, setStatuses] = useState([])
  const [incidents, setIncidents] = useState([])
  const [claims, setClaims] = useState([])
  const [selectedIncidentId, setSelectedIncidentId] = useState('')
  const [incidentUpdates, setIncidentUpdates] = useState([])
  const [filters, setFilters] = useState({ shipment_id: '', status: '', incident_type: '' })
  const [incidentForm, setIncidentForm] = useState({
    shipment_id: '',
    incident_type: 'lost',
    description: '',
  })
  const [updateForm, setUpdateForm] = useState({ status: '', message: '' })
  const [claimForm, setClaimForm] = useState({
    incident_id: '',
    shipment_id: '',
    amount: '',
    reason: '',
  })
  const [claimUpdateForm, setClaimUpdateForm] = useState({
    claim_id: '',
    status: 'reviewing',
    resolution_note: '',
    refunded_payment_id: '',
  })

  async function loadIncidents() {
    if (!token) return
    const [statusData, incidentData, claimData] = await Promise.all([
      listIncidentStatuses(token),
      listIncidents(token, filters),
      listClaims(token),
    ])
    setStatuses(statusData)
    setIncidents(incidentData)
    setClaims(claimData)
    if (!selectedIncidentId && incidentData.length > 0) {
      setSelectedIncidentId(incidentData[0].id)
    }
  }

  async function loadUpdates(incidentId) {
    if (!token || !incidentId) return
    const data = await listIncidentUpdates(token, incidentId)
    setIncidentUpdates(data)
  }

  useEffect(() => {
    loadIncidents().catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    loadUpdates(selectedIncidentId).catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIncidentId, token])

  async function onApplyFilters(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      const data = await listIncidents(token, filters)
      setIncidents(data)
    } catch (err) {
      setError(err.message)
    }
  }

  async function onCreateIncident(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      await createIncident(token, incidentForm)
      setMessage('Incident cree')
      setIncidentForm({ shipment_id: '', incident_type: 'lost', description: '' })
      await loadIncidents()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onUpdateIncidentStatus(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (!selectedIncidentId || !updateForm.status) return
    try {
      await updateIncidentStatus(token, selectedIncidentId, updateForm.status)
      setMessage('Statut incident mis a jour')
      setUpdateForm((s) => ({ ...s, status: '' }))
      await loadIncidents()
      await loadUpdates(selectedIncidentId)
    } catch (err) {
      setError(err.message)
    }
  }

  async function onAddIncidentUpdate(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (!selectedIncidentId || !updateForm.message) return
    try {
      await addIncidentUpdate(token, selectedIncidentId, updateForm.message)
      setMessage('Mise a jour ajoutee')
      setUpdateForm((s) => ({ ...s, message: '' }))
      await loadUpdates(selectedIncidentId)
    } catch (err) {
      setError(err.message)
    }
  }

  async function onCreateClaim(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      await createClaim(token, {
        incident_id: claimForm.incident_id,
        shipment_id: claimForm.shipment_id,
        amount: Number(claimForm.amount),
        reason: claimForm.reason,
      })
      setMessage('Reclamation creee')
      setClaimForm({ incident_id: '', shipment_id: '', amount: '', reason: '' })
      const claimData = await listClaims(token)
      setClaims(claimData)
    } catch (err) {
      setError(err.message)
    }
  }

  async function onUpdateClaimStatus(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (!claimUpdateForm.claim_id) return
    try {
      await updateClaimStatus(token, claimUpdateForm.claim_id, {
        status: claimUpdateForm.status,
        resolution_note: claimUpdateForm.resolution_note || null,
        refunded_payment_id: claimUpdateForm.refunded_payment_id || null,
      })
      setMessage('Statut reclamation mis a jour')
      setClaimUpdateForm({
        claim_id: '',
        status: 'reviewing',
        resolution_note: '',
        refunded_payment_id: '',
      })
      const claimData = await listClaims(token)
      setClaims(claimData)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="page-grid">
      <article className="panel">
        <p className="eyebrow">Incidents</p>
        <h2>Perte, dommage, retard, reclamation</h2>
        <p>Declaration, investigation, suivi et gestion des reclamations.</p>
      </article>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Declarer incident</h3>
          <form className="form" onSubmit={onCreateIncident}>
            <label>
              Shipment ID
              <input
                value={incidentForm.shipment_id}
                onChange={(e) => setIncidentForm((s) => ({ ...s, shipment_id: e.target.value }))}
                required
              />
            </label>
            <label>
              Type incident
              <select
                value={incidentForm.incident_type}
                onChange={(e) => setIncidentForm((s) => ({ ...s, incident_type: e.target.value }))}
              >
                {incidentTypes.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Description
              <input
                value={incidentForm.description}
                onChange={(e) => setIncidentForm((s) => ({ ...s, description: e.target.value }))}
                required
              />
            </label>
            <button type="submit">Creer incident</button>
          </form>
        </article>

        <article className="panel">
          <h3>Filtres incidents</h3>
          <form className="form" onSubmit={onApplyFilters}>
            <label>
              Shipment ID
              <input
                value={filters.shipment_id}
                onChange={(e) => setFilters((s) => ({ ...s, shipment_id: e.target.value }))}
              />
            </label>
            <label>
              Statut
              <select
                value={filters.status}
                onChange={(e) => setFilters((s) => ({ ...s, status: e.target.value }))}
              >
                <option value="">Tous</option>
                {statuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Type
              <select
                value={filters.incident_type}
                onChange={(e) => setFilters((s) => ({ ...s, incident_type: e.target.value }))}
              >
                <option value="">Tous</option>
                {incidentTypes.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit">Appliquer</button>
          </form>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Liste incidents</h3>
          <div className="relay-list">
            {incidents.length === 0 ? <p>Aucun incident</p> : null}
            {incidents.map((incident) => (
              <div key={incident.id} className="relay-item">
                <p>
                  <strong>{incident.id}</strong>
                </p>
                <p>
                  shipment: {incident.shipment_id} | type: {incident.incident_type} | statut:{' '}
                  <strong>{incident.status}</strong>
                </p>
                <p>{incident.description}</p>
                <button type="button" onClick={() => setSelectedIncidentId(incident.id)}>
                  Selectionner
                </button>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h3>Suivi incident</h3>
          <p>
            Incident selectionne: <strong>{selectedIncidentId || '-'}</strong>
          </p>
          <form className="form" onSubmit={onUpdateIncidentStatus}>
            <label>
              Nouveau statut
              <select
                value={updateForm.status}
                onChange={(e) => setUpdateForm((s) => ({ ...s, status: e.target.value }))}
              >
                <option value="">Choisir</option>
                {statuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={!selectedIncidentId || !updateForm.status}>
              Mettre a jour statut
            </button>
          </form>

          <form className="form" onSubmit={onAddIncidentUpdate}>
            <label>
              Message de suivi
              <input
                value={updateForm.message}
                onChange={(e) => setUpdateForm((s) => ({ ...s, message: e.target.value }))}
              />
            </label>
            <button type="submit" disabled={!selectedIncidentId || !updateForm.message}>
              Ajouter update
            </button>
          </form>

          <div className="relay-list">
            {incidentUpdates.length === 0 ? <p>Aucun suivi</p> : null}
            {incidentUpdates.map((update) => (
              <div key={update.id} className="relay-item">
                <p>{update.message}</p>
                <p>{update.created_at}</p>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Creer reclamation</h3>
          <form className="form" onSubmit={onCreateClaim}>
            <label>
              Incident ID
              <input
                value={claimForm.incident_id}
                onChange={(e) => setClaimForm((s) => ({ ...s, incident_id: e.target.value }))}
                required
              />
            </label>
            <label>
              Shipment ID
              <input
                value={claimForm.shipment_id}
                onChange={(e) => setClaimForm((s) => ({ ...s, shipment_id: e.target.value }))}
                required
              />
            </label>
            <label>
              Montant
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={claimForm.amount}
                onChange={(e) => setClaimForm((s) => ({ ...s, amount: e.target.value }))}
                required
              />
            </label>
            <label>
              Raison
              <input
                value={claimForm.reason}
                onChange={(e) => setClaimForm((s) => ({ ...s, reason: e.target.value }))}
                required
              />
            </label>
            <button type="submit">Creer reclamation</button>
          </form>
        </article>

        <article className="panel">
          <h3>Mettre a jour reclamation</h3>
          <form className="form" onSubmit={onUpdateClaimStatus}>
            <label>
              Claim ID
              <input
                value={claimUpdateForm.claim_id}
                onChange={(e) => setClaimUpdateForm((s) => ({ ...s, claim_id: e.target.value }))}
                required
              />
            </label>
            <label>
              Statut claim
              <select
                value={claimUpdateForm.status}
                onChange={(e) => setClaimUpdateForm((s) => ({ ...s, status: e.target.value }))}
              >
                {claimStatuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Note resolution
              <input
                value={claimUpdateForm.resolution_note}
                onChange={(e) => setClaimUpdateForm((s) => ({ ...s, resolution_note: e.target.value }))}
              />
            </label>
            <label>
              Payment ID remboursement (optionnel)
              <input
                value={claimUpdateForm.refunded_payment_id}
                onChange={(e) => setClaimUpdateForm((s) => ({ ...s, refunded_payment_id: e.target.value }))}
              />
            </label>
            <button type="submit">Mettre a jour claim</button>
          </form>
        </article>
      </section>

      <section className="page-grid">
        <article className="panel">
          <h3>Reclamations</h3>
          <div className="relay-list">
            {claims.length === 0 ? <p>Aucune reclamation</p> : null}
            {claims.map((claim) => (
              <div key={claim.id} className="relay-item">
                <p>
                  <strong>{claim.id}</strong>
                </p>
                <p>
                  incident: {claim.incident_id} | shipment: {claim.shipment_id}
                </p>
                <p>
                  montant: {claim.amount} | status: {claim.status}
                </p>
                <p>{claim.reason}</p>
                {claim.resolution_note ? <p>resolution: {claim.resolution_note}</p> : null}
                {claim.refunded_payment_id ? <p>refund payment: {claim.refunded_payment_id}</p> : null}
              </div>
            ))}
          </div>
        </article>
      </section>

      {message ? <p className="status-line">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
