import { useEffect, useState } from 'react'
import {
  dispatchBackofficeSms,
  getBackofficeSmsWorkerStatus,
  getBackofficeOverview,
  listBackofficeAlerts,
  listBackofficeAuditLogs,
  listBackofficeErrors,
  listBackofficeSmsLogs,
  listBackofficeUssdLogs,
  notifyBackofficeCriticalAlertsSms,
  runBackofficeAutoDetectIncidents,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function BackofficePage() {
  const { token } = useAuth()
  const [error, setError] = useState('')
  const [overview, setOverview] = useState(null)
  const [smsLogs, setSmsLogs] = useState([])
  const [ussdLogs, setUssdLogs] = useState([])
  const [auditLogs, setAuditLogs] = useState([])
  const [recentErrors, setRecentErrors] = useState([])
  const [dispatchResult, setDispatchResult] = useState(null)
  const [workerStatus, setWorkerStatus] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [autoDetectResult, setAutoDetectResult] = useState(null)
  const [notifyCriticalResult, setNotifyCriticalResult] = useState(null)

  async function loadData() {
    if (!token) return
    const [ov, sms, ussd, audit, errs, worker, opsAlerts] = await Promise.all([
      getBackofficeOverview(token),
      listBackofficeSmsLogs(token, 50),
      listBackofficeUssdLogs(token, 50),
      listBackofficeAuditLogs(token, 50),
      listBackofficeErrors(token, 50),
      getBackofficeSmsWorkerStatus(token),
      listBackofficeAlerts(token, { delayed_hours: 48, relay_utilization_warn: 0.9, limit: 100 }),
    ])
    setOverview(ov)
    setSmsLogs(sms)
    setUssdLogs(ussd)
    setAuditLogs(audit)
    setRecentErrors(errs)
    setWorkerStatus(worker)
    setAlerts(opsAlerts)
  }

  async function onDispatchSms() {
    if (!token) return
    setError('')
    try {
      const result = await dispatchBackofficeSms(token, 100)
      setDispatchResult(result)
      await loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onAutoDetectIncidents() {
    if (!token) return
    setError('')
    try {
      const result = await runBackofficeAutoDetectIncidents(token, 48, 200)
      setAutoDetectResult(result)
      await loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onNotifyCriticalAlertsSms() {
    if (!token) return
    setError('')
    try {
      const result = await notifyBackofficeCriticalAlertsSms(token, {
        delayedHours: 48,
        relayUtilizationWarn: 0.9,
        throttleMinutes: 30,
        maxRecipients: 20,
        maxPerHour: 4,
      })
      setNotifyCriticalResult(result)
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
      <article className="panel">
        <p className="eyebrow">Backoffice</p>
        <h2>Observabilite operations</h2>
        <p>KPI, logs SMS/USSD, erreurs recentes. Rafraichissement toutes les 30 secondes.</p>
      </article>

      <section className="kpi-grid">
        <article className="kpi-card">
          <p>Colis total</p>
          <h3>{overview?.shipments_total ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>Colis aujourd hui</p>
          <h3>{overview?.shipments_today ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>Trips en cours</p>
          <h3>{overview?.trips_in_progress ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>Paiements total</p>
          <h3>{overview?.payments_total ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>Paiements echoues 24h</p>
          <h3>{overview?.payments_failed_24h ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>Incidents ouverts</p>
          <h3>{overview?.incidents_open ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>SMS pending</p>
          <h3>{overview?.notifications_pending ?? '-'}</h3>
        </article>
        <article className="kpi-card">
          <p>SMS dead</p>
          <h3>{overview?.notifications_dead ?? '-'}</h3>
        </article>
      </section>

      <article className="panel">
        <h3>Dispatch SMS Queue</h3>
        <button type="button" onClick={onDispatchSms}>
          Executer retries SMS
        </button>
        <p>
          Worker: <strong>{workerStatus?.running ? 'running' : 'stopped'}</strong> | enabled:{' '}
          {workerStatus?.enabled ? 'yes' : 'no'} | interval: {workerStatus?.interval_seconds ?? '-'}s | batch:{' '}
          {workerStatus?.batch_size ?? '-'}
        </p>
        <p>
          leader lock: {workerStatus?.leader_lock_enabled ? 'on' : 'off'} | mode:{' '}
          {workerStatus?.leader_mode || '-'} | acquired: {workerStatus?.leader_acquired ? 'yes' : 'no'} | key:{' '}
          {workerStatus?.leader_lock_key ?? '-'}
        </p>
        <p>
          auto-notify: {workerStatus?.ops_alert_autonotify_enabled ? 'on' : 'off'} | interval:{' '}
          {workerStatus?.ops_alert_interval_seconds ?? '-'}s | max/hour:{' '}
          {workerStatus?.ops_alert_max_per_hour ?? '-'}
        </p>
        {workerStatus?.last_run_at ? <p>Last run: {workerStatus.last_run_at}</p> : null}
        {workerStatus?.last_error ? <p>Last error: {workerStatus.last_error}</p> : null}
        {workerStatus?.last_ops_alert_run_at ? <p>Last ops alert run: {workerStatus.last_ops_alert_run_at}</p> : null}
        {workerStatus?.last_ops_alert_error ? <p>Last ops alert error: {workerStatus.last_ops_alert_error}</p> : null}
        {workerStatus?.last_ops_alert_result ? (
          <pre className="ussd-response">{JSON.stringify(workerStatus.last_ops_alert_result, null, 2)}</pre>
        ) : null}
        {dispatchResult ? (
          <p>
            scanned: {dispatchResult.scanned} | delivered: {dispatchResult.delivered} | failed:{' '}
            {dispatchResult.failed} | dead: {dispatchResult.dead}
          </p>
        ) : null}
      </article>

      <article className="panel">
        <h3>Alertes Operationnelles</h3>
        <div className="ops-actions">
          <button type="button" onClick={onAutoDetectIncidents}>
            Auto-detect incidents retard
          </button>
          <button type="button" onClick={onNotifyCriticalAlertsSms}>
            Notifier alertes critiques (SMS)
          </button>
        </div>
        {autoDetectResult ? (
          <p>
            examined: {autoDetectResult.examined} | created: {autoDetectResult.created} | skipped:{' '}
            {autoDetectResult.skipped_existing}
          </p>
        ) : null}
        {notifyCriticalResult ? (
          <p>
            critical: {notifyCriticalResult.critical_count} | recipients: {notifyCriticalResult.recipients_count} |
            sent: {notifyCriticalResult.sent_count} | skipped:{' '}
            {notifyCriticalResult.skipped_reason || 'none'} | max/hour: {notifyCriticalResult.max_per_hour}
          </p>
        ) : null}
        <div className="relay-list">
          {alerts.length === 0 ? <p>Aucune alerte operationnelle</p> : null}
          {alerts.map((alert, idx) => (
            <div key={`${alert.code}-${idx}`} className="relay-item">
              <p>
                <strong>{alert.severity}</strong> | {alert.title}
              </p>
              <p>{alert.details}</p>
              <pre className="ussd-response">{JSON.stringify(alert.context, null, 2)}</pre>
            </div>
          ))}
        </div>
      </article>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Logs SMS</h3>
          <div className="relay-list">
            {smsLogs.length === 0 ? <p>Aucun log SMS</p> : null}
            {smsLogs.map((log) => (
              <div key={log.id} className="relay-item">
                <p>
                  <strong>{log.delivery_status || '-'}</strong> | {log.phone || '-'} | attempts:{' '}
                  {log.attempts_count ?? 0}/{log.max_attempts ?? '-'}
                </p>
                <p>{log.message}</p>
                {log.error_message ? <p>Erreur: {log.error_message}</p> : null}
                {log.next_retry_at ? <p>next retry: {log.next_retry_at}</p> : null}
                {log.last_attempt_at ? <p>last attempt: {log.last_attempt_at}</p> : null}
                <p>{log.created_at}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h3>Logs USSD</h3>
          <div className="relay-list">
            {ussdLogs.length === 0 ? <p>Aucun log USSD</p> : null}
            {ussdLogs.map((log) => (
              <div key={log.id} className="relay-item">
                <p>Session: {log.session_id}</p>
                <p>Payload: {log.payload || '(vide)'}</p>
                <p>{log.created_at}</p>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="page-grid two-cols">
        <article className="panel">
          <h3>Logs Audit</h3>
          <div className="relay-list">
            {auditLogs.length === 0 ? <p>Aucun audit log</p> : null}
            {auditLogs.map((log) => (
              <div key={log.id} className="relay-item">
                <p>
                  entity: {log.entity || '-'} | action: {log.action || '-'}
                </p>
                <p>
                  actor: {log.actor_phone || log.actor_user_id || '-'} | ip: {log.ip_address || '-'}
                </p>
                <p>
                  {log.method || '-'} {log.endpoint || '-'} | status: {log.status_code ?? '-'}
                </p>
                <p>{log.created_at}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h3>Erreurs recentes</h3>
          <div className="relay-list">
            {recentErrors.length === 0 ? <p>Aucune erreur recente</p> : null}
            {recentErrors.map((item, idx) => (
              <div key={`${item.source}-${idx}`} className="relay-item">
                <p>
                  <strong>{item.source}</strong>
                </p>
                <pre className="ussd-response">{JSON.stringify(item.record, null, 2)}</pre>
              </div>
            ))}
          </div>
        </article>
      </section>

      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
