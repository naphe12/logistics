import { useEffect, useMemo, useState } from 'react'
import {
  createShipment,
  getMyShippingPreferences,
  getRelayCapacity,
  getShipmentInsurancePolicy,
  getShipmentInsuranceQuote,
  getShipmentPriceEstimate,
  listMyShipmentsSlaSummary,
  listRelays,
  updateMyShippingPreferences,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { formatDateTime, humanizeStatus } from '../utils/display'

const initialForm = {
  sender_phone: '',
  receiver_name: '',
  receiver_phone: '',
  origin_relay_id: '',
  destination_relay_id: '',
  delivery_note: '',
  declared_value: '',
  insurance_opt_in: false,
}

const initialShippingPrefs = {
  preferred_relay_id: '',
  use_preferred_relay: false,
}

function slaBadgeClass(state) {
  if (state === 'late') return 'danger'
  if (state === 'at_risk') return 'warning'
  if (state === 'on_track') return 'success'
  return 'info'
}

export default function ShipmentsPage() {
  const { token, dashboardRole, userProfile } = useAuth()
  const isClient = dashboardRole === 'client'

  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [createdShipment, setCreatedShipment] = useState(null)
  const [form, setForm] = useState(initialForm)
  const [relays, setRelays] = useState([])
  const [relaySearch, setRelaySearch] = useState('')
  const [relayCapacityById, setRelayCapacityById] = useState({})
  const [shippingPrefs, setShippingPrefs] = useState(initialShippingPrefs)
  const [savingPrefs, setSavingPrefs] = useState(false)
  const [insuranceQuote, setInsuranceQuote] = useState(null)
  const [insurancePolicy, setInsurancePolicy] = useState(null)
  const [priceEstimate, setPriceEstimate] = useState(null)
  const [clientSlaItems, setClientSlaItems] = useState([])
  const [loadingClientShipments, setLoadingClientShipments] = useState(false)
  const [lateOnlyFilter, setLateOnlyFilter] = useState(false)
  const [clientListSort, setClientListSort] = useState('created_at_desc')
  const [loadingQuote, setLoadingQuote] = useState(false)
  const [loadingPriceEstimate, setLoadingPriceEstimate] = useState(false)
  const [loadingRelayMeta, setLoadingRelayMeta] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [reloadClientListTick, setReloadClientListTick] = useState(0)

  const canUseInsuranceQuote = Number(form.declared_value || 0) >= 0

  const selectedOrigin = useMemo(
    () => relays.find((relay) => relay.id === form.origin_relay_id),
    [relays, form.origin_relay_id],
  )
  const selectedDestination = useMemo(
    () => relays.find((relay) => relay.id === form.destination_relay_id),
    [relays, form.destination_relay_id],
  )

  const filteredRelays = useMemo(() => {
    const query = relaySearch.trim().toLowerCase()
    const base = relays.filter((relay) => relay.is_active)
    if (!query) return base
    return base.filter((relay) => {
      const name = String(relay.name || '').toLowerCase()
      const code = String(relay.relay_code || '').toLowerCase()
      const type = String(relay.type || '').toLowerCase()
      return name.includes(query) || code.includes(query) || type.includes(query)
    })
  }, [relays, relaySearch])

  const recommendedDestination = useMemo(() => {
    const candidates = filteredRelays
      .map((relay) => ({ relay, cap: relayCapacityById[relay.id] || null }))
      .filter((item) => !item.cap || item.cap.is_full !== true)
      .sort((a, b) => {
        const aUtil = a.cap?.utilization_ratio ?? 0
        const bUtil = b.cap?.utilization_ratio ?? 0
        const aAvail = a.cap?.available ?? 999999
        const bAvail = b.cap?.available ?? 999999
        if (aUtil !== bUtil) return aUtil - bUtil
        return bAvail - aAvail
      })
    return candidates.length > 0 ? candidates[0] : null
  }, [filteredRelays, relayCapacityById])
  const sortedClientSlaItems = useMemo(() => {
    const rows = [...clientSlaItems]
    if (clientListSort === 'sla_priority') {
      const score = { late: 3, at_risk: 2, on_track: 1 }
      rows.sort((a, b) => {
        const bySeverity = (score[b.sla_state] || 0) - (score[a.sla_state] || 0)
        if (bySeverity !== 0) return bySeverity
        return Number(a.remaining_sla_hours || 0) - Number(b.remaining_sla_hours || 0)
      })
      return rows
    }
    rows.sort((a, b) => {
      const ad = new Date(a.created_at || 0).getTime()
      const bd = new Date(b.created_at || 0).getTime()
      return clientListSort === 'created_at_asc' ? ad - bd : bd - ad
    })
    return rows
  }, [clientSlaItems, clientListSort])

  useEffect(() => {
    if (!token) return
    async function loadReference() {
      const promises = [listRelays(token), getShipmentInsurancePolicy(token)]
      if (isClient) promises.push(getMyShippingPreferences(token))
      const [relayData, policy, prefs] = await Promise.all(promises)

      const relayRows = Array.isArray(relayData) ? relayData : []
      setRelays(relayRows)
      setInsurancePolicy(policy || null)

      if (isClient && prefs) {
        setShippingPrefs({
          preferred_relay_id: prefs.preferred_relay_id || '',
          use_preferred_relay: Boolean(prefs.use_preferred_relay),
        })
      }

      const activeRelays = relayRows.filter((relay) => relay.is_active)
      setLoadingRelayMeta(true)
      try {
        const rows = await Promise.all(
          activeRelays.map(async (relay) => {
            try {
              const cap = await getRelayCapacity(token, relay.id)
              return [relay.id, cap]
            } catch {
              return [relay.id, null]
            }
          }),
        )
        setRelayCapacityById(Object.fromEntries(rows))
      } finally {
        setLoadingRelayMeta(false)
      }
    }
    loadReference().catch((err) => setError(err.message))
  }, [token, isClient])

  useEffect(() => {
    if (!isClient || !shippingPrefs.use_preferred_relay || !shippingPrefs.preferred_relay_id) return
    setForm((prev) => {
      if (prev.origin_relay_id || prev.destination_relay_id) return prev
      return {
        ...prev,
        origin_relay_id: shippingPrefs.preferred_relay_id,
        destination_relay_id: shippingPrefs.preferred_relay_id,
      }
    })
  }, [isClient, shippingPrefs.use_preferred_relay, shippingPrefs.preferred_relay_id])

  useEffect(() => {
    if (!token || !canUseInsuranceQuote) {
      setInsuranceQuote(null)
      return
    }
    const timer = setTimeout(async () => {
      setLoadingQuote(true)
      try {
        const quote = await getShipmentInsuranceQuote(token, {
          declaredValue: Number(form.declared_value || 0),
          insuranceOptIn: Boolean(form.insurance_opt_in),
        })
        setInsuranceQuote(quote || null)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoadingQuote(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [token, form.declared_value, form.insurance_opt_in, canUseInsuranceQuote])

  useEffect(() => {
    if (!token || !form.origin_relay_id || !form.destination_relay_id) {
      setPriceEstimate(null)
      return
    }
    const timer = setTimeout(async () => {
      setLoadingPriceEstimate(true)
      try {
        const estimate = await getShipmentPriceEstimate(token, {
          originRelayId: form.origin_relay_id,
          destinationRelayId: form.destination_relay_id,
          declaredValue: form.declared_value === '' ? null : Number(form.declared_value),
          insuranceOptIn: Boolean(form.insurance_opt_in),
        })
        setPriceEstimate(estimate || null)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoadingPriceEstimate(false)
      }
    }, 250)
    return () => clearTimeout(timer)
  }, [token, form.origin_relay_id, form.destination_relay_id, form.declared_value, form.insurance_opt_in])

  useEffect(() => {
    if (!token || !isClient) return
    async function loadClientShipments() {
      setLoadingClientShipments(true)
      try {
        const page = await listMyShipmentsSlaSummary(token, {
          direction: 'all',
          sort: clientListSort === 'created_at_asc' ? 'created_at_asc' : 'created_at_desc',
          late_only: lateOnlyFilter,
          limit: 12,
        })
        setClientSlaItems(Array.isArray(page?.items) ? page.items : [])
      } finally {
        setLoadingClientShipments(false)
      }
    }
    loadClientShipments().catch((err) => setError(err.message))
  }, [token, isClient, reloadClientListTick, lateOnlyFilter, clientListSort])

  async function onSaveShippingPreferences(e) {
    if (e?.preventDefault) e.preventDefault()
    if (!token || !isClient) return
    setSavingPrefs(true)
    setError('')
    setMessage('')
    try {
      const saved = await updateMyShippingPreferences(token, {
        preferred_relay_id: shippingPrefs.preferred_relay_id || null,
        use_preferred_relay: Boolean(shippingPrefs.use_preferred_relay),
      })
      setShippingPrefs({
        preferred_relay_id: saved.preferred_relay_id || '',
        use_preferred_relay: Boolean(saved.use_preferred_relay),
      })
      setMessage('Relais prefere enregistre.')
    } catch (err) {
      setError(err.message)
    } finally {
      setSavingPrefs(false)
    }
  }

  async function onSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setMessage('')
    setCreatedShipment(null)
    try {
      const destinationCapacity = relayCapacityById[form.destination_relay_id]
      if (destinationCapacity?.is_full) {
        setError('Le point relais destination est plein. Selectionne un autre point.')
        return
      }

      const payload = {
        sender_phone: form.sender_phone.trim(),
        receiver_name: form.receiver_name.trim(),
        receiver_phone: form.receiver_phone.trim(),
      }
      if (form.origin_relay_id) payload.origin_relay_id = form.origin_relay_id
      if (form.destination_relay_id) payload.destination_relay_id = form.destination_relay_id
      if (form.delivery_note.trim()) payload.delivery_note = form.delivery_note.trim()
      if (form.declared_value !== '') payload.declared_value = Number(form.declared_value)
      payload.insurance_opt_in = Boolean(form.insurance_opt_in)

      const shipment = await createShipment(token, payload)
      setCreatedShipment(shipment)
      setMessage('Colis cree avec succes.')
      setForm(initialForm)
      if (isClient) setReloadClientListTick((v) => v + 1)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const roleText =
    dashboardRole === 'admin'
      ? 'Creation admin avec controle complet'
      : dashboardRole === 'agent'
        ? 'Creation terrain agent'
        : 'Creation client self-service'

  return (
    <section className="page-grid">
      <article className="page-banner">
        <p className="eyebrow">Expedition Studio</p>
        <h2>Creation colis professionnelle</h2>
        <p>
          Interface complete avec parcours relais, adresse de livraison, valeur declaree, assurance et estimation de
          prix corridor.
        </p>
        <p className="status-line">
          <span className="badge info">Mode actif</span> {roleText}
        </p>
      </article>

      <section className="page-grid two-cols shipment-create-layout">
        <article className="panel">
          <h3>Fiche expedition</h3>
          <form className="form shipment-form-pro" onSubmit={onSubmit}>
            <fieldset>
              <legend>Coordonnees</legend>
              <label>
                Telephone expediteur
                <input
                  value={form.sender_phone}
                  onChange={(e) => setForm((s) => ({ ...s, sender_phone: e.target.value }))}
                  placeholder={userProfile?.phone_e164 || '+257...'}
                  required
                />
              </label>
              <label>
                Nom destinataire
                <input
                  value={form.receiver_name}
                  onChange={(e) => setForm((s) => ({ ...s, receiver_name: e.target.value }))}
                  placeholder="Nom complet"
                  required
                />
              </label>
              <label>
                Telephone destinataire
                <input
                  value={form.receiver_phone}
                  onChange={(e) => setForm((s) => ({ ...s, receiver_phone: e.target.value }))}
                  placeholder="+257..."
                  required
                />
              </label>
            </fieldset>

            <fieldset>
              <legend>Parcours logistique</legend>
              <label>
                Recherche point relais
                <input
                  value={relaySearch}
                  onChange={(e) => setRelaySearch(e.target.value)}
                  placeholder="Nom, code, type"
                />
              </label>

              {isClient ? (
                <div className="surface-soft">
                  <label>
                    Point relais prefere
                    <select
                      value={shippingPrefs.preferred_relay_id}
                      onChange={(e) => setShippingPrefs((s) => ({ ...s, preferred_relay_id: e.target.value }))}
                    >
                      <option value="">Aucun</option>
                      {filteredRelays.map((relay) => (
                        <option key={`pref-${relay.id}`} value={relay.id}>
                          {relay.name} ({relay.relay_code})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={shippingPrefs.use_preferred_relay}
                      onChange={(e) =>
                        setShippingPrefs((s) => ({ ...s, use_preferred_relay: e.target.checked }))
                      }
                    />
                    Utiliser automatiquement ce relais
                  </label>
                  <button
                    type="button"
                    className="button-secondary"
                    disabled={savingPrefs}
                    onClick={onSaveShippingPreferences}
                  >
                    {savingPrefs ? 'Enregistrement...' : 'Enregistrer le relais prefere'}
                  </button>
                </div>
              ) : null}

              {recommendedDestination ? (
                <div className="surface-soft">
                  <p>
                    Point recommande: <strong>{recommendedDestination.relay.name}</strong>{' '}
                    ({recommendedDestination.relay.relay_code})
                  </p>
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={() => setForm((s) => ({ ...s, destination_relay_id: recommendedDestination.relay.id }))}
                  >
                    Utiliser comme destination
                  </button>
                </div>
              ) : null}

              <label>
                Relais origine
                <select
                  value={form.origin_relay_id}
                  onChange={(e) => setForm((s) => ({ ...s, origin_relay_id: e.target.value }))}
                >
                  <option value="">Selectionner</option>
                  {filteredRelays.map((relay) => (
                    <option key={relay.id} value={relay.id}>
                      {relay.name} ({relay.relay_code})
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Relais destination
                <select
                  value={form.destination_relay_id}
                  onChange={(e) => setForm((s) => ({ ...s, destination_relay_id: e.target.value }))}
                >
                  <option value="">Selectionner</option>
                  {filteredRelays.map((relay) => {
                    const cap = relayCapacityById[relay.id]
                    const capLabel = cap
                      ? cap.is_full
                        ? 'complet'
                        : cap.available !== null && cap.available !== undefined
                          ? `${cap.available} places`
                          : 'disponible'
                      : 'n/a'
                    return (
                      <option key={relay.id} value={relay.id}>
                        {relay.name} ({relay.relay_code}) - {capLabel}
                      </option>
                    )
                  })}
                </select>
              </label>

              {isClient ? (
                <button
                  type="button"
                  className="button-secondary"
                  disabled={!form.destination_relay_id}
                  onClick={() => setShippingPrefs((s) => ({ ...s, preferred_relay_id: form.destination_relay_id }))}
                >
                  Definir la destination comme relais prefere
                </button>
              ) : null}

              <div className="relay-list">
                {loadingRelayMeta ? <p>Chargement disponibilites relais...</p> : null}
                {filteredRelays.slice(0, 5).map((relay) => {
                  const cap = relayCapacityById[relay.id]
                  return (
                    <div key={`quick-${relay.id}`} className="relay-item">
                      <p>
                        <strong>{relay.name}</strong> ({relay.relay_code}) | {relay.type}
                      </p>
                      <p>
                        Capacite: {cap?.storage_capacity ?? '-'} | Present: {cap?.current_present ?? '-'} | Dispo:{' '}
                        {cap?.available ?? '-'}
                      </p>
                      <div className="ops-actions">
                        <button
                          type="button"
                          className="button-secondary"
                          onClick={() => setForm((s) => ({ ...s, origin_relay_id: relay.id }))}
                        >
                          Choisir origine
                        </button>
                        <button
                          type="button"
                          className="button-secondary"
                          disabled={cap?.is_full}
                          onClick={() => setForm((s) => ({ ...s, destination_relay_id: relay.id }))}
                        >
                          {cap?.is_full ? 'Destination pleine' : 'Choisir destination'}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>

              <label>
                Note livraison
                <input
                  value={form.delivery_note}
                  onChange={(e) => setForm((s) => ({ ...s, delivery_note: e.target.value }))}
                  placeholder="Ex: Boutique principale, appelez avant livraison"
                  maxLength={500}
                />
              </label>
            </fieldset>

            <fieldset>
              <legend>Assurance et valeur</legend>
              <label>
                Valeur declaree (BIF)
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.declared_value}
                  onChange={(e) => setForm((s) => ({ ...s, declared_value: e.target.value }))}
                  placeholder="100000"
                />
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={form.insurance_opt_in}
                  onChange={(e) => setForm((s) => ({ ...s, insurance_opt_in: e.target.checked }))}
                />
                Activer assurance optionnelle
              </label>
              <button type="submit" disabled={!token || submitting}>
                {submitting ? 'Creation en cours...' : 'Creer le colis'}
              </button>
            </fieldset>
          </form>
        </article>

        <article className="panel shipment-preview-panel">
          <h3>Resume intelligent</h3>
          <div className="split-highlight">
            <div>
              <p className="eyebrow">Route</p>
              <div className="highlight-stat">
                <p>Trajet relais</p>
                <strong>
                  {selectedOrigin?.name || 'Origine non definie'} -&gt;{' '}
                  {selectedDestination?.name || 'Destination non definie'}
                </strong>
              </div>
              <p className="muted-note">Selectionne origine et destination pour verrouiller le parcours.</p>
            </div>
            <div>
              <p className="eyebrow">Assurance</p>
              {loadingQuote ? <p>Calcul prime...</p> : null}
              {!loadingQuote && insuranceQuote ? (
                <div className="data-grid">
                  <div className="data-row">
                    <span>Prime</span>
                    <strong>{insuranceQuote.insurance_fee} BIF</strong>
                  </div>
                  <div className="data-row">
                    <span>Couverture</span>
                    <strong>{insuranceQuote.coverage_amount} BIF</strong>
                  </div>
                  <div className="data-row">
                    <span>Taux</span>
                    <strong>{(Number(insuranceQuote.premium_rate) * 100).toFixed(2)}%</strong>
                  </div>
                </div>
              ) : (
                <p>Renseigne une valeur declaree pour simuler.</p>
              )}
            </div>
          </div>

          <div className="shipment-policy-card">
            <p className="eyebrow">Prix transport estime</p>
            {!form.origin_relay_id || !form.destination_relay_id ? (
              <p>Selectionne origine et destination pour estimer le prix corridor.</p>
            ) : loadingPriceEstimate ? (
              <p>Calcul tarif corridor...</p>
            ) : priceEstimate ? (
              <div className="stack-compact">
                <div className="data-row">
                  <span>Corridor</span>
                  <strong>{priceEstimate.corridor_code}</strong>
                </div>
                <div className="data-row">
                  <span>Base transport</span>
                  <strong>{priceEstimate.base_price_bif} BIF</strong>
                </div>
                <div className="data-row">
                  <span>Fuel surcharge</span>
                  <strong>{priceEstimate.fuel_surcharge_bif} BIF</strong>
                </div>
                <div className="data-row">
                  <span>Surcharge congestion</span>
                  <strong>{priceEstimate.congestion_surcharge_bif} BIF</strong>
                </div>
                <div className="data-row">
                  <span>Assurance</span>
                  <strong>{priceEstimate.insurance_fee_bif} BIF</strong>
                </div>
                <div className="data-row">
                  <span>Total estime</span>
                  <strong>{priceEstimate.total_estimated_bif} BIF</strong>
                </div>
                <div className="data-row">
                  <span>Confiance</span>
                  <span className={`badge ${priceEstimate.confidence === 'high' ? 'success' : 'warning'}`}>
                    {priceEstimate.confidence}
                  </span>
                </div>
              </div>
            ) : (
              <p>Estimation indisponible.</p>
            )}
          </div>

          {insurancePolicy ? (
            <div className="shipment-policy-card">
              <p className="eyebrow">Policy assurance</p>
              <p>Plafond: {insurancePolicy.max_coverage_bif} BIF</p>
              <p>Delai reclamation: {insurancePolicy.claim_window_hours}h</p>
              <p>SLA review: {insurancePolicy.claim_review_sla_hours}h</p>
              <p>Preuve obligatoire: {insurancePolicy.require_proof ? 'oui' : 'non'}</p>
            </div>
          ) : null}

          <div className="shipment-result">
            <p className="eyebrow">Resultat creation</p>
            {createdShipment ? (
              <div className="stack-compact">
                <div className="data-row">
                  <span>Numero colis</span>
                  <strong className="mono">{createdShipment.shipment_no}</strong>
                </div>
                <div className="data-row">
                  <span>Statut</span>
                  <span className="badge success">{humanizeStatus(createdShipment.status || 'created')}</span>
                </div>
                <div className="data-row">
                  <span>Couverture</span>
                  <strong>{createdShipment.coverage_amount ?? '-'} BIF</strong>
                </div>
                <div className="data-row">
                  <span>Prime assurance</span>
                  <strong>{createdShipment.insurance_fee ?? '-'} BIF</strong>
                </div>
              </div>
            ) : (
              <p>Aucun colis cree dans cette session.</p>
            )}
          </div>
        </article>
      </section>

      {isClient ? (
        <article className="panel">
          <h3>Mes colis recents</h3>
          <div className="ops-actions" style={{ marginBottom: 10 }}>
            <label className="checkbox-row" style={{ margin: 0 }}>
              <input type="checkbox" checked={lateOnlyFilter} onChange={(e) => setLateOnlyFilter(e.target.checked)} />
              Retard uniquement
            </label>
            <label style={{ margin: 0 }}>
              Tri
              <select value={clientListSort} onChange={(e) => setClientListSort(e.target.value)}>
                <option value="created_at_desc">Plus recents</option>
                <option value="created_at_asc">Plus anciens</option>
                <option value="sla_priority">SLA critique d'abord</option>
              </select>
            </label>
          </div>
          {loadingClientShipments ? <p>Chargement des colis...</p> : null}
          <div className="relay-list">
            {!loadingClientShipments && sortedClientSlaItems.length === 0 ? (
              <p>{lateOnlyFilter ? 'Aucun colis en retard.' : 'Aucun colis.'}</p>
            ) : null}
            {sortedClientSlaItems.map((shipment) => {
              const sla = shipment?.sla_state || 'on_track'
              return (
                <div key={shipment.shipment_id} className="relay-item">
                  <p>
                    <strong>{shipment.shipment_no}</strong>
                  </p>
                  <div className="data-row">
                    <span>Statut metier</span>
                    <span className="badge info">{humanizeStatus(shipment.status)}</span>
                  </div>
                  <div className="data-row">
                    <span>SLA</span>
                    <span className={`badge ${slaBadgeClass(sla)}`}>{sla.replace('_', '-')}</span>
                  </div>
                  <div className="data-row">
                    <span>ETA</span>
                    <strong>{formatDateTime(shipment?.estimated_delivery_at)}</strong>
                  </div>
                  <div className="data-row">
                    <span>Heures restantes SLA</span>
                    <strong>{shipment?.remaining_sla_hours ?? '-'}</strong>
                  </div>
                </div>
              )
            })}
          </div>
        </article>
      ) : null}

      {message ? <p className="status-line">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
