import { useEffect, useMemo, useState } from 'react'
import {
  createShipment,
  getShipmentInsurancePolicy,
  getShipmentInsuranceQuote,
  listRelays,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'

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

export default function ShipmentsPage() {
  const { token, dashboardRole } = useAuth()
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [createdShipment, setCreatedShipment] = useState(null)
  const [form, setForm] = useState(initialForm)
  const [relays, setRelays] = useState([])
  const [insuranceQuote, setInsuranceQuote] = useState(null)
  const [insurancePolicy, setInsurancePolicy] = useState(null)
  const [loadingQuote, setLoadingQuote] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const canUseInsuranceQuote = Number(form.declared_value || 0) >= 0

  const selectedOrigin = useMemo(
    () => relays.find((relay) => relay.id === form.origin_relay_id),
    [relays, form.origin_relay_id],
  )
  const selectedDestination = useMemo(
    () => relays.find((relay) => relay.id === form.destination_relay_id),
    [relays, form.destination_relay_id],
  )

  useEffect(() => {
    if (!token) return
    async function loadReference() {
      const [relayData, policy] = await Promise.all([listRelays(token), getShipmentInsurancePolicy(token)])
      setRelays(Array.isArray(relayData) ? relayData : [])
      setInsurancePolicy(policy || null)
    }
    loadReference().catch((err) => setError(err.message))
  }, [token])

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

  async function onSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setMessage('')
    setCreatedShipment(null)
    try {
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
      <article className="panel">
        <p className="eyebrow">Expedition Studio</p>
        <h2>Creation colis professionnelle</h2>
        <p>
          Interface complete avec parcours relais, adresse de livraison, valeur declaree et assurance optionnelle.
        </p>
        <p className="status-line">Mode actif: {roleText}</p>
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
                  placeholder="+257..."
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
                Relais origine
                <select
                  value={form.origin_relay_id}
                  onChange={(e) => setForm((s) => ({ ...s, origin_relay_id: e.target.value }))}
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
                Relais destination
                <select
                  value={form.destination_relay_id}
                  onChange={(e) => setForm((s) => ({ ...s, destination_relay_id: e.target.value }))}
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
              <legend>Assurance & valeur</legend>
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
          <div className="shipment-preview-grid">
            <div>
              <p className="eyebrow">Route</p>
              <p>
                {selectedOrigin?.name || 'Origine non definie'} →{' '}
                {selectedDestination?.name || 'Destination non definie'}
              </p>
            </div>
            <div>
              <p className="eyebrow">Assurance</p>
              {loadingQuote ? <p>Calcul prime...</p> : null}
              {!loadingQuote && insuranceQuote ? (
                <>
                  <p>
                    Prime: <strong>{insuranceQuote.insurance_fee} BIF</strong>
                  </p>
                  <p>
                    Couverture: <strong>{insuranceQuote.coverage_amount} BIF</strong>
                  </p>
                  <p>Taux: {(Number(insuranceQuote.premium_rate) * 100).toFixed(2)}%</p>
                </>
              ) : (
                <p>Renseigne une valeur declaree pour simuler.</p>
              )}
            </div>
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
              <>
                <p>
                  Numero colis: <strong>{createdShipment.shipment_no}</strong>
                </p>
                <p>Status: {createdShipment.status || 'created'}</p>
                <p>Coverage: {createdShipment.coverage_amount ?? '-'} BIF</p>
                <p>Insurance fee: {createdShipment.insurance_fee ?? '-'} BIF</p>
              </>
            ) : (
              <p>Aucun colis cree dans cette session.</p>
            )}
          </div>
        </article>
      </section>

      {message ? <p className="status-line">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
