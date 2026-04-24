from datetime import UTC, datetime, timedelta
import threading
import time

from sqlalchemy import text

from app.config import (
    OPS_ALERT_AUTONOTIFY_ENABLED,
    OPS_ALERT_AUTONOTIFY_INTERVAL_SECONDS,
    OPS_ALERT_SMS_MAX_PER_HOUR,
    SMS_QUEUE_AUTODISPATCH_BATCH,
    SMS_QUEUE_AUTODISPATCH_ENABLED,
    SMS_QUEUE_AUTODISPATCH_INTERVAL_SECONDS,
    SMS_QUEUE_LEADER_LOCK_ENABLED,
    SMS_QUEUE_LEADER_LOCK_KEY,
)
from app.database import SessionLocal
from app.services.backoffice_service import notify_critical_alerts_sms
from app.services.notification_service import process_pending_sms


_worker_thread: threading.Thread | None = None
_worker_stop_event = threading.Event()
_status_lock = threading.Lock()
_status: dict[str, object] = {
    "running": False,
    "enabled": SMS_QUEUE_AUTODISPATCH_ENABLED,
    "interval_seconds": SMS_QUEUE_AUTODISPATCH_INTERVAL_SECONDS,
    "batch_size": SMS_QUEUE_AUTODISPATCH_BATCH,
    "leader_lock_enabled": SMS_QUEUE_LEADER_LOCK_ENABLED,
    "leader_lock_key": SMS_QUEUE_LEADER_LOCK_KEY,
    "leader_acquired": False,
    "leader_mode": "unknown",
    "ops_alert_autonotify_enabled": OPS_ALERT_AUTONOTIFY_ENABLED,
    "ops_alert_interval_seconds": OPS_ALERT_AUTONOTIFY_INTERVAL_SECONDS,
    "ops_alert_max_per_hour": OPS_ALERT_SMS_MAX_PER_HOUR,
    "last_run_at": None,
    "last_result": None,
    "last_error": None,
    "last_ops_alert_run_at": None,
    "last_ops_alert_result": None,
    "last_ops_alert_error": None,
}


def _utc_iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _set_status(**kwargs: object) -> None:
    with _status_lock:
        for key, value in kwargs.items():
            _status[key] = value


def _try_acquire_leader_lock(lock_db) -> tuple[bool, str]:
    if not SMS_QUEUE_LEADER_LOCK_ENABLED:
        return True, "disabled"

    dialect = lock_db.get_bind().dialect.name
    if dialect != "postgresql":
        return True, "no_lock_non_postgres"

    acquired = bool(
        lock_db.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": SMS_QUEUE_LEADER_LOCK_KEY},
        ).scalar()
    )
    lock_db.commit()
    return acquired, "postgres_advisory_lock"


def _release_leader_lock(lock_db, leader_mode: str, leader_acquired: bool) -> None:
    if not lock_db or not leader_acquired:
        return
    if leader_mode != "postgres_advisory_lock":
        return
    try:
        lock_db.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": SMS_QUEUE_LEADER_LOCK_KEY},
        )
        lock_db.commit()
    except Exception:
        lock_db.rollback()


def _wait_interval_or_stop() -> None:
    waited = 0.0
    interval = max(1, float(SMS_QUEUE_AUTODISPATCH_INTERVAL_SECONDS))
    while waited < interval and not _worker_stop_event.is_set():
        chunk = min(0.5, interval - waited)
        time.sleep(chunk)
        waited += chunk


def _run_loop() -> None:
    lock_db = None
    leader_mode = "unknown"
    leader_acquired = False
    _set_status(running=True, last_error=None)

    try:
        lock_db = SessionLocal()
        leader_acquired, leader_mode = _try_acquire_leader_lock(lock_db)
        _set_status(leader_acquired=leader_acquired, leader_mode=leader_mode)
    except Exception as exc:
        if lock_db:
            lock_db.close()
            lock_db = None
        _set_status(
            leader_acquired=False,
            leader_mode="lock_error",
            last_run_at=_utc_iso_now(),
            last_error=str(exc)[:2000],
        )

    next_ops_alert_check_at = datetime.now(UTC)
    while not _worker_stop_event.is_set():
        if not leader_acquired:
            # No leadership: wait and retry lock acquisition.
            _wait_interval_or_stop()
            if _worker_stop_event.is_set():
                break
            try:
                if lock_db:
                    lock_db.close()
                lock_db = SessionLocal()
                leader_acquired, leader_mode = _try_acquire_leader_lock(lock_db)
                _set_status(leader_acquired=leader_acquired, leader_mode=leader_mode)
            except Exception as exc:
                _set_status(
                    leader_acquired=False,
                    leader_mode="lock_error",
                    last_run_at=_utc_iso_now(),
                    last_error=str(exc)[:2000],
                )
            continue

        run_db = SessionLocal()
        try:
            result = process_pending_sms(run_db, limit=SMS_QUEUE_AUTODISPATCH_BATCH)
            _set_status(
                last_run_at=_utc_iso_now(),
                last_result=result,
                last_error=None,
            )
        except Exception as exc:
            _set_status(
                last_run_at=_utc_iso_now(),
                last_error=str(exc)[:2000],
            )
        finally:
            run_db.close()

        if OPS_ALERT_AUTONOTIFY_ENABLED and datetime.now(UTC) >= next_ops_alert_check_at:
            ops_db = SessionLocal()
            try:
                ops_result = notify_critical_alerts_sms(
                    ops_db,
                    max_per_hour=OPS_ALERT_SMS_MAX_PER_HOUR,
                )
                _set_status(
                    last_ops_alert_run_at=_utc_iso_now(),
                    last_ops_alert_result=ops_result,
                    last_ops_alert_error=None,
                )
            except Exception as exc:
                _set_status(
                    last_ops_alert_run_at=_utc_iso_now(),
                    last_ops_alert_error=str(exc)[:2000],
                )
            finally:
                ops_db.close()
            interval = max(30, OPS_ALERT_AUTONOTIFY_INTERVAL_SECONDS)
            next_ops_alert_check_at = datetime.now(UTC) + timedelta(seconds=interval)

        _wait_interval_or_stop()

    _release_leader_lock(lock_db, leader_mode, leader_acquired)
    if lock_db:
        lock_db.close()
    _set_status(running=False, leader_acquired=False)


def start_sms_queue_worker() -> None:
    global _worker_thread
    if not SMS_QUEUE_AUTODISPATCH_ENABLED:
        _set_status(enabled=False, running=False, leader_acquired=False, leader_mode="disabled")
        return

    if _worker_thread and _worker_thread.is_alive():
        return

    _worker_stop_event.clear()
    _set_status(
        enabled=True,
        leader_lock_enabled=SMS_QUEUE_LEADER_LOCK_ENABLED,
        leader_lock_key=SMS_QUEUE_LEADER_LOCK_KEY,
        ops_alert_autonotify_enabled=OPS_ALERT_AUTONOTIFY_ENABLED,
        ops_alert_interval_seconds=OPS_ALERT_AUTONOTIFY_INTERVAL_SECONDS,
        ops_alert_max_per_hour=OPS_ALERT_SMS_MAX_PER_HOUR,
    )
    _worker_thread = threading.Thread(target=_run_loop, name="sms-queue-worker", daemon=True)
    _worker_thread.start()


def stop_sms_queue_worker(timeout_seconds: float = 5.0) -> None:
    global _worker_thread
    if not _worker_thread:
        return
    _worker_stop_event.set()
    _worker_thread.join(timeout=timeout_seconds)
    _worker_thread = None
    _set_status(running=False, leader_acquired=False)


def get_sms_queue_worker_status() -> dict[str, object]:
    with _status_lock:
        return dict(_status)
