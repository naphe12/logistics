import { useEffect, useMemo, useRef, useState } from 'react'
import {
  assignAgentToRelay,
  createRelay,
  createRelayManagerApplication,
  deleteRelay,
  getRelayCapacity,
  listCommunes,
  listProvinces,
  listRelayAgents,
  listRelayInventory,
  listRelayManagerApplications,
  listRelays,
  listUsers,
  reviewRelayManagerApplication,
  unassignAgentFromRelay,
  upsertRelayInventory,
  updateRelay,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { humanizeStatus } from '../utils/display'

const emptyRelayForm = {
  relay_code: '',
  name: '',
  type: 'relay',
  opening_hours: '',
  storage_capacity: '',
  is_active: true,
}

const initialRelayFilters = {
  q: '',
  province_id: '',
  commune_id: '',
  operational_status: '',
}

const initialManagerForm = {
  relay_id: '',
  manager_name: '',
  manager_phone: '',
  manager_email: '',
  notes: '',
}

function relayStatusLabel(status) {
  if (status === 'open') return 'Ouvert'
  if (status === 'full') return 'Complet'
  return 'Ferme'
}

export default function RelaysPage() {
  const { token } = useAuth()
  const mapRef = useRef(null)
  const markerLayerRef = useRef(null)

  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [relays, setRelays] = useState([])
  const [agents, setAgents] = useState([])
  const [selectedRelayId, setSelectedRelayId] = useState('')
  const [relayAgents, setRelayAgents] = useState([])
  const [relayInventory, setRelayInventory] = useState([])
  const [relayCapacity, setRelayCapacity] = useState(null)
  const [relayForm, setRelayForm] = useState(emptyRelayForm)
  const [editingRelayId, setEditingRelayId] = useState('')
  const [assignAgentId, setAssignAgentId] = useState('')
  const [inventoryForm, setInventoryForm] = useState({ shipment_id: '', present: true })
  const [relayFilters, setRelayFilters] = useState(initialRelayFilters)
  const [provinces, setProvinces] = useState([])
  const [communes, setCommunes] = useState([])
  const [managerForm, setManagerForm] = useState(initialManagerForm)
  const [managerApplications, setManagerApplications] = useState([])

  const selectedRelay = useMemo(
    () => relays.find((relay) => relay.id === selectedRelayId) || null,
    [relays, selectedRelayId],
  )

  async function loadRelaysAndAgents(filters = relayFilters) {
    if (!token) return
    const [relayData, agentData] = await Promise.all([
      listRelays(token, {
        q: filters.q,
        provinceId: filters.province_id,
        communeId: filters.commune_id,
        operationalStatus: filters.operational_status,
      }),
      listUsers(token, 'agent'),
    ])
    setRelays(Array.isArray(relayData) ? relayData : [])
    setAgents(Array.isArray(agentData) ? agentData : [])
    if (!selectedRelayId && relayData.length > 0) setSelectedRelayId(relayData[0].id)
  }

  async function loadGeoOptions() {
    if (!token) return
    const [provinceRows, communeRows] = await Promise.all([
      listProvinces(token, { limit: 200 }),
      listCommunes(token, { limit: 500 }),
    ])
    setProvinces(Array.isArray(provinceRows) ? provinceRows : [])
    setCommunes(Array.isArray(communeRows) ? communeRows : [])
  }

  async function loadManagerApplications() {
    if (!token) return
    const rows = await listRelayManagerApplications(token, { limit: 200 })
    setManagerApplications(Array.isArray(rows) ? rows : [])
  }

  async function loadRelayAgents(relayId) {
    if (!token || !relayId) return
    const data = await listRelayAgents(token, relayId)
    setRelayAgents(data)
  }

  async function loadRelayInventory(relayId) {
    if (!token || !relayId) return
    const data = await listRelayInventory(token, relayId, false)
    setRelayInventory(data)
  }

  async function loadRelayCapacity(relayId) {
    if (!token || !relayId) return
    const data = await getRelayCapacity(token, relayId)
    setRelayCapacity(data)
  }

  useEffect(() => {
    loadRelaysAndAgents().catch((err) => setError(err.message))
    loadGeoOptions().catch((err) => setError(err.message))
    loadManagerApplications().catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    loadRelayAgents(selectedRelayId).catch((err) => setError(err.message))
    loadRelayInventory(selectedRelayId).catch((err) => setError(err.message))
    loadRelayCapacity(selectedRelayId).catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRelayId, token])

  useEffect(() => {
    let cancelled = false

    const ensureLeaflet = async () => {
      if (window.L) return window.L
      if (!document.getElementById('leaflet-css')) {
        const link = document.createElement('link')
        link.id = 'leaflet-css'
        link.rel = 'stylesheet'
        link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
        document.head.appendChild(link)
      }
      await new Promise((resolve, reject) => {
        const existing = document.getElementById('leaflet-js')
        if (existing) {
          existing.addEventListener('load', resolve, { once: true })
          existing.addEventListener('error', reject, { once: true })
          return
        }
        const script = document.createElement('script')
        script.id = 'leaflet-js'
        script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
        script.async = true
        script.onload = resolve
        script.onerror = reject
        document.body.appendChild(script)
      })
      return window.L
    }

    ensureLeaflet()
      .then((L) => {
        if (cancelled || !L || !mapRef.current) return
        if (!mapRef.current.__leaflet) {
          const map = L.map(mapRef.current).setView([-3.3731, 29.9189], 7)
          L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
          }).addTo(map)
          markerLayerRef.current = L.layerGroup().addTo(map)
          mapRef.current.__leaflet = map
        }
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de charger la carte interactive')
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const L = window.L
    const map = mapRef.current?.__leaflet
    if (!L || !map || !markerLayerRef.current) return

    markerLayerRef.current.clearLayers()
    const pointRelays = relays.filter((row) => Number.isFinite(Number(row.latitude)) && Number.isFinite(Number(row.longitude)))
    for (const relay of pointRelays) {
      const color = relay.operational_status === 'open' ? '#16a34a' : relay.operational_status === 'full' ? '#d97706' : '#b42318'
      const marker = L.circleMarker([Number(relay.latitude), Number(relay.longitude)], {
        radius: 7,
        color,
        fillColor: color,
        fillOpacity: 0.8,
      })
      marker.bindPopup(
        `<strong>${relay.name || '-'}</strong><br/>` +
          `Code: ${relay.relay_code || '-'}<br/>` +
          `Statut: ${relayStatusLabel(relay.operational_status)}<br/>` +
          `Capacite: ${relay.current_present ?? 0}/${relay.storage_capacity ?? '8'}<br/>` +
          `Contact: ${relay.manager_phone || '-'}<br/>` +
          `${relay.landmark || ''}`,
      )
      marker.on('click', () => setSelectedRelayId(relay.id))
      markerLayerRef.current.addLayer(marker)
    }
    if (pointRelays.length > 0) {
      const bounds = L.latLngBounds(pointRelays.map((r) => [Number(r.latitude), Number(r.longitude)]))
      map.fitBounds(bounds.pad(0.2))
    }
  }, [relays])

  function resetRelayForm() {
    setRelayForm(emptyRelayForm)
    setEditingRelayId('')
  }

  async function onApplyRelayFilters(e) {
    e.preventDefault()
    setError('')
    await loadRelaysAndAgents(relayFilters)
  }

  async function onResetRelayFilters() {
    setRelayFilters(initialRelayFilters)
    setError('')
    await loadRelaysAndAgents(initialRelayFilters)
  }

  async function onCreateOrUpdateRelay(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      const payload = {
        relay_code: relayForm.relay_code,
        name: relayForm.name,
        type: relayForm.type,
        opening_hours: relayForm.opening_hours || null,
        storage_capacity: relayForm.storage_capacity === '' ? null : Number(relayForm.storage_capacity),
        is_active: Boolean(relayForm.is_active),
      }
      if (editingRelayId) {
        await updateRelay(token, editingRelayId, payload)
        setMessage('Relais mis a jour')
      } else {
        await createRelay(token, payload)
        setMessage('Relais cree')
      }
      resetRelayForm()
      await loadRelaysAndAgents()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onCreateManagerApplication(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      await createRelayManagerApplication(token, {
        relay_id: managerForm.relay_id || null,
        manager_name: managerForm.manager_name,
        manager_phone: managerForm.manager_phone,
        manager_email: managerForm.manager_email || null,
        notes: managerForm.notes || null,
      })
      setManagerForm(initialManagerForm)
      setMessage('Candidature gerant enregistree')
      await loadManagerApplications()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onReviewManagerApplication(app, status) {
    setError('')
    setMessage('')
    try {
      await reviewRelayManagerApplication(token, app.id, {
        status,
        training_completed: status === 'trained',
        notes: app.notes || null,
      })
      setMessage('Candidature mise a jour')
      await loadManagerApplications()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onDeleteRelay(relayId) {
    setError('')
    setMessage('')
    try {
      await deleteRelay(token, relayId)
      setMessage('Relais supprime')
      if (selectedRelayId === relayId) setSelectedRelayId('')
      await loadRelaysAndAgents()
    } catch (err) {
      setError(err.message)
    }
  }

  function onEditRelay(relay) {
    setEditingRelayId(relay.id)
    setRelayForm({
      relay_code: relay.relay_code || '',
      name: relay.name || '',
      type: relay.type || 'relay',
      opening_hours: relay.opening_hours || '',
      storage_capacity: relay.storage_capacity ?? '',
      is_active: relay.is_active,
    })
  }

  async function onAssignAgent(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (!selectedRelayId || !assignAgentId) return
    try {
      await assignAgentToRelay(token, selectedRelayId, assignAgentId)
      setMessage('Agent rattache au relais')
      setAssignAgentId('')
      await loadRelayAgents(selectedRelayId)
      await loadRelaysAndAgents()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onUnassignAgent(userId) {
    setError('')
    setMessage('')
    if (!selectedRelayId) return
    try {
      await unassignAgentFromRelay(token, selectedRelayId, userId)
      setMessage('Agent detache du relais')
      await loadRelayAgents(selectedRelayId)
      await loadRelaysAndAgents()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onUpsertInventory(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (!selectedRelayId) return
    try {
      await upsertRelayInventory(token, selectedRelayId, {
        shipment_id: inventoryForm.shipment_id,
        present: inventoryForm.present,
      })
      setMessage('Inventaire relais mis a jour')
      setInventoryForm({ shipment_id: '', present: true })
      await loadRelayInventory(selectedRelayId)
      await loadRelayCapacity(selectedRelayId)
      await loadRelaysAndAgents()
    } catch (err) {
      setError(err.message)
    }
  }

  const unassignedAgents = agents.filter((agent) => !agent.relay_id)

  return (
    <section className="page-grid">
      <article className="panel">
        <p className="eyebrow">Admin</p>
        <h2>Gestion des relais</h2>
        <p>CRUD relais + carte interactive + statut temps reel + onboarding des gerants.</p>
      </article>

      <article className="panel">
        <h3>Carte interactive des points</h3>
        <div ref={mapRef} style={{ height: 360, borderRadius: 12, overflow: 'hidden' }} />
      </article>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Recherche points depot/retrait</h3>
          <form className="form" onSubmit={onApplyRelayFilters}>
            <label>
              Recherche (nom, code, quartier/commune)
              <input
                value={relayFilters.q}
                onChange={(e) => setRelayFilters((s) => ({ ...s, q: e.target.value }))}
                placeholder="Ngagara, centre, RP-001"
              />
            </label>
            <label>
              Province
              <select
                value={relayFilters.province_id}
                onChange={(e) => setRelayFilters((s) => ({ ...s, province_id: e.target.value }))}
              >
                <option value="">Toutes</option>
                {provinces.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Commune
              <select
                value={relayFilters.commune_id}
                onChange={(e) => setRelayFilters((s) => ({ ...s, commune_id: e.target.value }))}
              >
                <option value="">Toutes</option>
                {communes.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Statut operationnel
              <select
                value={relayFilters.operational_status}
                onChange={(e) => setRelayFilters((s) => ({ ...s, operational_status: e.target.value }))}
              >
                <option value="">Tous</option>
                <option value="open">Ouvert</option>
                <option value="full">Complet</option>
                <option value="closed">Ferme</option>
              </select>
            </label>
            <div className="ops-actions">
              <button type="submit">Appliquer filtres</button>
              <button type="button" className="button-secondary" onClick={onResetRelayFilters}>
                Reinitialiser
              </button>
            </div>
          </form>
        </article>

        <article className="panel">
          <h3>{editingRelayId ? 'Modifier relais' : 'Nouveau relais'}</h3>
          <form className="form" onSubmit={onCreateOrUpdateRelay}>
            <label>
              Code relais
              <input
                value={relayForm.relay_code}
                onChange={(e) => setRelayForm((s) => ({ ...s, relay_code: e.target.value }))}
                required
              />
            </label>
            <label>
              Nom
              <input value={relayForm.name} onChange={(e) => setRelayForm((s) => ({ ...s, name: e.target.value }))} required />
            </label>
            <label>
              Type
              <input value={relayForm.type} onChange={(e) => setRelayForm((s) => ({ ...s, type: e.target.value }))} required />
            </label>
            <label>
              Horaires
              <input
                placeholder="Lun-Sam 08:00-18:00"
                value={relayForm.opening_hours}
                onChange={(e) => setRelayForm((s) => ({ ...s, opening_hours: e.target.value }))}
              />
            </label>
            <label>
              Capacite stockage
              <input
                type="number"
                min="0"
                value={relayForm.storage_capacity}
                onChange={(e) => setRelayForm((s) => ({ ...s, storage_capacity: e.target.value }))}
              />
            </label>
            <label>
              Actif
              <select
                value={relayForm.is_active ? 'true' : 'false'}
                onChange={(e) => setRelayForm((s) => ({ ...s, is_active: e.target.value === 'true' }))}
              >
                <option value="true">Oui</option>
                <option value="false">Non</option>
              </select>
            </label>
            <div className="ops-actions">
              <button type="submit">{editingRelayId ? 'Mettre a jour' : 'Creer relais'}</button>
              {editingRelayId ? (
                <button type="button" className="button-secondary" onClick={resetRelayForm}>
                  Annuler edition
                </button>
              ) : null}
            </div>
          </form>
        </article>
      </section>

      <article className="panel">
        <h3>Relais existants</h3>
        <div className="premium-table-wrap">
          {relays.length === 0 ? (
            <p>Aucun relais</p>
          ) : (
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Relais</th>
                  <th>Type</th>
                  <th>Zone</th>
                  <th>Horaires</th>
                  <th>Capacite</th>
                  <th>Etat</th>
                  <th>Statut temps reel</th>
                  <th>Contact</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {relays.map((relay) => (
                  <tr key={relay.id}>
                    <td>
                      <strong>{relay.name || '-'}</strong>
                      <br />
                      <span className="mono">{relay.relay_code || '-'}</span>
                    </td>
                    <td>{relay.type || '-'}</td>
                    <td>{[relay.quartier, relay.commune_name, relay.province_name].filter(Boolean).join(', ') || '-'}</td>
                    <td>{relay.opening_hours || 'Horaires non definis'}</td>
                    <td>{relay.storage_capacity ?? '-'}</td>
                    <td>
                      <span className={`badge ${relay.is_active ? 'success' : 'danger'}`}>{relay.is_active ? 'Actif' : 'Inactif'}</span>
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          relay.operational_status === 'open'
                            ? 'success'
                            : relay.operational_status === 'full'
                              ? 'warning'
                              : 'danger'
                        }`}
                      >
                        {relayStatusLabel(relay.operational_status)}
                      </span>
                      <p className="muted-note" style={{ marginTop: 6 }}>
                        {relay.current_present ?? 0}/{relay.storage_capacity ?? '8'} | dispo {relay.available ?? '-'}
                      </p>
                    </td>
                    <td>{relay.manager_phone || '-'}</td>
                    <td>
                      <div className="table-actions">
                        <button type="button" onClick={() => setSelectedRelayId(relay.id)}>
                          Selectionner
                        </button>
                        <button type="button" className="button-secondary" onClick={() => onEditRelay(relay)}>
                          Editer
                        </button>
                        <button type="button" onClick={() => onDeleteRelay(relay.id)}>
                          Supprimer
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

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Onboarding gerant de point</h3>
          <form className="form" onSubmit={onCreateManagerApplication}>
            <label>
              Point relais
              <select
                value={managerForm.relay_id}
                onChange={(e) => setManagerForm((s) => ({ ...s, relay_id: e.target.value }))}
              >
                <option value="">Selectionner</option>
                {relays.map((relay) => (
                  <option key={relay.id} value={relay.id}>
                    {relay.name} ({relay.relay_code})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Nom gerant
              <input
                value={managerForm.manager_name}
                onChange={(e) => setManagerForm((s) => ({ ...s, manager_name: e.target.value }))}
                required
              />
            </label>
            <label>
              Telephone
              <input
                value={managerForm.manager_phone}
                onChange={(e) => setManagerForm((s) => ({ ...s, manager_phone: e.target.value }))}
                required
              />
            </label>
            <label>
              Email (optionnel)
              <input
                value={managerForm.manager_email}
                onChange={(e) => setManagerForm((s) => ({ ...s, manager_email: e.target.value }))}
              />
            </label>
            <label>
              Notes
              <textarea
                rows={3}
                value={managerForm.notes}
                onChange={(e) => setManagerForm((s) => ({ ...s, notes: e.target.value }))}
              />
            </label>
            <button type="submit">Enregistrer candidature</button>
          </form>
        </article>

        <article className="panel">
          <h3>Candidatures gerants</h3>
          <div className="relay-list list-scroll">
            {managerApplications.length === 0 ? <p>Aucune candidature</p> : null}
            {managerApplications.map((app) => (
              <div key={app.id} className="relay-item">
                <p>
                  <strong>{app.manager_name}</strong> | {app.manager_phone}
                </p>
                <p>
                  statut: <span className="mono">{app.status}</span> | formation: {app.training_completed ? 'oui' : 'non'}
                </p>
                <div className="table-actions">
                  <button type="button" onClick={() => onReviewManagerApplication(app, 'validated')}>
                    Valider
                  </button>
                  <button type="button" className="button-secondary" onClick={() => onReviewManagerApplication(app, 'training_in_progress')}>
                    Formation
                  </button>
                  <button type="button" onClick={() => onReviewManagerApplication(app, 'trained')}>
                    Marquer forme
                  </button>
                  <button type="button" onClick={() => onReviewManagerApplication(app, 'rejected')}>
                    Rejeter
                  </button>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Rattacher agent</h3>
          <p>
            Relais selectionne: <strong>{selectedRelay ? selectedRelay.name : '-'}</strong>
          </p>
          <form className="form" onSubmit={onAssignAgent}>
            <label>
              Agent non assigne
              <select value={assignAgentId} onChange={(e) => setAssignAgentId(e.target.value)}>
                <option value="">Choisir un agent</option>
                {unassignedAgents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.phone_e164} ({agent.id})
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={!selectedRelayId || !assignAgentId}>
              Rattacher
            </button>
          </form>
        </article>

        <article className="panel">
          <h3>Agents du relais</h3>
          <div className="relay-list">
            {relayAgents.length === 0 ? <p>Aucun agent rattache</p> : null}
            {relayAgents.map((agent) => (
              <div key={agent.id} className="relay-item">
                <p>
                  <strong>{agent.phone_e164}</strong>
                </p>
                <p>
                  {agent.first_name || '-'} {agent.last_name || '-'}
                </p>
                <button type="button" onClick={() => onUnassignAgent(agent.id)}>
                  Detacher
                </button>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Inventaire relais</h3>
          <p>
            Capacite: <strong>{relayCapacity?.storage_capacity ?? 'illimitee'}</strong> | present:{' '}
            <strong>{relayCapacity?.current_present ?? '-'}</strong> | dispo: <strong>{relayCapacity?.available ?? '-'}</strong> | plein:{' '}
            <strong>{relayCapacity?.is_full ? 'oui' : 'non'}</strong>
          </p>
          <form className="form" onSubmit={onUpsertInventory}>
            <label>
              Shipment ID
              <input
                value={inventoryForm.shipment_id}
                onChange={(e) => setInventoryForm((s) => ({ ...s, shipment_id: e.target.value }))}
                required
              />
            </label>
            <label>
              Present au relais
              <select
                value={inventoryForm.present ? 'true' : 'false'}
                onChange={(e) => setInventoryForm((s) => ({ ...s, present: e.target.value === 'true' }))}
              >
                <option value="true">Oui</option>
                <option value="false">Non</option>
              </select>
            </label>
            <button type="submit" disabled={!selectedRelayId}>
              Upsert inventaire
            </button>
          </form>
        </article>

        <article className="panel">
          <h3>Lignes inventaire</h3>
          <div className="relay-list">
            {relayInventory.length === 0 ? <p>Aucune ligne inventaire</p> : null}
            {relayInventory.map((row) => (
              <div key={row.id} className="relay-item">
                <p>
                  <strong>{row.shipment_no || row.shipment_id}</strong>
                </p>
                <p>
                  status colis: {humanizeStatus(row.shipment_status)} | present: {row.present ? 'oui' : 'non'}
                </p>
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
