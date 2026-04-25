from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import OUTBOX_MAX_ATTEMPTS, SMS_MAX_RETRIES
from app.enums import NotificationChannelEnum
from app.models.notifications import Notification
from app.models.shipments import Shipment
from app.models.sync import EventOutbox
from app.realtime.events import emit_shipment_status_update


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _to_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except Exception:
        return None


def _format_money_bif(value: Decimal | float | int | str | None) -> str:
    if value is None:
        return "0"
    try:
        dec = Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return str(value)
    return f"{dec:.2f}".rstrip("0").rstrip(".")


def _queue_sms(db: Session, *, phone: str | None, message: str) -> bool:
    if not phone:
        return False
    normalized_phone = phone.strip()
    if not normalized_phone:
        return False
    db.add(
        Notification(
            phone=normalized_phone,
            message=message,
            channel=NotificationChannelEnum.sms,
            delivery_status="queued",
            attempts_count=0,
            max_attempts=SMS_MAX_RETRIES,
            next_retry_at=_now_utc(),
            last_attempt_at=None,
        )
    )
    return True


def _queue_shipment_status_notifications(db: Session, payload: dict) -> int:
    shipment_no = payload.get("shipment_no") or "N/A"
    new_status = payload.get("new_status") or "unknown"
    message = f"Colis {shipment_no}: nouveau statut '{new_status}'."
    recipients = {payload.get("sender_phone"), payload.get("receiver_phone")}
    queued = 0
    for phone in recipients:
        if _queue_sms(db, phone=phone, message=message):
            queued += 1
    return queued


def _queue_incident_status_notifications(db: Session, payload: dict) -> int:
    shipment_id = _to_uuid(payload.get("shipment_id"))
    if shipment_id is None:
        return 0
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        return 0

    new_status = payload.get("new_status") or "unknown"
    incident_type = payload.get("incident_type") or "incident"
    message = (
        f"Incident ({incident_type}) du colis {shipment.shipment_no} "
        f"mis a jour: statut '{new_status}'."
    )
    recipients = {shipment.sender_phone, shipment.receiver_phone}
    queued = 0
    for phone in recipients:
        if _queue_sms(db, phone=phone, message=message):
            queued += 1
    return queued


def _queue_claim_status_notifications(db: Session, payload: dict) -> int:
    shipment_id = _to_uuid(payload.get("shipment_id"))
    if shipment_id is None:
        return 0
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        return 0

    new_status = payload.get("new_status") or "unknown"
    amount_approved = payload.get("amount_approved")
    amount_hint = ""
    if amount_approved is not None and str(amount_approved) != "":
        amount_hint = f" Montant approuve: {_format_money_bif(amount_approved)} BIF."

    message = (
        f"Reclamation colis {shipment.shipment_no}: statut '{new_status}'."
        f"{amount_hint}"
    )
    recipients = {shipment.sender_phone, shipment.receiver_phone}
    queued = 0
    for phone in recipients:
        if _queue_sms(db, phone=phone, message=message):
            queued += 1
    return queued


def _emit_shipment_event_realtime(
    db: Session,
    payload: dict,
    *,
    fallback_event_type: str = "shipment_event",
) -> None:
    shipment_id = _to_uuid(payload.get("shipment_id"))
    if shipment_id is None:
        return
    event_type = str(payload.get("event_type") or fallback_event_type)
    relay_id = _to_uuid(payload.get("relay_id"))
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        return
    emit_shipment_status_update(
        shipment_id=shipment_id,
        status=shipment.status or "unknown",
        event_type=event_type,
        relay_id=relay_id,
    )


def _handle_outbox_event(db: Session, event: EventOutbox) -> int:
    payload = event.payload if isinstance(event.payload, dict) else {}
    event_type = (event.event_type or "").strip()
    if event_type == "shipment.event.created":
        _emit_shipment_event_realtime(db, payload, fallback_event_type="shipment_event_created")
        return 0
    if event_type == "shipment.status.changed":
        _emit_shipment_event_realtime(db, payload, fallback_event_type="shipment_status_changed")
        return _queue_shipment_status_notifications(db, payload)
    if event_type == "incident.status.changed":
        return _queue_incident_status_notifications(db, payload)
    if event_type == "claim.status.changed":
        return _queue_claim_status_notifications(db, payload)
    return 0


def _compute_backoff_seconds(attempts_count: int) -> int:
    # Exponential backoff with cap to keep retries bounded.
    return min(1800, 15 * (2 ** max(0, min(attempts_count - 1, 10))))


def process_event_outbox(
    db: Session,
    *,
    limit: int = 100,
    max_attempts: int = OUTBOX_MAX_ATTEMPTS,
) -> dict[str, int]:
    now = _now_utc()
    rows = (
        db.query(EventOutbox)
        .filter(
            EventOutbox.status.in_(["queued", "failed"]),
            EventOutbox.available_at <= now,
            EventOutbox.attempts_count < func.coalesce(EventOutbox.max_attempts, max_attempts),
        )
        .order_by(EventOutbox.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(max(1, min(limit, 1000)))
        .all()
    )

    result = {
        "scanned": len(rows),
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "dead": 0,
        "notifications_queued": 0,
    }
    for row in rows:
        row.status = "processing"
        row.attempts_count = int(row.attempts_count or 0) + 1
        row.last_error = None
        db.flush()

        try:
            queued = _handle_outbox_event(db, row)
            row.status = "done"
            row.processed_at = _now_utc()
            row.last_error = None
            result["succeeded"] += 1
            result["notifications_queued"] += max(0, int(queued))
        except Exception as exc:
            effective_max_attempts = int(row.max_attempts or max_attempts or 1)
            row.last_error = str(exc)[:2000]
            if int(row.attempts_count or 0) >= effective_max_attempts:
                row.status = "dead"
                row.available_at = _now_utc()
                result["dead"] += 1
            else:
                row.status = "failed"
                row.available_at = _now_utc() + timedelta(
                    seconds=_compute_backoff_seconds(int(row.attempts_count or 1))
                )
                result["failed"] += 1
        finally:
            result["processed"] += 1

    db.commit()
    return result


def get_outbox_status_counts(db: Session) -> dict[str, int]:
    rows = (
        db.query(EventOutbox.status, func.count(EventOutbox.id))
        .group_by(EventOutbox.status)
        .all()
    )
    return {str(status or "unknown"): int(count) for status, count in rows}


def reset_stuck_processing_outbox(db: Session, *, stale_minutes: int = 15) -> int:
    stale_minutes = max(1, min(stale_minutes, 24 * 60))
    cutoff = _now_utc() - timedelta(minutes=stale_minutes)
    updated = (
        db.query(EventOutbox)
        .filter(
            EventOutbox.status == "processing",
            EventOutbox.created_at <= cutoff,
        )
        .update(
            {
                EventOutbox.status: "queued",
                EventOutbox.available_at: _now_utc(),
                EventOutbox.last_error: "Recovered from stale processing lock.",
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return int(updated)
