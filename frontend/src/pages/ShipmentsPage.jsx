import { useState } from 'react'
import { createShipment } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function ShipmentsPage() {
  const { token } = useAuth()
  const [shipmentNo, setShipmentNo] = useState('')
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    sender_phone: '',
    receiver_name: '',
    receiver_phone: '',
  })

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setShipmentNo('')
    try {
      const shipment = await createShipment(token, form)
      setShipmentNo(shipment.shipment_no || '')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="page-grid">
      <article className="panel">
        <p className="eyebrow">Workflow</p>
        <h2>Creation d un colis</h2>
        <p>Renseigne les informations de depart et de destination puis lance l expedition.</p>
      </article>

      <article className="panel">
        <form className="form" onSubmit={onSubmit}>
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
          <button type="submit">Creer le colis</button>
        </form>
      </article>

      <article className="panel">
        <h3>Resultat</h3>
        <p>
          Numero colis: <strong>{shipmentNo || '-'}</strong>
        </p>
        {error ? <p className="error">{error}</p> : null}
      </article>
    </section>
  )
}
