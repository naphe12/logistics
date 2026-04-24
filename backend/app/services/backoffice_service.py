from datetime import UTC, datetime, timedelta
import hashlib
import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import (
    OPS_ALERT_SMS_MAX_PER_HOUR,
    OPS_ALERT_SMS_MAX_RECIPIENTS,
    OPS_ALERT_SMS_THROTTLE_MINUTES,
    OPS_DELAY_RISK_HOURS,
    OPS_RELAY_UTILIZATION_WARN,
)
from app.models.audit import AuditLog
from app.models.incidents import Incident
from app.models.notifications import Notification
from app.models.relays import RelayPoint
from app.models.shipments import RelayInventory
from app.models.payments import PaymentTransaction
from app.models.shipments import Shipment
from app.models.statuses import IncidentStatus
from app.models.transport import Trip
from app.models.ussd import UssdLog
from app.models.users import User
from app.enums import NotificationChannelEnum, UserTypeEnum
from app.services.audit_service import log_action
from app.services.notification_service import queue_and_send_sms


def get_backoffice_overview(db: Session) -> dict:
    now = datetime.now(UTC)
    since_24h = now - timedelta(hours=24)
    today_start = datetime(now.year, now.month, now.day, tzinfo=UTC)

    shipments_total = db.query(Shipment).count()
    shipments_today = db.query(Shipment).filter(Shipment.created_at >= today_start).count()
    payments_total = db.query(PaymentTransaction).count()
    payments_failed_24h = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.status == "failed", PaymentTransaction.updated_at >= since_24h)
        .count()
    )
    incidents_open = db.query(Incident).filter(Incident.status.in_(["open", "investigating"])).count()
    incidents_total = db.query(Incident).count()
    notifications_failed_24h = (
        db.query(Notification)
        .filter(Notification.delivery_status == "failed", Notification.created_at >= since_24h)
        .count()
    )
    notifications_pending = (
        db.query(Notification)
        .filter(Notification.delivery_status.in_(["queued", "failed", "processing"]))
        .count()
    )
    notifications_dead = db.query(Notification).filter(Notification.delivery_status == "dead").count()
    ussd_requests_24h = db.query(UssdLog).filter(UssdLog.created_at >= since_24h).count()
    trips_in_progress = db.query(Trip).filter(Trip.status == "in_progress").count()

    status_rows = (
        db.query(func.coalesce(Shipment.status, "unknown"), func.count(Shipment.id))
        .group_by(Shipment.status)
        .all()
    )
    shipment_status_breakdown = [
        {"key": key, "value": value}
        for key, value in status_rows
    ]

    return {
        "shipments_total": shipments_total,
        "shipments_today": shipments_today,
        "payments_total": payments_total,
        "payments_failed_24h": payments_failed_24h,
        "incidents_open": incidents_open,
        "incidents_total": incidents_total,
        "notifications_failed_24h": notifications_failed_24h,
        "notifications_pending": notifications_pending,
        "notifications_dead": notifications_dead,
        "ussd_requests_24h": ussd_requests_24h,
        "trips_in_progress": trips_in_progress,
        "shipment_status_breakdown": shipment_status_breakdown,
    }


def list_sms_logs(db: Session, *, limit: int = 100) -> list[Notification]:
    return (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


def list_ussd_logs(db: Session, *, limit: int = 100) -> list[UssdLog]:
    return db.query(UssdLog).order_by(UssdLog.created_at.desc()).limit(limit).all()


def list_audit_logs(db: Session, *, limit: int = 100) -> list[AuditLog]:
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()


def list_recent_errors(db: Session, *, limit: int = 100) -> list[dict]:
    sms_failed = (
        db.query(Notification)
        .filter(Notification.delivery_status.in_(["failed", "dead"]))
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )

    rows: list[dict] = []
    for item in sms_failed:
        rows.append(
            {
                "source": "sms",
                "record": {
                    "id": str(item.id),
                    "phone": item.phone,
                    "attempts_count": item.attempts_count,
                    "max_attempts": item.max_attempts,
                    "error_message": item.error_message,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                },
            }
        )
    return rows[:limit]


def list_operational_alerts(
    db: Session,
    *,
    delayed_hours: int = OPS_DELAY_RISK_HOURS,
    relay_utilization_warn: float = OPS_RELAY_UTILIZATION_WARN,
    limit: int = 200,
) -> list[dict]:
    alerts: list[dict] = []
    warn_threshold = min(max(relay_utilization_warn, 0.0), 1.0)

    relays = db.query(RelayPoint).filter(RelayPoint.is_active.is_(True)).all()
    for relay in relays:
        if relay.storage_capacity is None or relay.storage_capacity <= 0:
            continue
        current_present = (
            db.query(RelayInventory)
            .filter(RelayInventory.relay_id == relay.id, RelayInventory.present.is_(True))
            .count()
        )
        utilization = current_present / relay.storage_capacity
        if current_present >= relay.storage_capacity:
            alerts.append(
                {
                    "code": "relay_full",
                    "severity": "critical",
                    "title": "Relais saturé",
                    "details": f"{relay.name or relay.relay_code} est plein ({current_present}/{relay.storage_capacity}).",
                    "context": {
                        "relay_id": str(relay.id),
                        "relay_code": relay.relay_code,
                        "current_present": current_present,
                        "storage_capacity": relay.storage_capacity,
                        "utilization_ratio": utilization,
                    },
                }
            )
        elif utilization >= warn_threshold:
            alerts.append(
                {
                    "code": "relay_near_capacity",
                    "severity": "warning",
                    "title": "Relais proche saturation",
                    "details": f"{relay.name or relay.relay_code} à {utilization:.0%} de capacité.",
                    "context": {
                        "relay_id": str(relay.id),
                        "relay_code": relay.relay_code,
                        "current_present": current_present,
                        "storage_capacity": relay.storage_capacity,
                        "utilization_ratio": utilization,
                    },
                }
            )

    since = datetime.now(UTC) - timedelta(hours=max(1, delayed_hours))
    delayed_candidates = (
        db.query(Shipment)
        .filter(
            Shipment.created_at <= since,
            Shipment.status.in_(["picked_up", "in_transit", "arrived_at_relay", "ready_for_pickup"]),
        )
        .order_by(Shipment.created_at.asc())
        .limit(limit)
        .all()
    )
    for shipment in delayed_candidates:
        alerts.append(
            {
                "code": "shipment_delay_risk",
                "severity": "warning",
                "title": "Risque de retard",
                "details": f"Colis {shipment.shipment_no} bloqué en statut {shipment.status}.",
                "context": {
                    "shipment_id": str(shipment.id),
                    "shipment_no": shipment.shipment_no,
                    "status": shipment.status,
                    "created_at": shipment.created_at.isoformat() if shipment.created_at else None,
                    "threshold_hours": delayed_hours,
                },
            }
        )

    alerts.sort(key=lambda item: 0 if item["severity"] == "critical" else 1)
    return alerts[:limit]


def auto_detect_delay_incidents(
    db: Session,
    *,
    delayed_hours: int = OPS_DELAY_RISK_HOURS,
    limit: int = 200,
) -> dict:
    open_status_exists = db.query(IncidentStatus.code).filter(IncidentStatus.code == "open").first()
    if not open_status_exists:
        raise ValueError("Incident status 'open' is not configured")

    since = datetime.now(UTC) - timedelta(hours=max(1, delayed_hours))
    candidates = (
        db.query(Shipment)
        .filter(
            Shipment.created_at <= since,
            Shipment.status.in_(["picked_up", "in_transit", "arrived_at_relay", "ready_for_pickup"]),
        )
        .order_by(Shipment.created_at.asc())
        .limit(limit)
        .all()
    )

    created = 0
    skipped_existing = 0
    for shipment in candidates:
        existing = (
            db.query(Incident.id)
            .filter(
                Incident.shipment_id == shipment.id,
                Incident.incident_type == "delayed",
                Incident.status.in_(["open", "investigating"]),
            )
            .first()
        )
        if existing:
            skipped_existing += 1
            continue
        db.add(
            Incident(
                shipment_id=shipment.id,
                incident_type="delayed",
                description=f"Auto-detected delay risk after {delayed_hours}h in status '{shipment.status}'.",
                status="open",
            )
        )
        created += 1

    if created > 0:
        log_action(db, entity="incidents", action="auto_detect_delay")
    db.commit()
    return {
        "examined": len(candidates),
        "created": created,
        "skipped_existing": skipped_existing,
        "delayed_hours": max(1, delayed_hours),
    }


def _critical_alerts_fingerprint(alerts: list[dict]) -> str:
    payload = [
        {
            "code": item.get("code"),
            "title": item.get("title"),
            "context": item.get("context"),
        }
        for item in alerts
    ]
    text = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def notify_critical_alerts_sms(
    db: Session,
    *,
    delayed_hours: int = OPS_DELAY_RISK_HOURS,
    relay_utilization_warn: float = OPS_RELAY_UTILIZATION_WARN,
    throttle_minutes: int = OPS_ALERT_SMS_THROTTLE_MINUTES,
    max_recipients: int = OPS_ALERT_SMS_MAX_RECIPIENTS,
    max_per_hour: int = OPS_ALERT_SMS_MAX_PER_HOUR,
) -> dict:
    alerts = list_operational_alerts(
        db,
        delayed_hours=delayed_hours,
        relay_utilization_warn=relay_utilization_warn,
        limit=500,
    )
    critical_alerts = [item for item in alerts if item.get("severity") == "critical"]
    if not critical_alerts:
        return {
            "alerts_considered": len(alerts),
            "critical_count": 0,
            "recipients_count": 0,
            "sent_count": 0,
            "skipped_reason": "no_critical_alerts",
            "throttle_minutes": max(1, throttle_minutes),
            "max_per_hour": max(1, max_per_hour),
        }

    since = datetime.now(UTC) - timedelta(minutes=max(1, throttle_minutes))
    recent_any = (
        db.query(Notification.id)
        .filter(
            Notification.channel == NotificationChannelEnum.sms,
            Notification.created_at >= since,
            Notification.message.like("ALERT_CRITICAL|%"),
        )
        .first()
    )
    if recent_any:
        return {
            "alerts_considered": len(alerts),
            "critical_count": len(critical_alerts),
            "recipients_count": 0,
            "sent_count": 0,
            "skipped_reason": "cooldown_active",
            "throttle_minutes": max(1, throttle_minutes),
            "max_per_hour": max(1, max_per_hour),
        }

    fingerprint = _critical_alerts_fingerprint(critical_alerts)
    recent_same = (
        db.query(Notification.id)
        .filter(
            Notification.channel == NotificationChannelEnum.sms,
            Notification.created_at >= since,
            Notification.message.like(f"ALERT_CRITICAL|fp={fingerprint}|%"),
        )
        .first()
    )
    if recent_same:
        return {
            "alerts_considered": len(alerts),
            "critical_count": len(critical_alerts),
            "recipients_count": 0,
            "sent_count": 0,
            "skipped_reason": "duplicate_fingerprint",
            "throttle_minutes": max(1, throttle_minutes),
            "max_per_hour": max(1, max_per_hour),
        }

    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    sent_last_hour = (
        db.query(Notification.id)
        .filter(
            Notification.channel == NotificationChannelEnum.sms,
            Notification.created_at >= one_hour_ago,
            Notification.message.like("ALERT_CRITICAL|%"),
        )
        .count()
    )
    if sent_last_hour >= max(1, max_per_hour):
        return {
            "alerts_considered": len(alerts),
            "critical_count": len(critical_alerts),
            "recipients_count": 0,
            "sent_count": 0,
            "skipped_reason": "hourly_rate_limited",
            "throttle_minutes": max(1, throttle_minutes),
            "max_per_hour": max(1, max_per_hour),
        }

    recipients = (
        db.query(User.phone_e164)
        .filter(User.user_type.in_([UserTypeEnum.admin, UserTypeEnum.hub]))
        .order_by(User.created_at.asc())
        .limit(max(1, max_recipients))
        .all()
    )
    phones = sorted({row.phone_e164 for row in recipients if row.phone_e164})
    if not phones:
        return {
            "alerts_considered": len(alerts),
            "critical_count": len(critical_alerts),
            "recipients_count": 0,
            "sent_count": 0,
            "skipped_reason": "no_recipients",
            "throttle_minutes": max(1, throttle_minutes),
            "max_per_hour": max(1, max_per_hour),
        }

    highlights = ", ".join(item["title"] for item in critical_alerts[:2])
    if len(critical_alerts) > 2:
        highlights = f"{highlights}, +{len(critical_alerts) - 2} autres"
    message = f"ALERT_CRITICAL|fp={fingerprint}|n={len(critical_alerts)}|{highlights}"

    sent_count = 0
    for phone in phones:
        queue_and_send_sms(db, phone, message, background_tasks=None)
        sent_count += 1

    log_action(db, entity="alerts", action="notify_critical_sms")
    return {
        "alerts_considered": len(alerts),
        "critical_count": len(critical_alerts),
        "recipients_count": len(phones),
        "sent_count": sent_count,
        "skipped_reason": None,
        "throttle_minutes": max(1, throttle_minutes),
        "max_per_hour": max(1, max_per_hour),
    }
