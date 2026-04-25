import { useEffect, useState } from 'react'
import {
  autoEscalateClaims,
  dispatchBackofficeSms,
  getBackofficeOverview,
  getBackofficeSmsWorkerStatus,
  getClaimsFinanceReport,
  getClaimsOpsStats,
  listBackofficeAlerts,
  listBackofficeAuditLogs,
  listBackofficeErrors,
  listBackofficeSmsLogs,
  listBackofficeUssdLogs,
  notifyBackofficeCriticalAlertsSms,
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

  const [dispatchResult, setDispatchResult] = useState(null)
  const [autoDetectResult, setAutoDetectResult] = useState(null)
  const [notifyCriticalResult, setNotifyCriticalResult] = useState(null)
  const [claimsEscalationResult, setClaimsEscalationResult] = useState(null)

  async function loadData() {
    if (!token) return
    const [ov, worker, opsAlerts, sms, ussd, audit, errs, claimStats, claimFinance] = await Promise.all([
      getBackofficeOverview(token),
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
    setWorkerStatus(worker)
    setAlerts(opsAlerts || [])
    setSmsLogs(sms || [])
    setUssdLogs(ussd || [])
    setAuditLogs(audit || [])
    setRecentErrors(errs || [])
    setClaimsStats(claimStats || null)
    setClaimsFinance(claimFinance || null)
  }

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
      </article>

      <section className="kpi-grid">
        <article className="kpi-card">
          <p>Colis aujourd hui</p>
          <h3>{overview?.shipments_today ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>Incidents ouverts</p>
          <h3>{overview?.incidents_open ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>Claims en attente</p>
          <h3>{claimsStats?.pending ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>Claims retard SLA</p>
          <h3>{claimsStats?.pending_over_sla ?? '-'}</h3>
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
            {workerStatus?.last_error ? <p className="error">SMS worker: {workerStatus.last_error}</p> : null}
            {workerStatus?.last_outbox_error ? <p className="error">Outbox: {workerStatus.last_outbox_error}</p> : null}
          </div>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Alertes operationnelles</h3>
          <div className="relay-list list-scroll">
            {alerts.length === 0 ? <p>Aucune alerte</p> : null}
            {alerts.map((alert, idx) => (
              <div key={`${alert.code}-${idx}`} className="relay-item">
                <p>
                  <span className={`badge ${severityBadge(alert.severity)}`}>{alert.severity}</span>
                </p>
                <p>
                  <strong>{alert.title}</strong>
                </p>
                <p>{alert.details}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h3>Finance assurance (6 mois)</h3>
          <div className="relay-list list-scroll">
            {Array.isArray(claimsFinance?.points) && claimsFinance.points.length > 0 ? (
              claimsFinance.points.map((point) => (
                <div key={point.month} className="relay-item">
                  <p>
                    <strong>{point.month}</strong>
                  </p>
                  <p>primes {point.premiums_collected} | paid {point.claims_paid}</p>
                  <p>
                    margin {point.margin} | loss ratio {point.loss_ratio_pct}% | approved {point.claims_approved}
                  </p>
                </div>
              ))
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
