import { useEffect, useMemo, useState } from 'react'
import {
  assignAgentToRelay,
  createRelay,
  deleteRelay,
  getRelayCapacity,
  listRelayAgents,
  listRelayInventory,
  listRelays,
  listUsers,
  unassignAgentFromRelay,
  upsertRelayInventory,
  updateRelay,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'

const emptyRelayForm = {
  relay_code: '',
  name: '',
  type: 'relay',
  opening_hours: '',
  storage_capacity: '',
  is_active: true,
}

export default function RelaysPage() {
  const { token } = useAuth()
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

  const selectedRelay = useMemo(
    () => relays.find((relay) => relay.id === selectedRelayId) || null,
    [relays, selectedRelayId],
  )

  async function loadRelaysAndAgents() {
    if (!token) return
    const [relayData, agentData] = await Promise.all([listRelays(token), listUsers(token, 'agent')])
    setRelays(relayData)
    setAgents(agentData)
    if (!selectedRelayId && relayData.length > 0) setSelectedRelayId(relayData[0].id)
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    loadRelayAgents(selectedRelayId).catch((err) => setError(err.message))
    loadRelayInventory(selectedRelayId).catch((err) => setError(err.message))
    loadRelayCapacity(selectedRelayId).catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRelayId, token])

  function resetRelayForm() {
    setRelayForm(emptyRelayForm)
    setEditingRelayId('')
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
        <p>CRUD relais + rattachement des agents + capacite/horaires.</p>
      </article>

      <section className="page-grid two-cols">
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
              <input
                value={relayForm.name}
                onChange={(e) => setRelayForm((s) => ({ ...s, name: e.target.value }))}
                required
              />
            </label>
            <label>
              Type
              <input
                value={relayForm.type}
                onChange={(e) => setRelayForm((s) => ({ ...s, type: e.target.value }))}
                required
              />
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

        <article className="panel">
          <h3>Relais existants</h3>
          <div className="relay-list">
            {relays.length === 0 ? <p>Aucun relais</p> : null}
            {relays.map((relay) => (
              <div key={relay.id} className="relay-item">
                <p>
                  <strong>{relay.name}</strong> ({relay.relay_code})
                </p>
                <p>
                  {relay.type} | {relay.opening_hours || 'Horaires non definis'} | Cap:{' '}
                  {relay.storage_capacity ?? '-'} | {relay.is_active ? 'Actif' : 'Inactif'}
                </p>
                <div className="ops-actions">
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
            <strong>{relayCapacity?.current_present ?? '-'}</strong> | dispo:{' '}
            <strong>{relayCapacity?.available ?? '-'}</strong> | plein:{' '}
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
                  status colis: {row.shipment_status || '-'} | present: {row.present ? 'oui' : 'non'}
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
