from datetime import UTC, datetime, timedelta
import hashlib
import json
import uuid

from sqlalchemy import String, func, or_
from sqlalchemy.orm import Session

from app.config import (
    OPS_ALERT_SMS_MAX_PER_HOUR,
    OPS_ALERT_SMS_MAX_RECIPIENTS,
    OPS_ALERT_SMS_THROTTLE_MINUTES,
    OPS_DELAY_RISK_HOURS,
    OPS_RELAY_UTILIZATION_WARN,
    SMS_MAX_RETRIES,
)
from app.models.audit import AuditLog
from app.models.incidents import Incident
from app.models.notifications import Notification
from app.models.relays import RelayPoint
from app.models.shipments import RelayInventory
from app.models.payments import PaymentTransaction
from app.models.shipments import Shipment
from app.models.shipments import ShipmentEvent
from app.models.statuses import IncidentStatus
from app.models.transport import Trip
from app.models.ussd import UssdLog
from app.models.users import User
from app.enums import NotificationChannelEnum, UserTypeEnum
from app.services.audit_service import log_action
from app.services.notification_service import queue_and_send_sms
from app.services.user_preferences_service import is_sms_allowed


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
    auto_assign_accepted_24h = (
        db.query(func.coalesce(func.sum(AuditLog.status_code), 0))
        .filter(
            AuditLog.entity == "manifest_shipments",
            AuditLog.action == "auto_assign_accept",
            AuditLog.created_at >= since_24h,
        )
        .scalar()
    ) or 0
    auto_assign_rejected_24h = (
        db.query(func.coalesce(func.sum(AuditLog.status_code), 0))
        .filter(
            AuditLog.entity == "manifest_shipments",
            AuditLog.action == "auto_assign_reject",
            AuditLog.created_at >= since_24h,
        )
        .scalar()
    ) or 0
    auto_assign_total_24h = auto_assign_accepted_24h + auto_assign_rejected_24h
    auto_assign_acceptance_rate_24h = (
        int(round((auto_assign_accepted_24h * 100) / auto_assign_total_24h))
        if auto_assign_total_24h > 0
        else 0
    )

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
        "auto_assign_accepted_24h": int(auto_assign_accepted_24h),
        "auto_assign_rejected_24h": int(auto_assign_rejected_24h),
        "auto_assign_total_24h": int(auto_assign_total_24h),
        "auto_assign_acceptance_rate_24h": int(auto_assign_acceptance_rate_24h),
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


def get_ussd_kpis(db: Session, *, window_hours: int = 24) -> dict:
    window_hours = max(1, min(window_hours, 24 * 30))
    since = datetime.now(UTC) - timedelta(hours=window_hours)

    query = db.query(UssdLog).filter(UssdLog.created_at >= since)
    rows = query.all()

    total_requests = len(rows)
    unique_callers = (
        db.query(func.count(func.distinct(UssdSession.phone)))
        .join(UssdSession, UssdSession.id == UssdLog.session_id)
        .filter(UssdLog.created_at >= since)
        .scalar()
        or 0
    )

    def _payload(row: UssdLog) -> str:
        return (row.payload or "").lower()

    menu_hits = 0
    send_flow_hits = 0
    track_flow_hits = 0
    pickup_flow_hits = 0
    pay_flow_hits = 0
    for row in rows:
        payload = _payload(row)
        if "txt=" in payload and ("txt=" == payload[-4:] or "txt=00" in payload or "txt=menu" in payload):
            menu_hits += 1
        if "txt=1" in payload or "txt=1*" in payload:
            send_flow_hits += 1
        if "txt=2" in payload or "txt=2*" in payload:
            track_flow_hits += 1
        if "txt=3" in payload or "txt=3*" in payload:
            pickup_flow_hits += 1
        if "txt=4" in payload or "txt=4*" in payload:
            pay_flow_hits += 1

    return {
        "window_hours": window_hours,
        "total_requests": int(total_requests),
        "unique_callers": int(unique_callers),
        "menu_hits": int(menu_hits),
        "send_flow_hits": int(send_flow_hits),
        "track_flow_hits": int(track_flow_hits),
        "pickup_flow_hits": int(pickup_flow_hits),
        "pay_flow_hits": int(pay_flow_hits),
    }


def get_s1_ops_kpis(db: Session, *, window_hours: int = 24 * 7) -> dict:
    window_hours = max(1, min(window_hours, 24 * 90))
    since = datetime.now(UTC) - timedelta(hours=window_hours)

    shipments_created = (
        db.query(Shipment.id)
        .filter(Shipment.created_at >= since)
        .count()
    )

    delivered_rows = (
        db.query(Shipment.created_at, Shipment.updated_at)
        .filter(
            Shipment.created_at >= since,
            Shipment.status == "delivered",
            Shipment.created_at.is_not(None),
            Shipment.updated_at.is_not(None),
        )
        .all()
    )
    delivered_count = len(delivered_rows)
    on_time_count = 0
    for created_at, updated_at in delivered_rows:
        elapsed_h = (updated_at - created_at).total_seconds() / 3600.0
        if elapsed_h <= max(1, OPS_DELAY_RISK_HOURS):
            on_time_count += 1
    on_time_rate = round((on_time_count * 100.0) / delivered_count, 2) if delivered_count > 0 else 0.0

    incident_count = (
        db.query(Incident.id)
        .filter(Incident.created_at >= since)
        .count()
    )
    incident_rate = round((incident_count * 100.0) / shipments_created, 2) if shipments_created > 0 else 0.0

    eligible_statuses = {"in_transit", "arrived_at_relay", "ready_for_pickup", "delivered"}
    eligible_shipments = (
        db.query(Shipment.id, Shipment.status)
        .filter(Shipment.created_at >= since, Shipment.status.in_(list(eligible_statuses)))
        .all()
    )
    eligible_count = len(eligible_shipments)
    if eligible_count == 0:
        scan_compliance = 0.0
    else:
        expected_scan_by_shipment: dict[str, int] = {}
        for shipment_id, status in eligible_shipments:
            normalized = (status or "").strip().lower()
            expected_scan_by_shipment[str(shipment_id)] = 1 if normalized == "in_transit" else 2

        scan_rows = (
            db.query(
                ShipmentEvent.shipment_id,
                func.count(ShipmentEvent.id).label("scan_count"),
            )
            .filter(
                ShipmentEvent.shipment_id.in_([shipment_id for shipment_id, _ in eligible_shipments]),
                ShipmentEvent.created_at >= since,
                func.lower(func.coalesce(ShipmentEvent.event_type, "")).in_(
                    ["shipment_departed_trip", "shipment_arrived_trip"]
                ),
            )
            .group_by(ShipmentEvent.shipment_id)
            .all()
        )
        actual_scan_by_shipment = {str(row.shipment_id): int(row.scan_count) for row in scan_rows}

        compliant = 0
        for shipment_id, expected_scans in expected_scan_by_shipment.items():
            if actual_scan_by_shipment.get(shipment_id, 0) >= expected_scans:
                compliant += 1
        scan_compliance = round((compliant * 100.0) / eligible_count, 2)

    return {
        "window_hours": window_hours,
        "on_time_rate": on_time_rate,
        "incident_rate": incident_rate,
        "scan_compliance": scan_compliance,
        "shipments_created": int(shipments_created),
        "delivered_count": int(delivered_count),
        "on_time_count": int(on_time_count),
        "incident_count": int(incident_count),
        "scan_eligible_count": int(eligible_count),
    }


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


def global_search(
    db: Session,
    *,
    q: str,
    limit: int = 50,
) -> dict:
    term = q.strip()
    if not term:
        return {"q": q, "total": 0, "by_entity": {}, "items": []}

    limit = max(1, min(limit, 200))
    like = f"%{term}%"
    items: list[dict] = []

    shipment_rows = (
        db.query(Shipment)
        .filter(
            or_(
                Shipment.shipment_no.ilike(like),
                Shipment.sender_phone.ilike(like),
                Shipment.receiver_phone.ilike(like),
                Shipment.receiver_name.ilike(like),
            )
        )
        .order_by(Shipment.created_at.desc())
        .limit(limit)
        .all()
    )
    for row in shipment_rows:
        items.append(
            {
                "entity": "shipment",
                "id": str(row.id),
                "label": row.shipment_no or str(row.id),
                "status": row.status,
                "created_at": row.created_at,
                "highlights": [item for item in [row.sender_phone, row.receiver_phone, row.receiver_name] if item],
            }
        )

    payment_rows = (
        db.query(PaymentTransaction)
        .filter(
            or_(
                PaymentTransaction.external_ref.ilike(like),
                PaymentTransaction.payer_phone.ilike(like),
            )
        )
        .order_by(PaymentTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
    for row in payment_rows:
        items.append(
            {
                "entity": "payment",
                "id": str(row.id),
                "label": row.external_ref or str(row.id),
                "status": row.status,
                "created_at": row.created_at,
                "highlights": [item for item in [row.payer_phone, row.provider] if item],
            }
        )

    incident_rows = (
        db.query(Incident)
        .filter(
            or_(
                Incident.incident_type.ilike(like),
                Incident.description.ilike(like),
            )
        )
        .order_by(Incident.created_at.desc())
        .limit(limit)
        .all()
    )
    for row in incident_rows:
        items.append(
            {
                "entity": "incident",
                "id": str(row.id),
                "label": row.incident_type or str(row.id),
                "status": row.status,
                "created_at": row.created_at,
                "highlights": [row.description] if row.description else [],
            }
        )

    trip_rows = (
        db.query(Trip)
        .filter(
            or_(
                func.cast(Trip.id, String).ilike(like),
                Trip.status.ilike(like),
            )
        )
        .order_by(Trip.id.desc())
        .limit(limit)
        .all()
    )
    for row in trip_rows:
        items.append(
            {
                "entity": "trip",
                "id": str(row.id),
                "label": str(row.id),
                "status": row.status,
                "created_at": None,
                "highlights": [],
            }
        )

    items.sort(
        key=lambda item: item.get("created_at") or datetime(1970, 1, 1, tzinfo=UTC),
        reverse=True,
    )
    items = items[:limit]

    by_entity: dict[str, int] = {}
    for item in items:
        entity = str(item["entity"])
        by_entity[entity] = by_entity.get(entity, 0) + 1

    return {
        "q": q,
        "total": len(items),
        "by_entity": by_entity,
        "items": items,
    }


def get_backoffice_timeseries(
    db: Session,
    *,
    days: int = 30,
) -> dict:
    days = max(1, min(days, 365))
    now = datetime.now(UTC)
    since = now - timedelta(days=days - 1)
    start_day = since.date()

    shipment_rows = (
        db.query(func.date(Shipment.created_at).label("day"), func.count(Shipment.id).label("count"))
        .filter(Shipment.created_at >= since)
        .group_by(func.date(Shipment.created_at))
        .all()
    )
    payment_rows = (
        db.query(func.date(PaymentTransaction.created_at).label("day"), func.count(PaymentTransaction.id).label("count"))
        .filter(PaymentTransaction.created_at >= since)
        .group_by(func.date(PaymentTransaction.created_at))
        .all()
    )
    incident_rows = (
        db.query(func.date(Incident.created_at).label("day"), func.count(Incident.id).label("count"))
        .filter(Incident.created_at >= since)
        .group_by(func.date(Incident.created_at))
        .all()
    )
    sms_sent_rows = (
        db.query(func.date(Notification.created_at).label("day"), func.count(Notification.id).label("count"))
        .filter(
            Notification.created_at >= since,
            Notification.channel == NotificationChannelEnum.sms,
            Notification.delivery_status == "delivered",
        )
        .group_by(func.date(Notification.created_at))
        .all()
    )
    sms_failed_rows = (
        db.query(func.date(Notification.created_at).label("day"), func.count(Notification.id).label("count"))
        .filter(
            Notification.created_at >= since,
            Notification.channel == NotificationChannelEnum.sms,
            Notification.delivery_status.in_(["failed", "dead"]),
        )
        .group_by(func.date(Notification.created_at))
        .all()
    )

    by_ship = {row.day: int(row.count) for row in shipment_rows}
    by_pay = {row.day: int(row.count) for row in payment_rows}
    by_inc = {row.day: int(row.count) for row in incident_rows}
    by_sms_sent = {row.day: int(row.count) for row in sms_sent_rows}
    by_sms_failed = {row.day: int(row.count) for row in sms_failed_rows}

    points: list[dict] = []
    for i in range(days):
        day = start_day + timedelta(days=i)
        points.append(
            {
                "day": day.isoformat(),
                "shipments_created": by_ship.get(day, 0),
                "payments_created": by_pay.get(day, 0),
                "incidents_created": by_inc.get(day, 0),
                "sms_sent": by_sms_sent.get(day, 0),
                "sms_failed": by_sms_failed.get(day, 0),
            }
        )

    return {"days": days, "points": points}


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


def notify_delay_risk_customers_sms(
    db: Session,
    *,
    delayed_hours: int = OPS_DELAY_RISK_HOURS,
    limit: int = 200,
    throttle_hours: int = 12,
) -> dict:
    delayed_hours = max(1, min(delayed_hours, 24 * 30))
    limit = max(1, min(limit, 1000))
    throttle_hours = max(1, min(throttle_hours, 24 * 14))

    since = datetime.now(UTC) - timedelta(hours=delayed_hours)
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

    alerts_triggered = 0
    recipients_targeted = 0
    notifications_queued = 0
    skipped_throttled = 0
    now = datetime.now(UTC)

    for shipment in candidates:
        extra = shipment.extra if isinstance(shipment.extra, dict) else {}
        delay_alert = extra.get("delay_alert") if isinstance(extra.get("delay_alert"), dict) else {}
        last_sent_raw = delay_alert.get("last_sent_at")
        last_sent_at = None
        if isinstance(last_sent_raw, str):
            try:
                last_sent_at = datetime.fromisoformat(last_sent_raw)
            except Exception:
                last_sent_at = None

        if last_sent_at and (now - last_sent_at) < timedelta(hours=throttle_hours):
            skipped_throttled += 1
            continue

        phones = sorted({p for p in [shipment.sender_phone, shipment.receiver_phone] if p})
        if not phones:
            continue

        message = (
            f"ALERT_DELAY|Colis {shipment.shipment_no} en statut {shipment.status}. "
            "Nous travaillons pour accelerer la livraison."
        )
        for phone in phones:
            queue_and_send_sms(db, phone, message, background_tasks=None)
            notifications_queued += 1
        recipients_targeted += len(phones)
        alerts_triggered += 1

        delay_alert["last_sent_at"] = now.isoformat()
        delay_alert["last_status"] = shipment.status
        delay_alert["delayed_hours_threshold"] = delayed_hours
        extra["delay_alert"] = delay_alert
        shipment.extra = extra

    if alerts_triggered > 0:
        log_action(
            db,
            entity="alerts",
            action="notify_delay_risk_sms",
            status_code=alerts_triggered,
        )
    db.commit()
    return {
        "examined": len(candidates),
        "alerts_triggered": alerts_triggered,
        "recipients_targeted": recipients_targeted,
        "notifications_queued": notifications_queued,
        "skipped_throttled": skipped_throttled,
        "delayed_hours": delayed_hours,
        "throttle_hours": throttle_hours,
    }


def _render_broadcast_message(template: str, user: User) -> str:
    values = {
        "first_name": (user.first_name or "").strip(),
        "last_name": (user.last_name or "").strip(),
        "phone": (user.phone_e164 or "").strip(),
        "role": str(user.user_type.value if hasattr(user.user_type, "value") else user.user_type),
    }
    return template.format(**values)


def preview_broadcast_sms_to_roles(
    db: Session,
    *,
    message: str,
    roles: list[UserTypeEnum] | None = None,
    limit: int = 1000,
    preview_limit: int = 20,
) -> dict:
    selected_roles = roles or [UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent]
    normalized_roles = list(dict.fromkeys(selected_roles))
    limit = max(1, min(limit, 5000))
    preview_limit = max(1, min(preview_limit, 200))

    users = (
        db.query(User)
        .filter(User.user_type.in_(normalized_roles))
        .order_by(User.created_at.asc())
        .limit(limit)
        .all()
    )

    seen_phones: set[str] = set()
    skipped_no_phone = 0
    skipped_render_errors = 0
    items: list[dict] = []
    recipients_count = 0

    for user in users:
        phone = (user.phone_e164 or "").strip()
        if not phone:
            skipped_no_phone += 1
            continue
        if phone in seen_phones:
            continue
        seen_phones.add(phone)
        try:
            rendered = _render_broadcast_message(message, user)
        except Exception:
            skipped_render_errors += 1
            continue
        recipients_count += 1
        if len(items) < preview_limit:
            items.append(
                {
                    "phone": phone,
                    "role": user.user_type,
                    "rendered_message": rendered,
                }
            )

    return {
        "scanned_users": len(users),
        "recipients_count": recipients_count,
        "skipped_no_phone": skipped_no_phone,
        "skipped_render_errors": skipped_render_errors,
        "items": items,
    }


def broadcast_sms_to_roles(
    db: Session,
    *,
    message: str,
    roles: list[UserTypeEnum] | None = None,
    dry_run: bool = False,
    limit: int = 1000,
    respect_preferences: bool = True,
) -> dict:
    preview = preview_broadcast_sms_to_roles(
        db,
        message=message,
        roles=roles,
        limit=limit,
        preview_limit=10,
    )

    recipients = [item["phone"] for item in preview["items"]]
    rendered_by_phone = {item["phone"]: item["rendered_message"] for item in preview["items"]}
    if preview["recipients_count"] > len(recipients):
        selected_roles = roles or [UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent]
        normalized_roles = list(dict.fromkeys(selected_roles))
        users = (
            db.query(User)
            .filter(User.user_type.in_(normalized_roles))
            .order_by(User.created_at.asc())
            .limit(max(1, min(limit, 5000)))
            .all()
        )
        seen_phones: set[str] = set(recipients)
        for user in users:
            phone = (user.phone_e164 or "").strip()
            if not phone or phone in seen_phones:
                continue
            try:
                rendered = _render_broadcast_message(message, user)
            except Exception:
                continue
            seen_phones.add(phone)
            recipients.append(phone)
            rendered_by_phone[phone] = rendered

    notifications_queued = 0
    if not dry_run:
        for phone in recipients:
            queue_and_send_sms(
                db,
                phone,
                rendered_by_phone[phone],
                background_tasks=None,
                respect_preferences=respect_preferences,
            )
            notifications_queued += 1
        if notifications_queued > 0:
            log_action(
                db,
                entity="notifications",
                action="broadcast_sms_roles",
                status_code=notifications_queued,
            )
            db.commit()

    return {
        "scanned_users": preview["scanned_users"],
        "recipients_count": preview["recipients_count"],
        "notifications_queued": notifications_queued,
        "skipped_no_phone": preview["skipped_no_phone"],
        "skipped_render_errors": preview["skipped_render_errors"],
        "dry_run": dry_run,
        "sample_phones": recipients[:10],
        "sample_messages": [rendered_by_phone[phone] for phone in recipients[:10]],
    }


def _build_campaign_marker(campaign_id: str, campaign_name: str | None) -> str:
    safe_name = (campaign_name or "").strip().replace("|", " ")[:120]
    return f"campaign:{campaign_id}|name:{safe_name}"


def _parse_campaign_marker(marker: str | None) -> tuple[str | None, str | None]:
    if not marker or not marker.startswith("campaign:"):
        return None, None


def _notification_campaign(notification: Notification) -> tuple[str | None, str | None]:
    extra = notification.extra if isinstance(notification.extra, dict) else {}
    campaign_id = extra.get("campaign_id")
    campaign_name = extra.get("campaign_name")
    if isinstance(campaign_id, str) and campaign_id.strip():
        normalized_id = campaign_id.strip()
        normalized_name = campaign_name.strip() if isinstance(campaign_name, str) and campaign_name.strip() else None
        return normalized_id, normalized_name
    return _parse_campaign_marker(notification.error_message)
    try:
        head, _, tail = marker.partition("|name:")
        campaign_id = head.split("campaign:", 1)[1].strip()
        campaign_name = tail.strip() or None
        if not campaign_id:
            return None, None
        return campaign_id, campaign_name
    except Exception:
        return None, None


def schedule_sms_campaign_to_roles(
    db: Session,
    *,
    message: str,
    send_at: datetime,
    roles: list[UserTypeEnum] | None = None,
    campaign_name: str | None = None,
    limit: int = 1000,
    respect_preferences: bool = True,
) -> dict:
    if send_at.tzinfo is None:
        send_at = send_at.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if send_at <= now:
        raise ValueError("send_at must be in the future")

    selected_roles = roles or [UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent]
    normalized_roles = list(dict.fromkeys(selected_roles))
    limit = max(1, min(limit, 5000))

    users = (
        db.query(User)
        .filter(User.user_type.in_(normalized_roles))
        .order_by(User.created_at.asc())
        .limit(limit)
        .all()
    )

    campaign_id = uuid.uuid4().hex[:12]
    campaign_name = (campaign_name or "").strip() or None

    seen_phones: set[str] = set()
    recipients_count = 0
    scheduled_count = 0
    skipped_no_phone = 0
    skipped_preferences = 0
    skipped_render_errors = 0

    for user in users:
        phone = (user.phone_e164 or "").strip()
        if not phone:
            skipped_no_phone += 1
            continue
        if phone in seen_phones:
            continue
        seen_phones.add(phone)

        if respect_preferences and not is_sms_allowed(user):
            skipped_preferences += 1
            continue

        try:
            rendered = _render_broadcast_message(message, user)
        except Exception:
            skipped_render_errors += 1
            continue

        recipients_count += 1
        db.add(
            Notification(
                phone=phone,
                message=rendered,
                channel=NotificationChannelEnum.sms,
                delivery_status="queued",
                error_message=None,
                extra={
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_name,
                },
                attempts_count=0,
                max_attempts=SMS_MAX_RETRIES,
                next_retry_at=send_at,
                last_attempt_at=None,
            )
        )
        scheduled_count += 1

    if scheduled_count > 0:
        log_action(
            db,
            entity="notifications",
            action="schedule_sms_campaign",
            status_code=scheduled_count,
        )
    db.commit()

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "send_at": send_at,
        "scanned_users": len(users),
        "recipients_count": recipients_count,
        "scheduled_count": scheduled_count,
        "skipped_no_phone": skipped_no_phone,
        "skipped_preferences": skipped_preferences,
        "skipped_render_errors": skipped_render_errors,
    }


def list_scheduled_sms_campaigns(
    db: Session,
    *,
    limit: int = 100,
) -> list[dict]:
    now = datetime.now(UTC)
    limit = max(1, min(limit, 500))
    rows = (
        db.query(Notification)
        .filter(
            Notification.channel == NotificationChannelEnum.sms,
            Notification.delivery_status == "queued",
            Notification.next_retry_at.is_not(None),
            Notification.next_retry_at > now,
        )
        .order_by(Notification.created_at.desc())
        .limit(5000)
        .all()
    )

    grouped: dict[str, dict] = {}
    for row in rows:
        campaign_id, campaign_name = _notification_campaign(row)
        if not campaign_id:
            continue
        bucket = grouped.get(campaign_id)
        if not bucket:
            grouped[campaign_id] = {
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "send_at": row.next_retry_at,
                "recipients_count": 1,
                "created_at": row.created_at,
            }
            continue
        bucket["recipients_count"] += 1
        if row.created_at and (bucket["created_at"] is None or row.created_at < bucket["created_at"]):
            bucket["created_at"] = row.created_at
        if row.next_retry_at and (bucket["send_at"] is None or row.next_retry_at < bucket["send_at"]):
            bucket["send_at"] = row.next_retry_at

    items = sorted(
        grouped.values(),
        key=lambda item: item.get("send_at") or datetime.max.replace(tzinfo=UTC),
    )
    return items[:limit]


def cancel_scheduled_sms_campaign(
    db: Session,
    *,
    campaign_id: str,
) -> dict:
    rows = (
        db.query(Notification)
        .filter(
            Notification.channel == NotificationChannelEnum.sms,
            Notification.delivery_status == "queued",
        )
        .all()
    )
    cancelled_count = 0
    for row in rows:
        row_campaign_id, _ = _notification_campaign(row)
        if row_campaign_id != campaign_id:
            continue
        row.delivery_status = "cancelled"
        row.next_retry_at = None
        cancelled_count += 1
    if cancelled_count > 0:
        log_action(
            db,
            entity="notifications",
            action="cancel_sms_campaign",
            status_code=cancelled_count,
        )
    db.commit()
    return {
        "campaign_id": campaign_id,
        "cancelled_count": cancelled_count,
    }


def get_scheduled_sms_campaign(
    db: Session,
    *,
    campaign_id: str,
    limit: int = 100,
) -> dict:
    limit = max(1, min(limit, 500))
    rows = (
        db.query(Notification)
        .filter(
            Notification.channel == NotificationChannelEnum.sms,
        )
        .order_by(Notification.created_at.desc())
        .all()
    )
    rows = [row for row in rows if _notification_campaign(row)[0] == campaign_id]
    if not rows:
        raise ValueError("Campaign not found")

    _, campaign_name = _notification_campaign(rows[0])
    queued = 0
    cancelled = 0
    send_at: datetime | None = None
    for row in rows:
        if row.delivery_status == "queued":
            queued += 1
        if row.delivery_status == "cancelled":
            cancelled += 1
        if row.next_retry_at and (send_at is None or row.next_retry_at < send_at):
            send_at = row.next_retry_at

    items = [
        {
            "notification_id": row.id,
            "phone": row.phone,
            "delivery_status": row.delivery_status,
            "attempts_count": row.attempts_count,
            "next_retry_at": row.next_retry_at,
            "created_at": row.created_at,
        }
        for row in rows[:limit]
    ]
    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "send_at": send_at,
        "total": len(rows),
        "queued": queued,
        "cancelled": cancelled,
        "items": items,
    }


def reschedule_sms_campaign(
    db: Session,
    *,
    campaign_id: str,
    send_at: datetime,
) -> dict:
    if send_at.tzinfo is None:
        send_at = send_at.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if send_at <= now:
        raise ValueError("send_at must be in the future")

    rows = (
        db.query(Notification)
        .filter(
            Notification.channel == NotificationChannelEnum.sms,
            Notification.delivery_status == "queued",
        )
        .all()
    )
    rows = [row for row in rows if _notification_campaign(row)[0] == campaign_id]
    if not rows:
        raise ValueError("No queued notifications found for this campaign")

    for row in rows:
        row.next_retry_at = send_at

    log_action(
        db,
        entity="notifications",
        action="reschedule_sms_campaign",
        status_code=len(rows),
    )
    db.commit()
    return {
        "campaign_id": campaign_id,
        "send_at": send_at,
        "rescheduled_count": len(rows),
    }


def list_sms_campaign_history(
    db: Session,
    *,
    limit: int = 100,
) -> list[dict]:
    limit = max(1, min(limit, 500))
    rows = (
        db.query(Notification)
        .filter(Notification.channel == NotificationChannelEnum.sms)
        .order_by(Notification.created_at.desc())
        .limit(20000)
        .all()
    )

    grouped: dict[str, dict] = {}
    for row in rows:
        campaign_id, campaign_name = _notification_campaign(row)
        if not campaign_id:
            continue
        bucket = grouped.get(campaign_id)
        if not bucket:
            bucket = {
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "total": 0,
                "queued": 0,
                "processing": 0,
                "delivered": 0,
                "failed": 0,
                "dead": 0,
                "cancelled": 0,
                "skipped": 0,
                "created_at": row.created_at,
                "last_activity_at": row.created_at,
            }
            grouped[campaign_id] = bucket

        status = (row.delivery_status or "").strip().lower()
        if status in bucket:
            bucket[status] += 1
        bucket["total"] += 1
        if row.created_at and (bucket["created_at"] is None or row.created_at < bucket["created_at"]):
            bucket["created_at"] = row.created_at
        if row.created_at and (bucket["last_activity_at"] is None or row.created_at > bucket["last_activity_at"]):
            bucket["last_activity_at"] = row.created_at

    items = sorted(
        grouped.values(),
        key=lambda item: item.get("last_activity_at") or datetime(1970, 1, 1, tzinfo=UTC),
        reverse=True,
    )
    return items[:limit]
