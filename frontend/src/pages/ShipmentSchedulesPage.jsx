import { useEffect, useMemo, useState } from 'react'
import {
  createShipmentSchedule,
  listShipmentSchedules,
  runDueShipmentSchedules,
  updateShipmentSchedule,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'

const SCHEDULE_PREFS_KEY = 'logix_shipment_schedule_prefs_v1'
const SCHEDULE_PAGE_SIZE = 12

function loadSchedulePrefs() {
  try {
    const raw = localStorage.getItem(SCHEDULE_PREFS_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return {}
    return parsed
  } catch {
    return {}
  }
}

function saveSchedulePrefs(prefs) {
  try {
    localStorage.setItem(SCHEDULE_PREFS_KEY, JSON.stringify(prefs))
  } catch {
    // ignore storage issues
  }
}

function clearSchedulePrefs() {
  try {
    localStorage.removeItem(SCHEDULE_PREFS_KEY)
  } catch {
    // ignore storage issues
  }
}

function toDatetimeLocalValue(date) {
  const dt = date instanceof Date ? date : new Date(date)
  if (Number.isNaN(dt.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  const yyyy = dt.getFullYear()
  const mm = pad(dt.getMonth() + 1)
  const dd = pad(dt.getDate())
  const hh = pad(dt.getHours())
  const mi = pad(dt.getMinutes())
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}`
}

const initialForm = {
  sender_phone: '',
  receiver_name: '',
  receiver_phone: '',
  frequency: 'once',
  interval_count: 1,
  day_of_week: '0',
  day_of_month: '1',
  start_at: toDatetimeLocalValue(new Date(Date.now() + 5 * 60 * 1000)),
  end_at: '',
  remaining_runs: '',
  is_active: true,
}

export default function ShipmentSchedulesPage() {
  const { token, userProfile } = useAuth()
  const initialPrefs = useMemo(() => loadSchedulePrefs(), [])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [running, setRunning] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [activeOnly, setActiveOnly] = useState(
    typeof initialPrefs.activeOnly === 'boolean' ? initialPrefs.activeOnly : true,
  )
  const [mineOnly, setMineOnly] = useState(typeof initialPrefs.mineOnly === 'boolean' ? initialPrefs.mineOnly : false)
  const [sortMode, setSortMode] = useState(
    typeof initialPrefs.sortMode === 'string' ? initialPrefs.sortMode : 'next_run_asc',
  )
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [totalSchedules, setTotalSchedules] = useState(0)
  const [schedules, setSchedules] = useState([])
  const [runResult, setRunResult] = useState(null)
  const [form, setForm] = useState({
    ...initialForm,
    sender_phone: userProfile?.phone_e164 || '',
  })

  const sortedSchedules = useMemo(() => [...schedules], [schedules])

  async function loadSchedules() {
    if (!token) return
    const pageData = await listShipmentSchedules(token, {
      activeOnly,
      mine: mineOnly,
      offset: page * SCHEDULE_PAGE_SIZE,
      limit: SCHEDULE_PAGE_SIZE,
      sort: sortMode,
    })
    const rows = Array.isArray(pageData?.items) ? pageData.items : []
    const total = Number(pageData?.total || 0)
    const offset = Number(pageData?.offset || 0)
    const limit = Number(pageData?.limit || SCHEDULE_PAGE_SIZE)
    setSchedules(rows)
    setTotalSchedules(total)
    setHasMore(offset + rows.length < total && rows.length > 0 && limit > 0)
  }

  useEffect(() => {
    loadSchedules().catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, activeOnly, mineOnly, page])

  useEffect(() => {
    const role = userProfile?.user_type || ''
    if (role === 'customer' || role === 'business') {
      setMineOnly(true)
    }
  }, [userProfile?.user_type])

  useEffect(() => {
    saveSchedulePrefs({
      activeOnly,
      mineOnly,
      sortMode,
    })
  }, [activeOnly, mineOnly, sortMode])

  useEffect(() => {
    setPage(0)
  }, [activeOnly, mineOnly, sortMode])

  useEffect(() => {
    if (!userProfile?.phone_e164) return
    setForm((prev) => (prev.sender_phone ? prev : { ...prev, sender_phone: userProfile.phone_e164 }))
  }, [userProfile?.phone_e164])

  async function onCreate(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setSubmitting(true)
    try {
      const payload = {
        sender_phone: form.sender_phone.trim(),
        receiver_name: form.receiver_name.trim(),
        receiver_phone: form.receiver_phone.trim(),
        frequency: form.frequency,
        interval_count: Number(form.interval_count || 1),
        start_at: new Date(form.start_at).toISOString(),
        is_active: Boolean(form.is_active),
      }
      if (form.frequency === 'weekly') payload.day_of_week = Number(form.day_of_week)
      if (form.frequency === 'monthly') payload.day_of_month = Number(form.day_of_month)
      if (form.end_at) payload.end_at = new Date(form.end_at).toISOString()
      if (form.remaining_runs !== '') payload.remaining_runs = Number(form.remaining_runs)

      await createShipmentSchedule(token, payload)
      setMessage('Programme d envoi cree.')
      setPage(0)
      setForm({
        ...initialForm,
        sender_phone: form.sender_phone,
      })
      await loadSchedules()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  async function onToggleActive(schedule) {
    setError('')
    setMessage('')
    try {
      await updateShipmentSchedule(token, schedule.id, { is_active: !schedule.is_active })
      setMessage(`Programme ${schedule.is_active ? 'desactive' : 'active'}.`)
      await loadSchedules()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onRunDueNow() {
    setError('')
    setMessage('')
    setRunning(true)
    try {
      const result = await runDueShipmentSchedules(token, { limit: 200 })
      setRunResult(result || null)
      setMessage('Execution des envois dus terminee.')
      await loadSchedules()
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  function onResetFilters() {
    const role = userProfile?.user_type || ''
    setActiveOnly(true)
    setSortMode('next_run_asc')
    setMineOnly(role === 'customer' || role === 'business')
    setPage(0)
    clearSchedulePrefs()
    setMessage('Filtres reinitialises.')
    setError('')
  }

  return (
    <section className="page-grid">
      <article className="page-banner">
        <p className="eyebrow">Automatisation envois</p>
        <h2>Envois programmes et repetitifs</h2>
        <p>Configure des envois ponctuels ou recurrents: journalier, hebdomadaire, mensuel.</p>
      </article>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Nouveau programme</h3>
          <form className="form shipment-form-pro" onSubmit={onCreate}>
            <label>
              Telephone expediteur
              <input
                required
                value={form.sender_phone}
                onChange={(e) => setForm((s) => ({ ...s, sender_phone: e.target.value }))}
              />
            </label>
            <label>
              Nom destinataire
              <input
                required
                value={form.receiver_name}
                onChange={(e) => setForm((s) => ({ ...s, receiver_name: e.target.value }))}
              />
            </label>
            <label>
              Telephone destinataire
              <input
                required
                value={form.receiver_phone}
                onChange={(e) => setForm((s) => ({ ...s, receiver_phone: e.target.value }))}
              />
            </label>
            <label>
              Frequence
              <select
                value={form.frequency}
                onChange={(e) => setForm((s) => ({ ...s, frequency: e.target.value }))}
              >
                <option value="once">Ponctuel (once)</option>
                <option value="daily">Quotidien</option>
                <option value="weekly">Hebdomadaire</option>
                <option value="monthly">Mensuel</option>
              </select>
            </label>
            <label>
              Intervalle
              <input
                type="number"
                min="1"
                max="365"
                value={form.interval_count}
                onChange={(e) => setForm((s) => ({ ...s, interval_count: e.target.value }))}
              />
            </label>
            {form.frequency === 'weekly' ? (
              <label>
                Jour de semaine
                <select
                  value={form.day_of_week}
                  onChange={(e) => setForm((s) => ({ ...s, day_of_week: e.target.value }))}
                >
                  <option value="0">Lundi</option>
                  <option value="1">Mardi</option>
                  <option value="2">Mercredi</option>
                  <option value="3">Jeudi</option>
                  <option value="4">Vendredi</option>
                  <option value="5">Samedi</option>
                  <option value="6">Dimanche</option>
                </select>
              </label>
            ) : null}
            {form.frequency === 'monthly' ? (
              <label>
                Jour du mois
                <input
                  type="number"
                  min="1"
                  max="31"
                  value={form.day_of_month}
                  onChange={(e) => setForm((s) => ({ ...s, day_of_month: e.target.value }))}
                />
              </label>
            ) : null}
            <label>
              Debut execution
              <input
                type="datetime-local"
                required
                value={form.start_at}
                onChange={(e) => setForm((s) => ({ ...s, start_at: e.target.value }))}
              />
            </label>
            <label>
              Fin execution (optionnel)
              <input
                type="datetime-local"
                value={form.end_at}
                onChange={(e) => setForm((s) => ({ ...s, end_at: e.target.value }))}
              />
            </label>
            <label>
              Nombre max d executions (optionnel)
              <input
                type="number"
                min="1"
                max="10000"
                value={form.remaining_runs}
                onChange={(e) => setForm((s) => ({ ...s, remaining_runs: e.target.value }))}
              />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm((s) => ({ ...s, is_active: e.target.checked }))}
              />
              Programme actif
            </label>
            <button type="submit" disabled={submitting}>
              {submitting ? 'Creation...' : 'Creer le programme'}
            </button>
          </form>
        </article>

        <article className="panel">
          <h3>Execution et controle</h3>
          <div className="ops-actions">
            <button type="button" onClick={onRunDueNow} disabled={running}>
              {running ? 'Execution...' : 'Executer les envois dus maintenant'}
            </button>
            <label className="checkbox-row">
              <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} />
              Afficher seulement les actifs
            </label>
            <label className="checkbox-row">
              <input type="checkbox" checked={mineOnly} onChange={(e) => setMineOnly(e.target.checked)} />
              Afficher seulement mes programmes
            </label>
            <label>
              Tri
              <select value={sortMode} onChange={(e) => setSortMode(e.target.value)}>
                <option value="next_run_asc">Prochaine execution (asc)</option>
                <option value="next_run_desc">Prochaine execution (desc)</option>
                <option value="created_desc">Creation recente</option>
                <option value="created_asc">Creation ancienne</option>
              </select>
            </label>
            <button type="button" className="button-secondary" onClick={onResetFilters}>
              Reinitialiser les filtres
            </button>
          </div>
          {mineOnly ? (
            <p className="status-line" style={{ marginTop: 10 }}>
              Filtre actif: vue limitee a mes programmes (owner).
            </p>
          ) : null}
          {runResult ? (
            <div className="surface-soft" style={{ marginTop: 12 }}>
              <div className="data-row">
                <span>Examines</span>
                <strong>{runResult.examined}</strong>
              </div>
              <div className="data-row">
                <span>Declenches</span>
                <strong>{runResult.triggered}</strong>
              </div>
              <div className="data-row">
                <span>Echecs</span>
                <strong>{runResult.failed}</strong>
              </div>
            </div>
          ) : (
            <p>Aucune execution manuelle lancee.</p>
          )}
        </article>
      </section>

      <article className="panel">
        <h3>Programmes configures</h3>
        <div className="ops-actions" style={{ marginBottom: 8 }}>
          <p className="status-line" style={{ margin: 0 }}>
            Page {page + 1} - {sortedSchedules.length} affiche(s) / {totalSchedules} total.
          </p>
          <button type="button" className="button-secondary" disabled={page <= 0} onClick={() => setPage(page - 1)}>
            Precedent
          </button>
          <button type="button" className="button-secondary" disabled={!hasMore} onClick={() => setPage(page + 1)}>
            Suivant
          </button>
        </div>
        <div className="relay-list list-scroll">
          {sortedSchedules.length === 0 ? <p>Aucun programme.</p> : null}
          {sortedSchedules.map((row) => (
            <div key={row.id} className="relay-item">
              <p>
                <strong>{row.receiver_name}</strong> ({row.receiver_phone})
              </p>
              <p className="mono">{row.id}</p>
              <div className="data-row">
                <span>Frequence</span>
                <span className="badge info">
                  {row.frequency} / every {row.interval_count}
                </span>
              </div>
              <div className="data-row">
                <span>Prochaine execution</span>
                <strong>{row.next_run_at || '-'}</strong>
              </div>
              <div className="data-row">
                <span>Runs restants</span>
                <strong>{row.remaining_runs ?? 'illimite'}</strong>
              </div>
              <div className="data-row">
                <span>Etat</span>
                <span className={`badge ${row.is_active ? 'success' : 'warning'}`}>
                  {row.is_active ? 'actif' : 'inactif'}
                </span>
              </div>
              {row.last_error ? <p className="error">{row.last_error}</p> : null}
              <div className="ops-actions">
                <button type="button" className="button-secondary" onClick={() => onToggleActive(row)}>
                  {row.is_active ? 'Desactiver' : 'Activer'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </article>

      {message ? <p className="status-line">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
