import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listPublicRelays, publicEstimateShipment, publicTrackShipment } from '../api/client'
import { formatDateTime, humanizeCode, humanizeStatus, relayDisplayName } from '../utils/display'

export default function PublicTrackingPage() {
  const [error, setError] = useState('')
  const [trackResult, setTrackResult] = useState(null)
  const [estimateResult, setEstimateResult] = useState(null)
  const [relays, setRelays] = useState([])
  const [trackForm, setTrackForm] = useState({ shipment_no: '', phone: '', access_code: '' })
  const [estimateForm, setEstimateForm] = useState({
    origin_relay_id: '',
    destination_relay_id: '',
    declared_value: '',
    insurance_opt_in: false,
  })
  const relayNameById = Object.fromEntries((relays || []).filter((r) => r?.id).map((r) => [r.id, r.name || r.id]))

  useEffect(() => {
    listPublicRelays()
      .then((rows) => setRelays(Array.isArray(rows) ? rows : []))
      .catch((err) => setError(err.message))
  }, [])

  async function onTrackSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      const res = await publicTrackShipment({
        shipmentNo: trackForm.shipment_no.trim(),
        phone: trackForm.phone.trim(),
        accessCode: trackForm.access_code.trim(),
      })
      setTrackResult(res)
    } catch (err) {
      setError(err.message)
      setTrackResult(null)
    }
  }

  async function onEstimateSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      const res = await publicEstimateShipment({
        originRelayId: estimateForm.origin_relay_id,
        destinationRelayId: estimateForm.destination_relay_id,
        declaredValue: estimateForm.declared_value === '' ? null : Number(estimateForm.declared_value),
        insuranceOptIn: estimateForm.insurance_opt_in,
      })
      setEstimateResult(res)
    } catch (err) {
      setError(err.message)
      setEstimateResult(null)
    }
  }

  return (
    <section className="page-grid">
      <article className="page-banner">
        <p className="eyebrow">Public Tracking</p>
        <h2>Suivre un colis sans connexion</h2>
        <p>Entrez votre numero de colis et votre numero de telephone pour consulter le statut.</p>
      </article>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Suivi public colis</h3>
          <form className="form" onSubmit={onTrackSubmit}>
            <label>
              Numero colis
              <input
                value={trackForm.shipment_no}
                onChange={(e) => setTrackForm((s) => ({ ...s, shipment_no: e.target.value }))}
                placeholder="PBL-..."
                required
              />
            </label>
            <label>
              Telephone (expediteur ou destinataire)
              <input
                value={trackForm.phone}
                onChange={(e) => setTrackForm((s) => ({ ...s, phone: e.target.value }))}
                placeholder="+257..."
                required
              />
            </label>
            <label>
              Code d'acces suivi
              <input
                value={trackForm.access_code}
                onChange={(e) => setTrackForm((s) => ({ ...s, access_code: e.target.value }))}
                placeholder="6 chiffres"
                required
              />
            </label>
            <button type="submit">Rechercher</button>
          </form>

          {trackResult ? (
            <div className="stack-compact" style={{ marginTop: 10 }}>
              <div className="data-row">
                <span>Colis</span>
                <strong>{trackResult.shipment_no_masked}</strong>
              </div>
              <div className="data-row">
                <span>Statut</span>
                <span className="badge info">{humanizeStatus(trackResult.status)}</span>
              </div>
              <div className="data-row">
                <span>Destinataire</span>
                <strong>{trackResult.receiver_name_masked || '-'}</strong>
              </div>
              <div className="data-row">
                <span>SLA</span>
                <span className={`badge ${trackResult.sla_state === 'late' ? 'danger' : trackResult.sla_state === 'at_risk' ? 'warning' : 'success'}`}>
                  {trackResult.sla_state}
                </span>
              </div>
              <div className="data-row">
                <span>ETA</span>
                <strong>{trackResult.estimated_delivery_at}</strong>
              </div>
              <div className="relay-list">
                {(trackResult.recent_timeline || []).map((item, idx) => (
                  <div key={`${item.occurred_at || 'x'}-${idx}`} className="relay-item">
                    <p>
                      <strong>{humanizeCode(item.code)}</strong>
                    </p>
                    <p>{formatDateTime(item.occurred_at)}</p>
                    <p>status: {humanizeStatus(item.status)}</p>
                    <p>relay: {relayDisplayName(item.relay_id, relayNameById)}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </article>

        <article className="panel">
          <h3>Simulateur prix corridor</h3>
          <form className="form" onSubmit={onEstimateSubmit}>
            <label>
              Relais origine
              <select
                value={estimateForm.origin_relay_id}
                onChange={(e) => setEstimateForm((s) => ({ ...s, origin_relay_id: e.target.value }))}
                required
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
                value={estimateForm.destination_relay_id}
                onChange={(e) => setEstimateForm((s) => ({ ...s, destination_relay_id: e.target.value }))}
                required
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
              Valeur declaree (BIF)
              <input
                type="number"
                min="0"
                value={estimateForm.declared_value}
                onChange={(e) => setEstimateForm((s) => ({ ...s, declared_value: e.target.value }))}
              />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={estimateForm.insurance_opt_in}
                onChange={(e) => setEstimateForm((s) => ({ ...s, insurance_opt_in: e.target.checked }))}
              />
              Inclure assurance
            </label>
            <button type="submit">Estimer</button>
          </form>

          {estimateResult ? (
            <div className="stack-compact" style={{ marginTop: 10 }}>
              <div className="data-row">
                <span>Corridor</span>
                <strong>{estimateResult.corridor_code}</strong>
              </div>
              <div className="data-row">
                <span>Total estime</span>
                <strong>{estimateResult.total_estimated_bif} BIF</strong>
              </div>
            </div>
          ) : null}
        </article>
      </section>

      <p>
        <Link to="/">Retour accueil</Link>
      </p>
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
