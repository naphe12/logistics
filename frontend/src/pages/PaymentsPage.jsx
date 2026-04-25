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
  const [filters, setFilters] = useState({ shipment_id: '', status: '', payer_phone: '' })
  const [createForm, setCreateForm] = useState(createDefaults)

  async function loadStatusesAndPayments() {
    if (!token) return
    const [statusData, paymentData] = await Promise.all([
      listPaymentStatuses(token),
      listPayments(token, filters),
    ])
    setStatuses(statusData)
    setPayments(paymentData)
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
              Shipment ID
              <input
                value={createForm.shipment_id}
                onChange={(e) => setCreateForm((s) => ({ ...s, shipment_id: e.target.value }))}
                required
              />
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
        <div className="relay-list">
          {payments.length === 0 ? <p>Aucune transaction</p> : null}
          {payments.map((payment) => (
            <div key={payment.id} className="relay-item">
              <p>
                <strong>{payment.id}</strong>
              </p>
              <p>
                shipment: {payment.shipment_id} | montant: {payment.amount} | stage:{' '}
                {humanizeCode(payment.payment_stage)} | provider: {payment.provider || '-'}
              </p>
              <p>
                statut: <strong>{humanizeStatus(payment.status)}</strong> | ref: {payment.external_ref || '-'} |
                payer:{' '}
                {payment.payer_phone || '-'}
              </p>
              {payment.failure_reason ? <p>raison echec: {payment.failure_reason}</p> : null}
              <div className="ops-actions">
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
                  onClick={() => runPaymentAction(failPayment, payment.id, 'payment_provider_error', 'Paiement marque en echec')}
                >
                  Marquer echec
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
            </div>
          ))}
        </div>
      </article>

      <article className="panel">
        <h3>Commissions</h3>
        <div className="relay-list">
          {commissions.length === 0 ? <p>Aucune commission</p> : null}
          {commissions.map((row) => (
            <div key={row.id} className="relay-item">
              <p>
                <strong>{row.commission_type || '-'}</strong> | amount: {row.amount} | rate: {row.rate_pct}
              </p>
              <p>
                payment: {row.payment_id || '-'} | shipment: {row.shipment_id || '-'} | beneficiary:{' '}
                {row.beneficiary_kind || '-'}:{row.beneficiary_id || '-'}
              </p>
              <p>status: {humanizeStatus(row.status)}</p>
            </div>
          ))}
        </div>
      </article>

      {message ? <p className="status-line">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
