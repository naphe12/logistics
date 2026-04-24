import { useState } from 'react'
import { simulateUssd } from '../api/client'

const presets = [
  { label: 'Menu principal', text: '' },
  { label: 'Suivi colis', text: '2' },
  { label: 'Code retrait', text: '3' },
  { label: 'Creer colis', text: '1' },
]

export default function UssdSimulatorPage() {
  const [error, setError] = useState('')
  const [response, setResponse] = useState('')
  const [history, setHistory] = useState([])
  const [form, setForm] = useState({
    sessionId: 'web-sim-001',
    serviceCode: '*123#',
    phoneNumber: '+25761000000',
    text: '',
  })

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setResponse('')
    try {
      const res = await simulateUssd(form)
      setResponse(res)
      setHistory((prev) => [
        {
          at: new Date().toISOString(),
          text: form.text,
          response: res,
        },
        ...prev,
      ])
    } catch (err) {
      setError(err.message)
    }
  }

  function onResetSession() {
    setForm((s) => ({ ...s, text: '' }))
    setResponse('')
    setError('')
    setHistory([])
  }

  return (
    <section className="page-grid">
      <article className="panel">
        <p className="eyebrow">USSD</p>
        <h2>Simulateur USSD</h2>
        <p>
          Utilise le format sequence operateur (ex: <code>1*Jean*+25761234567*1</code>).
        </p>
      </article>

      <article className="panel">
        <form className="form" onSubmit={onSubmit}>
          <label>
            Session ID
            <input
              value={form.sessionId}
              onChange={(e) => setForm((s) => ({ ...s, sessionId: e.target.value }))}
              required
            />
          </label>
          <label>
            Service code
            <input
              value={form.serviceCode}
              onChange={(e) => setForm((s) => ({ ...s, serviceCode: e.target.value }))}
              required
            />
          </label>
          <label>
            Telephone
            <input
              value={form.phoneNumber}
              onChange={(e) => setForm((s) => ({ ...s, phoneNumber: e.target.value }))}
              placeholder="+257..."
              required
            />
          </label>
          <label>
            Text USSD
            <input
              value={form.text}
              onChange={(e) => setForm((s) => ({ ...s, text: e.target.value }))}
              placeholder="Ex: 2*PBL-20260424-ABC12345"
            />
          </label>
          <div className="ops-actions">
            <button type="submit">Envoyer</button>
            <button type="button" className="button-secondary" onClick={onResetSession}>
              Reset session
            </button>
          </div>
        </form>

        <div className="preset-row">
          {presets.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className="button-secondary"
              onClick={() => setForm((s) => ({ ...s, text: preset.text }))}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </article>

      <article className="panel">
        <h3>Reponse courante</h3>
        <pre className="ussd-response">{response || '-'}</pre>
        {error ? <p className="error">{error}</p> : null}
      </article>

      <article className="panel">
        <h3>Historique</h3>
        <div className="ussd-history">
          {history.length === 0 ? <p>Aucune requete</p> : null}
          {history.map((entry) => (
            <div key={entry.at} className="ussd-history-item">
              <p>
                <strong>Text:</strong> {entry.text || '(vide)'}
              </p>
              <p>
                <strong>Reponse:</strong> {entry.response}
              </p>
            </div>
          ))}
        </div>
      </article>
    </section>
  )
}
