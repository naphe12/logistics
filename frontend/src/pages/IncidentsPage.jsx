import { useEffect, useMemo, useState } from 'react'
import {
  addIncidentUpdate,
  autoEscalateClaims,
  createClaim,
  createIncident,
  getClaimsFinanceReport,
  getClaimsOpsStats,
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
  const { token, dashboardRole } = useAuth()
  const isOpsRole = dashboardRole === 'agent' || dashboardRole === 'admin'

  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [statuses, setStatuses] = useState([])
  const [incidents, setIncidents] = useState([])
  const [claims, setClaims] = useState([])
  const [selectedIncidentId, setSelectedIncidentId] = useState('')
  const [incidentUpdates, setIncidentUpdates] = useState([])
  const [claimStats, setClaimStats] = useState(null)
  const [claimFinance, setClaimFinance] = useState(null)
  const [autoEscalationResult, setAutoEscalationResult] = useState(null)

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
    amount_requested: '',
    claim_type: 'lost',
    proof_urls: '',
    reason: '',
  })
  const [claimUpdateForm, setClaimUpdateForm] = useState({
    claim_id: '',
    status: 'reviewing',
    amount_approved: '',
    resolution_note: '',
    refunded_payment_id: '',
  })

  const topRiskClaims = useMemo(() => {
    return [...claims]
      .filter((item) => item.risk_score !== null && item.risk_score !== undefined)
      .sort((a, b) => Number(b.risk_score || 0) - Number(a.risk_score || 0))
      .slice(0, 5)
  }, [claims])

  async function loadAll() {
    if (!token) return
    const [statusData, incidentData, claimData, statsData, financeData] = await Promise.all([
      listIncidentStatuses(token),
      listIncidents(token, filters),
      listClaims(token),
      getClaimsOpsStats(token, { staleHours: 24 }),
      getClaimsFinanceReport(token, { months: 6 }),
    ])
    setStatuses(statusData || [])
    setIncidents(incidentData || [])
    setClaims(claimData || [])
    setClaimStats(statsData || null)
    setClaimFinance(financeData || null)
    if (!selectedIncidentId && Array.isArray(incidentData) && incidentData.length > 0) {
      setSelectedIncidentId(incidentData[0].id)
    }
  }

  async function loadUpdates(incidentId) {
    if (!token || !incidentId) return
    const data = await listIncidentUpdates(token, incidentId)
    setIncidentUpdates(data || [])
  }

  useEffect(() => {
    loadAll().catch((err) => setError(err.message))
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
      setIncidents(data || [])
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
      await loadAll()
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
      await loadAll()
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
      const proofUrls = claimForm.proof_urls
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
      await createClaim(token, {
        incident_id: claimForm.incident_id,
        shipment_id: claimForm.shipment_id,
        amount_requested: Number(claimForm.amount_requested),
        claim_type: claimForm.claim_type,
        proof_urls: proofUrls,
        reason: claimForm.reason,
      })
      setMessage('Reclamation creee')
      setClaimForm({
        incident_id: '',
        shipment_id: '',
        amount_requested: '',
        claim_type: 'lost',
        proof_urls: '',
        reason: '',
      })
      await loadAll()
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
        amount_approved:
          claimUpdateForm.amount_approved === '' ? null : Number(claimUpdateForm.amount_approved),
        resolution_note: claimUpdateForm.resolution_note || null,
        refunded_payment_id: claimUpdateForm.refunded_payment_id || null,
      })
      setMessage('Statut reclamation mis a jour')
      setClaimUpdateForm({
        claim_id: '',
        status: 'reviewing',
        amount_approved: '',
        resolution_note: '',
        refunded_payment_id: '',
      })
      await loadAll()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onAutoEscalateClaims() {
    if (!isOpsRole) return
    setError('')
    setMessage('')
    try {
      const result = await autoEscalateClaims(token, {
        staleHours: 24,
        limit: 200,
        dryRun: false,
        notifyInternal: true,
      })
      setAutoEscalationResult(result)
      setMessage('Escalade SLA claims executee')
      await loadAll()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="page-grid">
      <article className="panel">
        <p className="eyebrow">Claims Control</p>
        <h2>Incidents, reclamations et risque fraude</h2>
        <p>
          Vue unifiee pour declaration, traitement SLA, anti-fraude et suivi financier assurance.
        </p>
      </article>

      <section className="kpi-grid">
        <article className="kpi-card">
          <p>Claims total</p>
          <h3>{claimStats?.total ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>Claims en attente</p>
          <h3>{claimStats?.pending ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>En retard SLA</p>
          <h3>{claimStats?.pending_over_sla ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>Montant approuve</p>
          <h3>{claimStats?.approved_total ?? '-'}</h3>
        </article>
      </section>

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
              Type claim
              <select
                value={claimForm.claim_type}
                onChange={(e) => setClaimForm((s) => ({ ...s, claim_type: e.target.value }))}
              >
                <option value="lost">lost</option>
                <option value="damaged">damaged</option>
                <option value="partial_loss">partial_loss</option>
                <option value="other">other</option>
              </select>
            </label>
            <label>
              Montant demande (BIF)
              <input
                type="number"
                min="1"
                step="0.01"
                value={claimForm.amount_requested}
                onChange={(e) => setClaimForm((s) => ({ ...s, amount_requested: e.target.value }))}
                required
              />
            </label>
            <label>
              Preuves (URLs, separees par virgule)
              <input
                value={claimForm.proof_urls}
                onChange={(e) => setClaimForm((s) => ({ ...s, proof_urls: e.target.value }))}
                placeholder="https://... , https://..."
              />
            </label>
            <label>
              Motif
              <input
                value={claimForm.reason}
                onChange={(e) => setClaimForm((s) => ({ ...s, reason: e.target.value }))}
                required
              />
            </label>
            <button type="submit">Creer reclamation</button>
          </form>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Pilotage incidents</h3>
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
            <button type="submit">Appliquer filtres</button>
          </form>
          <div className="relay-list" style={{ marginTop: '12px' }}>
            {incidents.length === 0 ? <p>Aucun incident</p> : null}
            {incidents.map((incident) => (
              <div key={incident.id} className="relay-item">
                <p>
                  <strong>{incident.incident_type}</strong> | statut: {incident.status}
                </p>
                <p>shipment: {incident.shipment_id}</p>
                <p>{incident.description}</p>
                <button type="button" onClick={() => setSelectedIncidentId(incident.id)}>
                  Ouvrir dossier
                </button>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h3>Workflow dossier incident</h3>
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
              Journal interne
              <input
                value={updateForm.message}
                onChange={(e) => setUpdateForm((s) => ({ ...s, message: e.target.value }))}
              />
            </label>
            <button type="submit" disabled={!selectedIncidentId || !updateForm.message}>
              Ajouter note
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
          <h3>File reclamations</h3>
          {isOpsRole ? (
            <div className="ops-actions" style={{ marginBottom: '10px' }}>
              <button type="button" onClick={onAutoEscalateClaims}>
                Escalader claims en retard (SLA)
              </button>
            </div>
          ) : null}
          {autoEscalationResult ? (
            <p>
              escalated: {autoEscalationResult.escalated} | notified:{' '}
              {autoEscalationResult.notified_recipients}
            </p>
          ) : null}
          <div className="relay-list">
            {claims.length === 0 ? <p>Aucune reclamation</p> : null}
            {claims.map((claim) => (
              <div key={claim.id} className="relay-item">
                <p>
                  <strong>{claim.status}</strong> | {claim.claim_type || '-'} | req:{' '}
                  {claim.amount_requested ?? claim.amount}
                </p>
                <p>approved: {claim.amount_approved ?? '-'} | risk: {claim.risk_score ?? '-'}</p>
                {Array.isArray(claim.risk_flags) && claim.risk_flags.length > 0 ? (
                  <p>flags: {claim.risk_flags.join(', ')}</p>
                ) : null}
                <p>{claim.reason}</p>
                <p>{claim.created_at}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h3>Traitement reclamation</h3>
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
              Statut
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
              Montant approuve (optionnel)
              <input
                type="number"
                min="0"
                step="0.01"
                value={claimUpdateForm.amount_approved}
                onChange={(e) => setClaimUpdateForm((s) => ({ ...s, amount_approved: e.target.value }))}
              />
            </label>
            <label>
              Note resolution
              <input
                value={claimUpdateForm.resolution_note}
                onChange={(e) => setClaimUpdateForm((s) => ({ ...s, resolution_note: e.target.value }))}
              />
            </label>
            <label>
              Ref paiement remboursement (optionnel)
              <input
                value={claimUpdateForm.refunded_payment_id}
                onChange={(e) =>
                  setClaimUpdateForm((s) => ({ ...s, refunded_payment_id: e.target.value }))
                }
              />
            </label>
            <button type="submit">Mettre a jour reclamation</button>
          </form>

          <h3 style={{ marginTop: '12px' }}>Top risque fraude</h3>
          <div className="relay-list">
            {topRiskClaims.length === 0 ? <p>Aucun signal risque</p> : null}
            {topRiskClaims.map((claim) => (
              <div key={claim.id} className="relay-item">
                <p>
                  <strong>risk {claim.risk_score}</strong> | status {claim.status}
                </p>
                <p>{claim.id}</p>
                <p>{Array.isArray(claim.risk_flags) ? claim.risk_flags.join(', ') : '-'}</p>
              </div>
            ))}
          </div>
        </article>
      </section>

      <article className="panel">
        <h3>Finance assurance (6 mois)</h3>
        <div className="relay-list">
          {Array.isArray(claimFinance?.points) && claimFinance.points.length > 0 ? (
            claimFinance.points.map((point) => (
              <div key={point.month} className="relay-item">
                <p>
                  <strong>{point.month}</strong> | primes: {point.premiums_collected} | paid:{' '}
                  {point.claims_paid}
                </p>
                <p>
                  requested: {point.claims_requested} | approved: {point.claims_approved} | margin:{' '}
                  {point.margin} | loss ratio: {point.loss_ratio_pct}%
                </p>
              </div>
            ))
          ) : (
            <p>Aucune donnee finance assurance.</p>
          )}
        </div>
      </article>

      {message ? <p className="status-line">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
