import { useEffect, useState } from 'react'
import {
  cancelPayment,
  confirmPayment,
  createPayment,
  failPayment,
  initiatePayment,
  listCommissions,
  listPaymentStatuses,
  listPayments,
  listShipments,
  refundPayment,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { humanizeCode, humanizeStatus } from '../utils/display'

const createDefaults = {
  shipment_id: '',
  amount: '',
  payer_phone: '',
  payment_stage: 'at_send',
  provider: 'lumicash',
}

export default function PaymentsPage() {
  const { token } = useAuth()
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [statuses, setStatuses] = useState([])
  const [payments, setPayments] = useState([])
  const [commissions, setCommissions] = useState([])
  const [shipments, setShipments] = useState([])
  const [filters, setFilters] = useState({ shipment_id: '', status: '', payer_phone: '' })
  const [createForm, setCreateForm] = useState(createDefaults)

  const shipmentById = Object.fromEntries((shipments || []).map((row) => [row.id, row]))
  const shipmentOptions = (shipments || []).map((row) => ({
    id: row.id,
    label: `${row.shipment_no || row.id} | ${humanizeStatus(row.status)} | ${row.receiver_name || row.receiver_phone || '-'}`,
  }))

  function shipmentLabel(shipmentId) {
    const row = shipmentById[shipmentId]
    if (row?.shipment_no) return row.shipment_no
    if (!shipmentId) return '-'
    return String(shipmentId).slice(0, 8).toUpperCase()
  }

  async function loadStatusesAndPayments() {
    if (!token) return
    const [statusData, paymentData, shipmentData] = await Promise.all([
      listPaymentStatuses(token),
      listPayments(token, filters),
      listShipments(token, { limit: 400, sort: 'created_at_desc' }).catch(() => []),
    ])
    setStatuses(statusData)
    setPayments(paymentData)
    setShipments(Array.isArray(shipmentData) ? shipmentData : [])
    const commissionData = await listCommissions(token)
    setCommissions(commissionData)
  }

  useEffect(() => {
    loadStatusesAndPayments().catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function onApplyFilters(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      const data = await listPayments(token, filters)
      setPayments(data)
    } catch (err) {
      setError(err.message)
    }
  }

  async function onCreatePayment(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    try {
      await createPayment(token, {
        shipment_id: createForm.shipment_id,
        amount: Number(createForm.amount),
        payer_phone: createForm.payer_phone,
        payment_stage: createForm.payment_stage,
        provider: createForm.provider,
      })
      setCreateForm(createDefaults)
      setMessage('Transaction de paiement creee')
      await loadStatusesAndPayments()
    } catch (err) {
      setError(err.message)
    }
  }

  async function runPaymentAction(action, paymentId, payload = undefined, okLabel = 'Operation faite') {
    setError('')
    setMessage('')
    try {
      await action(token, paymentId, payload)
      setMessage(okLabel)
      await loadStatusesAndPayments()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="page-grid">
      <article className="panel">
        <p className="eyebrow">Payments</p>
        <h2>Paiements envoi / livraison</h2>
        <p>Gestion des transactions mobile money et du cycle de statut.</p>
      </article>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Nouvelle transaction</h3>
          <form className="form" onSubmit={onCreatePayment}>
            <label>
              Colis
              <select
                value={createForm.shipment_id}
                onChange={(e) => setCreateForm((s) => ({ ...s, shipment_id: e.target.value }))}
                required
              >
                <option value="">Selectionner un colis</option>
                {shipmentOptions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Montant
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={createForm.amount}
                onChange={(e) => setCreateForm((s) => ({ ...s, amount: e.target.value }))}
                required
              />
            </label>
            <label>
              Telephone payeur
              <input
                value={createForm.payer_phone}
                onChange={(e) => setCreateForm((s) => ({ ...s, payer_phone: e.target.value }))}
                placeholder="+257..."
                required
              />
            </label>
            <label>
              Etape paiement
              <select
                value={createForm.payment_stage}
                onChange={(e) => setCreateForm((s) => ({ ...s, payment_stage: e.target.value }))}
              >
                <option value="at_send">at_send</option>
                <option value="at_delivery">at_delivery</option>
              </select>
            </label>
            <label>
              Provider
              <input
                value={createForm.provider}
                onChange={(e) => setCreateForm((s) => ({ ...s, provider: e.target.value }))}
                required
              />
            </label>
            <button type="submit">Creer transaction</button>
          </form>
        </article>

        <article className="panel">
          <h3>Filtres</h3>
          <form className="form" onSubmit={onApplyFilters}>
            <label>
              Colis
              <select
                value={filters.shipment_id}
                onChange={(e) => setFilters((s) => ({ ...s, shipment_id: e.target.value }))}
              >
                <option value="">Tous</option>
                {shipmentOptions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
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
              Telephone payeur
              <input
                value={filters.payer_phone}
                onChange={(e) => setFilters((s) => ({ ...s, payer_phone: e.target.value }))}
              />
            </label>
            <button type="submit">Appliquer</button>
          </form>
        </article>
      </section>

      <article className="panel">
        <h3>Transactions</h3>
        <div className="premium-table-wrap">
          {payments.length === 0 ? (
            <p>Aucune transaction</p>
          ) : (
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Transaction</th>
                  <th>Colis</th>
                  <th>Montant</th>
                  <th>Stage / Provider</th>
                  <th>Statut</th>
                  <th>Ref / Payer</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((payment) => (
                  <tr key={payment.id}>
                    <td className="mono">{String(payment.id).slice(0, 8).toUpperCase()}</td>
                    <td>{shipmentLabel(payment.shipment_id)}</td>
                    <td>{payment.amount}</td>
                    <td>
                      {humanizeCode(payment.payment_stage)} / {payment.provider || '-'}
                    </td>
                    <td>
                      <span className="badge info">{humanizeStatus(payment.status)}</span>
                    </td>
                    <td>
                      {payment.external_ref || '-'}
                      <br />
                      {payment.payer_phone || '-'}
                    </td>
                    <td>
                      <div className="table-actions">
                        <button
                          type="button"
                          onClick={() => runPaymentAction(initiatePayment, payment.id, '', 'Paiement initie')}
                        >
                          Initier
                        </button>
                        <button
                          type="button"
                          onClick={() => runPaymentAction(confirmPayment, payment.id, '', 'Paiement confirme')}
                        >
                          Confirmer
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            runPaymentAction(failPayment, payment.id, 'payment_provider_error', 'Paiement marque en echec')
                          }
                        >
                          Echec
                        </button>
                        <button
                          type="button"
                          onClick={() => runPaymentAction(cancelPayment, payment.id, undefined, 'Paiement annule')}
                        >
                          Annuler
                        </button>
                        <button
                          type="button"
                          onClick={() => runPaymentAction(refundPayment, payment.id, 'claim_refund', 'Paiement rembourse')}
                        >
                          Rembourser
                        </button>
                      </div>
                      {payment.failure_reason ? <small>Raison: {payment.failure_reason}</small> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </article>

      <article className="panel">
        <h3>Commissions</h3>
        <div className="premium-table-wrap">
          {commissions.length === 0 ? (
            <p>Aucune commission</p>
          ) : (
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Montant</th>
                  <th>Taux</th>
                  <th>Paiement</th>
                  <th>Colis</th>
                  <th>Beneficiaire</th>
                  <th>Statut</th>
                </tr>
              </thead>
              <tbody>
                {commissions.map((row) => (
                  <tr key={row.id}>
                    <td>{row.commission_type || '-'}</td>
                    <td>{row.amount}</td>
                    <td>{row.rate_pct}</td>
                    <td className="mono">{row.payment_id ? String(row.payment_id).slice(0, 8).toUpperCase() : '-'}</td>
                    <td>{shipmentLabel(row.shipment_id)}</td>
                    <td>
                      {row.beneficiary_kind || '-'}:{' '}
                      <span className="mono">
                        {row.beneficiary_id ? String(row.beneficiary_id).slice(0, 8).toUpperCase() : '-'}
                      </span>
                    </td>
                    <td>{humanizeStatus(row.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </article>

      {message ? <p className="status-line">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
