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
    <section className="card">
      <h2>Créer un colis</h2>
      <form className="form" onSubmit={onSubmit}>
        <input
          value={form.sender_phone}
          onChange={(e) => setForm((s) => ({ ...s, sender_phone: e.target.value }))}
          placeholder="sender_phone"
          required
        />
        <input
          value={form.receiver_name}
          onChange={(e) => setForm((s) => ({ ...s, receiver_name: e.target.value }))}
          placeholder="receiver_name"
          required
        />
        <input
          value={form.receiver_phone}
          onChange={(e) => setForm((s) => ({ ...s, receiver_phone: e.target.value }))}
          placeholder="receiver_phone"
          required
        />
        <button type="submit">Créer</button>
      </form>
      <p>Shipment No: {shipmentNo || '-'}</p>
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
