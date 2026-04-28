import { useEffect, useState } from 'react'
import {
  autoEscalateClaims,
  dispatchBackofficeSms,
  getBackofficeOverview,
  getBackofficeS1OpsKpis,
  getBackofficeSmsWorkerStatus,
  getClaimsFinanceReport,
  getClaimsOpsStats,
  listBackofficeAlerts,
  listBackofficeAuditLogs,
  listBackofficeErrors,
  listBackofficeSmsLogs,
  listBackofficeUssdLogs,
  notifyBackofficeCriticalAlertsSms,
  runBackofficeShipmentSchedulesDue,
  runBackofficeAutoDetectIncidents,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'

function severityBadge(severity) {
  const value = String(severity || '').toLowerCase()
  if (value.includes('critical') || value.includes('high')) return 'danger'
  if (value.includes('warning') || value.includes('medium')) return 'warning'
  if (value.includes('low') || value.includes('info')) return 'info'
  return 'info'
}

function severityIcon(severity) {
  const value = String(severity || '').toLowerCase()
  if (value.includes('critical') || value.includes('high')) return 'HIGH'
  if (value.includes('warning') || value.includes('medium')) return 'WARN'
  return 'INFO'
}

function parseDelayDetails(details) {
  const text = String(details || '')
  const match = text.match(/Colis\s+([A-Za-z0-9-]+)\s+bloqu[eé]\s+en\s+statut\s+([a-z_]+)/i)
  if (!match) {
    return { shipmentNo: '-', blockedStatus: '-', text }
  }
  return {
    shipmentNo: match[1] || '-',
    blockedStatus: match[2] || '-',
    text,
  }
}

function financeIcon(point) {
  const ratio = Number(point?.loss_ratio_pct || 0)
  const margin = Number(point?.margin || 0)
  if (ratio >= 70 || margin < 0) return 'risk'
  if (ratio >= 40) return 'watch'
  return 'ok'
}

function getS1Health(kpis) {
  const onTime = Number(kpis?.on_time_rate ?? NaN)
  const incident = Number(kpis?.incident_rate ?? NaN)
  const scan = Number(kpis?.scan_compliance ?? NaN)

  if (Number.isNaN(onTime) || Number.isNaN(incident) || Number.isNaN(scan)) {
    return { tone: 'info', label: 'S1 health unknown', reasons: ['Insufficient KPI data'] }
  }

  const hardAlerts = []
  const softAlerts = []

  if (onTime < 85) hardAlerts.push(`on_time_rate ${onTime.toFixed(2)}% < 85%`)
  else if (onTime < 90) softAlerts.push(`on_time_rate ${onTime.toFixed(2)}% < 90%`)

  if (incident > 8) hardAlerts.push(`incident_rate ${incident.toFixed(2)}% > 8%`)
  else if (incident > 5) softAlerts.push(`incident_rate ${incident.toFixed(2)}% > 5%`)

  if (scan < 90) hardAlerts.push(`scan_compliance ${scan.toFixed(2)}% < 90%`)
  else if (scan < 95) softAlerts.push(`scan_compliance ${scan.toFixed(2)}% < 95%`)

  if (hardAlerts.length > 0) {
    return { tone: 'danger', label: 'S1 health critical', reasons: hardAlerts }
  }
  if (softAlerts.length > 0) {
    return { tone: 'warning', label: 'S1 health at risk', reasons: softAlerts }
  }
  return { tone: 'success', label: 'S1 health healthy', reasons: ['All KPI thresholds met'] }
}

export default function BackofficePage() {
  const { token } = useAuth()
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const [overview, setOverview] = useState(null)
  const [workerStatus, setWorkerStatus] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [smsLogs, setSmsLogs] = useState([])
  const [ussdLogs, setUssdLogs] = useState([])
  const [auditLogs, setAuditLogs] = useState([])
  const [recentErrors, setRecentErrors] = useState([])
  const [claimsStats, setClaimsStats] = useState(null)
  const [claimsFinance, setClaimsFinance] = useState(null)
  const [s1Kpis, setS1Kpis] = useState(null)

  const [dispatchResult, setDispatchResult] = useState(null)
  const [autoDetectResult, setAutoDetectResult] = useState(null)
  const [notifyCriticalResult, setNotifyCriticalResult] = useState(null)
  const [claimsEscalationResult, setClaimsEscalationResult] = useState(null)
  const [shipmentSchedulesRunResult, setShipmentSchedulesRunResult] = useState(null)

  async function loadData() {
    if (!token) return
    const [ov, s1, worker, opsAlerts, sms, ussd, audit, errs, claimStats, claimFinance] = await Promise.all([
      getBackofficeOverview(token),
      getBackofficeS1OpsKpis(token, 168),
      getBackofficeSmsWorkerStatus(token),
      listBackofficeAlerts(token, { delayed_hours: 48, relay_utilization_warn: 0.9, limit: 100 }),
      listBackofficeSmsLogs(token, 30),
      listBackofficeUssdLogs(token, 30),
      listBackofficeAuditLogs(token, 30),
      listBackofficeErrors(token, 30),
      getClaimsOpsStats(token, { staleHours: 24 }),
      getClaimsFinanceReport(token, { months: 6 }),
    ])
    setOverview(ov)
    setS1Kpis(s1 || null)
    setWorkerStatus(worker)
    setAlerts(opsAlerts || [])
    setSmsLogs(sms || [])
    setUssdLogs(ussd || [])
    setAuditLogs(audit || [])
    setRecentErrors(errs || [])
    setClaimsStats(claimStats || null)
    setClaimsFinance(claimFinance || null)
  }

  function pct(value) {
    if (typeof value !== 'number' || Number.isNaN(value)) return '-'
    return `${value.toFixed(2)}%`
  }

  function fmtMoney(value) {
    const num = Number(value)
    if (!Number.isFinite(num)) return '-'
    return num.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  function fmtRatio(value) {
    const num = Number(value)
    if (!Number.isFinite(num)) return '-'
    return `${num.toFixed(2)}%`
  }
  const s1Health = getS1Health(s1Kpis)

  async function onDispatchSms() {
    setError('')
    setMessage('')
    try {
      const result = await dispatchBackofficeSms(token, 100)
      setDispatchResult(result)
      setMessage('Dispatch SMS execute')
      await loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onAutoDetectIncidents() {
    setError('')
    setMessage('')
    try {
      const result = await runBackofficeAutoDetectIncidents(token, 48, 200)
      setAutoDetectResult(result)
      setMessage('Auto-detect incidents execute')
      await loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onNotifyCriticalAlertsSms() {
    setError('')
    setMessage('')
    try {
      const result = await notifyBackofficeCriticalAlertsSms(token, {
        delayedHours: 48,
        relayUtilizationWarn: 0.9,
        throttleMinutes: 30,
        maxRecipients: 20,
        maxPerHour: 4,
      })
      setNotifyCriticalResult(result)
      setMessage('Notification alertes critiques executee')
      await loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onEscalateClaimsSla() {
    setError('')
    setMessage('')
    try {
      const result = await autoEscalateClaims(token, {
        staleHours: 24,
        limit: 200,
        dryRun: false,
        notifyInternal: true,
      })
      setClaimsEscalationResult(result)
      setMessage('Escalade SLA claims executee')
      await loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onRunShipmentSchedulesDueNow() {
    setError('')
    setMessage('')
    try {
      const result = await runBackofficeShipmentSchedulesDue(token, 200)
      setShipmentSchedulesRunResult(result)
      setMessage('Execution forcee des envois programmes terminee')
      await loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    let mounted = true
    loadData().catch((err) => {
      if (mounted) setError(err.message)
    })
    const interval = setInterval(() => {
      loadData().catch((err) => {
        if (mounted) setError(err.message)
      })
    }, 30000)
    return () => {
      mounted = false
      clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  return (
    <section className="page-grid">
      <article className="page-banner">
        <p className="eyebrow">Control Tower</p>
        <h2>Backoffice operations and reliability</h2>
        <p>
          Supervision unifiee du reseau: incidents, claims SLA, SMS queue, outbox event-driven, alertes
          critiques et marges assurance.
        </p>
        <p style={{ marginTop: 8 }}>
          <span className={`badge ${s1Health.tone}`}>{s1Health.label}</span>
        </p>
        <p className="kpi-subline">{s1Health.reasons.join(' | ')}</p>
      </article>

      <section className="kpi-grid">
        <article className="kpi-card">
          <p>S1 On-time rate</p>
          <h3>{pct(s1Kpis?.on_time_rate)}</h3>
          <p className="kpi-subline">window {s1Kpis?.window_hours ?? 168}h</p>
        </article>
        <article className="kpi-card">
          <p>S1 Incident rate</p>
          <h3>{pct(s1Kpis?.incident_rate)}</h3>
          <p className="kpi-subline">incidents {s1Kpis?.incident_count ?? '-'}</p>
        </article>
        <article className="kpi-card">
          <p>S1 Scan compliance</p>
          <h3>{pct(s1Kpis?.scan_compliance)}</h3>
          <p className="kpi-subline">eligible {s1Kpis?.scan_eligible_count ?? '-'}</p>
        </article>
        <article className="kpi-card">
          <p>Colis aujourd hui</p>
          <h3>{overview?.shipments_today ?? '-'}</h3>
          <p className="kpi-subline">claims pending {claimsStats?.pending ?? '-'}</p>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Actions operations</h3>
          <div className="ops-actions">
            <button type="button" onClick={onDispatchSms}>
              Dispatch SMS queue
            </button>
            <button type="button" onClick={onAutoDetectIncidents}>
              Auto-detect incidents retard
            </button>
            <button type="button" onClick={onNotifyCriticalAlertsSms}>
              Notifier alertes critiques
            </button>
            <button type="button" onClick={onEscalateClaimsSla}>
              Escalader claims SLA
            </button>
            <button type="button" onClick={onRunShipmentSchedulesDueNow}>
              Forcer run-due schedules
            </button>
          </div>

          <div className="stack-compact" style={{ marginTop: 12 }}>
            {dispatchResult ? (
              <div className="data-row">
                <span>SMS dispatch</span>
                <strong>
                  scanned {dispatchResult.scanned} / delivered {dispatchResult.delivered} / dead {dispatchResult.dead}
                </strong>
              </div>
            ) : null}
            {autoDetectResult ? (
              <div className="data-row">
                <span>Auto-detect incidents</span>
                <strong>
                  examined {autoDetectResult.examined} / created {autoDetectResult.created}
                </strong>
              </div>
            ) : null}
            {notifyCriticalResult ? (
              <div className="data-row">
                <span>Critical alerts notification</span>
                <strong>
                  sent {notifyCriticalResult.sent_count} / recipients {notifyCriticalResult.recipients_count}
                </strong>
              </div>
            ) : null}
            {claimsEscalationResult ? (
              <div className="data-row">
                <span>Claims escalation</span>
                <strong>
                  escalated {claimsEscalationResult.escalated} / notified {claimsEscalationResult.notified_recipients}
                </strong>
              </div>
            ) : null}
            {shipmentSchedulesRunResult ? (
              <div className="data-row">
                <span>Shipment schedules run-due</span>
                <strong>
                  examined {shipmentSchedulesRunResult.examined} / triggered {shipmentSchedulesRunResult.triggered} /
                  failed {shipmentSchedulesRunResult.failed}
                </strong>
              </div>
            ) : null}
          </div>
        </article>

        <article className="panel">
          <h3>Etat worker</h3>
          <div className="stack-compact">
            <div className="data-row">
              <span>Worker SMS</span>
              <strong>{workerStatus?.running ? 'running' : 'stopped'}</strong>
            </div>
            <div className="data-row">
              <span>Interval / batch</span>
              <strong>
                {workerStatus?.interval_seconds ?? '-'}s / {workerStatus?.batch_size ?? '-'}
              </strong>
            </div>
            <div className="data-row">
              <span>Leader lock</span>
              <strong>
                {workerStatus?.leader_mode || '-'} ({workerStatus?.leader_acquired ? 'acquired' : 'not acquired'})
              </strong>
            </div>
            <div className="data-row">
              <span>Claims auto-escalate</span>
              <strong>
                {workerStatus?.claims_auto_escalate_enabled ? 'on' : 'off'} / {workerStatus?.claims_auto_escalate_interval_seconds ?? '-'}s
              </strong>
            </div>
            <div className="data-row">
              <span>Shipment schedules autorun</span>
              <strong>
                {workerStatus?.shipment_schedule_autorun_enabled ? 'on' : 'off'} /{' '}
                {workerStatus?.shipment_schedule_autorun_interval_seconds ?? '-'}s / limit{' '}
                {workerStatus?.shipment_schedule_autorun_limit ?? '-'}
              </strong>
            </div>
            <div className="data-row">
              <span>Outbox worker</span>
              <strong>
                {workerStatus?.outbox_worker_enabled ? 'on' : 'off'} / {workerStatus?.outbox_interval_seconds ?? '-'}s / batch {workerStatus?.outbox_batch_size ?? '-'}
              </strong>
            </div>
            {workerStatus?.outbox_status_counts ? (
              <div className="surface-soft">
                <p className="mono">outbox_status_counts: {JSON.stringify(workerStatus.outbox_status_counts)}</p>
              </div>
            ) : null}
            {workerStatus?.last_run_at ? <p className="muted-note">SMS last run: {workerStatus.last_run_at}</p> : null}
            {workerStatus?.last_outbox_run_at ? (
              <p className="muted-note">Outbox last run: {workerStatus.last_outbox_run_at}</p>
            ) : null}
            {workerStatus?.last_shipment_schedule_run_at ? (
              <p className="muted-note">Shipment schedules last run: {workerStatus.last_shipment_schedule_run_at}</p>
            ) : null}
            {workerStatus?.last_error ? <p className="error">SMS worker: {workerStatus.last_error}</p> : null}
            {workerStatus?.last_outbox_error ? <p className="error">Outbox: {workerStatus.last_outbox_error}</p> : null}
            {workerStatus?.last_shipment_schedule_error ? (
              <p className="error">Shipment schedules: {workerStatus.last_shipment_schedule_error}</p>
            ) : null}
          </div>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Alertes operationnelles</h3>
          <div className="premium-table-wrap list-scroll">
            {alerts.length === 0 ? (
              <p>Aucune alerte</p>
            ) : (
              <table className="premium-table">
                <thead>
                  <tr>
                    <th>Signal</th>
                    <th>Niveau</th>
                    <th>Alerte</th>
                    <th>Colis</th>
                    <th>Statut bloque</th>
                    <th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((alert, idx) => {
                    const parsed = parseDelayDetails(alert.details)
                    return (
                      <tr key={`${alert.code}-${idx}`}>
                        <td>{severityIcon(alert.severity)}</td>
                        <td>
                          <span className={`badge ${severityBadge(alert.severity)}`}>{alert.severity || '-'}</span>
                        </td>
                        <td>{alert.title || '-'}</td>
                        <td>
                          <strong>{parsed.shipmentNo}</strong>
                        </td>
                        <td>{parsed.blockedStatus !== '-' ? parsed.blockedStatus : '-'}</td>
                        <td>{parsed.text || '-'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </article>

        <article className="panel">
          <h3>Finance assurance (6 mois)</h3>
          <div className="premium-table-wrap list-scroll">
            {Array.isArray(claimsFinance?.points) && claimsFinance.points.length > 0 ? (
              <table className="premium-table">
                <thead>
                  <tr>
                    <th>Trend</th>
                    <th>Mois</th>
                    <th>Primes</th>
                    <th>Paid</th>
                    <th>Margin</th>
                    <th>Loss ratio</th>
                    <th>Approved</th>
                  </tr>
                </thead>
                <tbody>
                  {claimsFinance.points.map((point) => (
                    <tr key={point.month}>
                      <td>{financeIcon(point)}</td>
                      <td>
                        <strong>{point.month}</strong>
                      </td>
                      <td>{fmtMoney(point.premiums_collected)}</td>
                      <td>{fmtMoney(point.claims_paid)}</td>
                      <td>{fmtMoney(point.margin)}</td>
                      <td>{fmtRatio(point.loss_ratio_pct)}</td>
                      <td>{point.claims_approved}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p>Aucune donnee finance.</p>
            )}
          </div>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Logs SMS et USSD</h3>
          <div className="relay-list list-scroll">
            {smsLogs.map((log) => (
              <div key={log.id} className="relay-item">
                <p>
                  <span className={`badge ${severityBadge(log.delivery_status)}`}>{log.delivery_status || '-'}</span>
                </p>
                <p>
                  <strong>{log.phone || '-'}</strong>
                </p>
                <p>{log.message}</p>
              </div>
            ))}
            {ussdLogs.map((log) => (
              <div key={log.id} className="relay-item">
                <p>
                  <span className="badge info">USSD</span>
                </p>
                <p className="mono">session {log.session_id}</p>
                <p>{log.payload || '(vide)'}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h3>Audit et erreurs recentes</h3>
          <div className="relay-list list-scroll">
            {auditLogs.map((log) => (
              <div key={log.id} className="relay-item">
                <p>
                  <strong>{log.entity || '-'}</strong> | {log.action || '-'}
                </p>
                <p>
                  {log.method || '-'} {log.endpoint || '-'} | status {log.status_code ?? '-'}
                </p>
              </div>
            ))}
            {recentErrors.map((item, idx) => (
              <div key={`${item.source}-${idx}`} className="relay-item">
                <p>
                  <span className="badge danger">{item.source}</span>
                </p>
                <pre className="ussd-response">{JSON.stringify(item.record, null, 2)}</pre>
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
