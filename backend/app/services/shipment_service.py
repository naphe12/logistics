import uuid
from datetime import UTC, datetime, timedelta
from statistics import median
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func, or_
from app.models.shipments import RelayInventory, Shipment, ShipmentEvent
from app.models.statuses import IncidentStatus, ShipmentStatus
from app.models.relays import RelayPoint
from app.models.incidents import Incident, IncidentUpdate
from app.services.audit_service import log_action
from app.schemas.shipments import ShipmentBulkStatusItem, ShipmentCreate, ShipmentStatusUpdate
from app.services.code_service import create_pickup_code
from app.services.notification_service import queue_and_send_sms
from app.realtime.events import emit_shipment_status_update
from app.enums import UserTypeEnum
from app.models.users import User


class ShipmentNotFoundError(Exception):
    pass


ETA_BASE_HOURS_BY_STATUS: dict[str, int] = {
    "created": 72,
    "ready_for_pickup": 12,
    "picked_up": 48,
    "in_transit": 24,
    "arrived_at_relay": 8,
    "delivered": 0,
}

ETA_MIN_CORRIDOR_SAMPLES = 5
ETA_CORRIDOR_LOOKBACK_LIMIT = 200
ETA_INCIDENT_PENALTY_BASE_HOURS = 8
ETA_INCIDENT_PENALTY_EXTRA_HOURS = 4
ETA_MAX_INCIDENT_PENALTY_HOURS = 24
ETA_STAGNATION_THRESHOLDS_HOURS: dict[str, int] = {
    "created": 12,
    "ready_for_pickup": 6,
    "picked_up": 12,
    "in_transit": 18,
    "arrived_at_relay": 10,
}


def _apply_visibility_scope(query, current_user: User):
    if current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        return query.filter(
            or_(
                Shipment.sender_id == current_user.id,
                Shipment.sender_phone == current_user.phone_e164,
                Shipment.receiver_phone == current_user.phone_e164,
            )
        )
    return query


def generate_shipment_no() -> str:
    return f"PBL-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def create_shipment(
    db: Session,
    payload: ShipmentCreate,
    background_tasks: BackgroundTasks | None = None,
) -> Shipment:
    origin_relay_id = payload.origin_relay_id or payload.origin
    destination_relay_id = payload.destination_relay_id or payload.destination

    shipment = Shipment(
        shipment_no=generate_shipment_no(),
        sender_id=payload.sender_id,
        sender_phone=payload.sender_phone,
        receiver_name=payload.receiver_name,
        receiver_phone=payload.receiver_phone,
        origin_relay_id=origin_relay_id,
        destination_relay_id=destination_relay_id,
        delivery_address_id=payload.delivery_address_id,
        delivery_note=payload.delivery_note,
        origin=origin_relay_id,
        destination=destination_relay_id,
        status="created",
        extra=payload.extra,
    )
    db.add(shipment)
    db.flush()

    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            relay_id=origin_relay_id,
            event_type="shipment_created",
            extra=None,
        )
    )

    _, raw_pickup_code = create_pickup_code(db, shipment.id)

    queue_and_send_sms(
        db,
        payload.sender_phone,
        f"Colis {shipment.shipment_no} cree avec succes.",
        background_tasks=background_tasks,
    )
    queue_and_send_sms(
        db,
        payload.receiver_phone,
        f"Votre colis {shipment.shipment_no} est enregistre. Code retrait: {raw_pickup_code}.",
        background_tasks=background_tasks,
    )

    db.refresh(shipment)
    emit_shipment_status_update(
        shipment_id=shipment.id,
        status=shipment.status or "created",
        event_type="shipment_created",
        relay_id=origin_relay_id,
    )
    return shipment


def update_shipment_status(db: Session, shipment_id, payload: ShipmentStatusUpdate) -> Shipment:
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise ShipmentNotFoundError("Shipment not found")

    shipment.status = payload.status
    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            relay_id=payload.relay_id,
            event_type=payload.event_type,
            extra=payload.extra,
        )
    )
    db.commit()
    db.refresh(shipment)
    emit_shipment_status_update(
        shipment_id=shipment.id,
        status=shipment.status or payload.status,
        event_type=payload.event_type,
        relay_id=payload.relay_id,
    )
    return shipment


def create_shipment_event(
    db: Session,
    shipment_id,
    *,
    event_type: str,
    relay_id=None,
    status: str | None = None,
    extra: dict | None = None,
) -> ShipmentEvent:
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise ShipmentNotFoundError("Shipment not found")

    event = ShipmentEvent(
        shipment_id=shipment.id,
        relay_id=relay_id,
        event_type=event_type,
        extra=extra,
    )
    db.add(event)

    if status is not None:
        shipment.status = status

    db.commit()
    db.refresh(event)
    if status is not None:
        emit_shipment_status_update(
            shipment_id=shipment.id,
            status=status,
            event_type=event_type,
            relay_id=relay_id,
        )
    return event


def list_shipments(
    db: Session,
    current_user: User,
    *,
    status: str | None = None,
    sender_phone: str | None = None,
    receiver_phone: str | None = None,
    shipment_no: str | None = None,
    q: str | None = None,
    extra_key: str | None = None,
    extra_value: str | None = None,
    sort: str = "created_at_desc",
    offset: int = 0,
    limit: int = 50,
) -> list[Shipment]:
    query = db.query(Shipment)
    query = _apply_visibility_scope(query, current_user)

    if status:
        query = query.filter(Shipment.status == status)
    if sender_phone:
        query = query.filter(Shipment.sender_phone == sender_phone)
    if receiver_phone:
        query = query.filter(Shipment.receiver_phone == receiver_phone)
    if shipment_no:
        query = query.filter(Shipment.shipment_no == shipment_no)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Shipment.shipment_no.ilike(like),
                Shipment.sender_phone.ilike(like),
                Shipment.receiver_phone.ilike(like),
                Shipment.receiver_name.ilike(like),
            )
        )
    if extra_key and extra_value is not None:
        query = query.filter(Shipment.extra[extra_key].astext == extra_value)

    if sort == "created_at_asc":
        query = query.order_by(asc(Shipment.created_at))
    else:
        query = query.order_by(desc(Shipment.created_at))

    return query.offset(offset).limit(limit).all()


def get_shipment(db: Session, shipment_id, current_user: User) -> Shipment | None:
    query = db.query(Shipment).filter(Shipment.id == shipment_id)
    query = _apply_visibility_scope(query, current_user)
    return query.first()


def list_shipment_events(db: Session, shipment_id, current_user: User) -> list[ShipmentEvent]:
    shipment = get_shipment(db, shipment_id, current_user)
    if not shipment:
        raise ShipmentNotFoundError("Shipment not found")

    return (
        db.query(ShipmentEvent)
        .filter(ShipmentEvent.shipment_id == shipment_id)
        .order_by(ShipmentEvent.created_at.desc())
        .all()
    )


def get_shipment_overview_stats(db: Session, current_user: User) -> dict[str, int | dict[str, int]]:
    scoped_query = _apply_visibility_scope(db.query(Shipment), current_user)
    now = datetime.now(UTC)
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    total = scoped_query.count()
    created_last_24h = scoped_query.filter(Shipment.created_at >= since_24h).count()
    created_last_7d = scoped_query.filter(Shipment.created_at >= since_7d).count()

    status_rows = (
        scoped_query.with_entities(
            func.coalesce(Shipment.status, "unknown"),
            func.count(Shipment.id),
        )
        .group_by(Shipment.status)
        .all()
    )

    by_status = {status: count for status, count in status_rows}
    return {
        "total": total,
        "created_last_24h": created_last_24h,
        "created_last_7d": created_last_7d,
        "by_status": by_status,
    }


def get_shipment_timeseries_stats(
    db: Session,
    current_user: User,
    *,
    days: int = 30,
    status: str | None = None,
) -> dict[str, int | list[dict[str, int | str]]]:
    days = max(1, min(days, 365))
    now = datetime.now(UTC)
    since = now - timedelta(days=days - 1)

    scoped_query = _apply_visibility_scope(db.query(Shipment), current_user).filter(Shipment.created_at >= since)
    if status:
        scoped_query = scoped_query.filter(Shipment.status == status)

    rows = (
        scoped_query.with_entities(
            func.date(Shipment.created_at).label("day"),
            func.count(Shipment.id).label("created_count"),
        )
        .group_by(func.date(Shipment.created_at))
        .order_by(func.date(Shipment.created_at))
        .all()
    )

    by_day = {row.day: int(row.created_count) for row in rows}
    start_day = since.date()
    points = []
    total_created = 0
    for i in range(days):
        day = start_day + timedelta(days=i)
        created_count = by_day.get(day, 0)
        total_created += created_count
        points.append({"day": day, "created_count": created_count})

    return {
        "days": days,
        "total_created": total_created,
        "points": points,
    }


def list_my_shipments(
    db: Session,
    current_user: User,
    *,
    direction: str = "all",
    status: str | None = None,
    q: str | None = None,
    extra_key: str | None = None,
    extra_value: str | None = None,
    sort: str = "created_at_desc",
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Shipment], int]:
    query = db.query(Shipment)

    if current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        sent_filter = or_(
            Shipment.sender_id == current_user.id,
            Shipment.sender_phone == current_user.phone_e164,
        )
        received_filter = Shipment.receiver_phone == current_user.phone_e164

        if direction == "sent":
            query = query.filter(sent_filter)
        elif direction == "received":
            query = query.filter(received_filter)
        else:
            query = query.filter(or_(sent_filter, received_filter))
    else:
        query = _apply_visibility_scope(query, current_user)

    if status:
        query = query.filter(Shipment.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Shipment.shipment_no.ilike(like),
                Shipment.sender_phone.ilike(like),
                Shipment.receiver_phone.ilike(like),
                Shipment.receiver_name.ilike(like),
            )
        )
    if extra_key and extra_value is not None:
        query = query.filter(Shipment.extra[extra_key].astext == extra_value)

    if sort == "created_at_asc":
        query = query.order_by(asc(Shipment.created_at))
    else:
        query = query.order_by(desc(Shipment.created_at))

    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def list_shipments_delta(
    db: Session,
    current_user: User,
    *,
    since: datetime | None = None,
    limit: int = 200,
) -> list[Shipment]:
    limit = max(1, min(limit, 1000))
    query = _apply_visibility_scope(db.query(Shipment), current_user)
    if since is not None:
        query = query.filter(Shipment.updated_at > since)
    return query.order_by(Shipment.updated_at.asc(), Shipment.id.asc()).limit(limit).all()


def list_shipment_statuses(db: Session) -> list[ShipmentStatus]:
    return db.query(ShipmentStatus).order_by(ShipmentStatus.code.asc()).all()


def shipment_status_exists(db: Session, status_code: str) -> bool:
    return (
        db.query(ShipmentStatus.code)
        .filter(ShipmentStatus.code == status_code)
        .first()
        is not None
    )


def bulk_update_shipment_status(
    db: Session,
    items: list[ShipmentBulkStatusItem],
    *,
    continue_on_error: bool = True,
    dry_run: bool = False,
) -> dict[str, int | list[dict[str, object]]]:
    shipment_ids = [item.shipment_id for item in items]
    existing_shipments = (
        db.query(Shipment)
        .filter(Shipment.id.in_(shipment_ids))
        .all()
    )
    shipment_by_id = {shipment.id: shipment for shipment in existing_shipments}

    results: list[dict[str, object]] = []
    succeeded = 0
    updated_shipments: list[tuple[Shipment, ShipmentBulkStatusItem]] = []

    for index, item in enumerate(items):
        shipment = shipment_by_id.get(item.shipment_id)
        if not shipment:
            results.append(
                {
                    "shipment_id": item.shipment_id,
                    "success": False,
                    "error": "Shipment not found",
                }
            )
            if not continue_on_error:
                for pending in items[index + 1 :]:
                    results.append(
                        {
                            "shipment_id": pending.shipment_id,
                            "success": False,
                            "error": "Skipped due to previous error",
                        }
                    )
                break
            continue

        if not dry_run:
            shipment.status = item.status
            db.add(
                ShipmentEvent(
                    shipment_id=shipment.id,
                    relay_id=item.relay_id,
                    event_type=item.event_type,
                    extra=item.extra,
                )
            )
            updated_shipments.append((shipment, item))
        results.append({"shipment_id": item.shipment_id, "success": True, "error": None})
        succeeded += 1

    if not dry_run:
        db.commit()
        for shipment, item in updated_shipments:
            emit_shipment_status_update(
                shipment_id=shipment.id,
                status=shipment.status or item.status,
                event_type=item.event_type,
                relay_id=item.relay_id,
            )
    failed = len(items) - succeeded
    return {
        "total": len(items),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


def _get_eta_floor_for_status(status: str) -> int:
    floor_by_status = {
        "created": 8,
        "ready_for_pickup": 2,
        "picked_up": 6,
        "in_transit": 3,
        "arrived_at_relay": 1,
    }
    return floor_by_status.get(status, 4)


def _build_baseline_eta(db: Session, shipment: Shipment, now: datetime) -> dict:
    status = shipment.status or "created"
    base_hours = ETA_BASE_HOURS_BY_STATUS.get(status, 48)
    last_event_at = (
        db.query(func.max(ShipmentEvent.created_at))
        .filter(ShipmentEvent.shipment_id == shipment.id)
        .scalar()
    )
    reference_at = last_event_at or shipment.created_at or now
    elapsed_hours = max(0.0, (now - reference_at).total_seconds() / 3600.0)
    remaining = max(_get_eta_floor_for_status(status), int(round(base_hours - elapsed_hours)))
    estimated_at = now + timedelta(hours=remaining)

    if status in {"in_transit", "arrived_at_relay"}:
        confidence = "medium"
    elif status in {"ready_for_pickup"}:
        confidence = "high"
    else:
        confidence = "low"

    return {
        "shipment_id": shipment.id,
        "shipment_no": shipment.shipment_no,
        "status": status,
        "estimated_delivery_at": estimated_at,
        "remaining_hours": remaining,
        "confidence": confidence,
        "basis": "status_baseline_v1",
        "historical_samples": None,
        "historical_median_hours": None,
    }


def _get_corridor_median_hours(db: Session, shipment: Shipment) -> tuple[int | None, int]:
    if not shipment.origin or not shipment.destination:
        return None, 0

    rows = (
        db.query(
            Shipment.created_at.label("created_at"),
            func.max(ShipmentEvent.created_at).label("delivered_at"),
        )
        .outerjoin(ShipmentEvent, ShipmentEvent.shipment_id == Shipment.id)
        .filter(Shipment.status == "delivered")
        .filter(Shipment.origin == shipment.origin)
        .filter(Shipment.destination == shipment.destination)
        .filter(Shipment.id != shipment.id)
        .group_by(Shipment.id)
        .order_by(desc(Shipment.created_at))
        .limit(ETA_CORRIDOR_LOOKBACK_LIMIT)
        .all()
    )

    durations_hours: list[float] = []
    for row in rows:
        created_at = getattr(row, "created_at", None)
        delivered_at = getattr(row, "delivered_at", None)
        if not created_at or not delivered_at:
            continue
        hours = (delivered_at - created_at).total_seconds() / 3600.0
        if hours > 0:
            durations_hours.append(hours)

    if not durations_hours:
        return None, 0

    return int(round(median(durations_hours))), len(durations_hours)


def _get_destination_utilization_ratio(db: Session, shipment: Shipment) -> float | None:
    if not shipment.destination:
        return None

    relay = db.query(RelayPoint).filter(RelayPoint.id == shipment.destination).first()
    if not relay or relay.storage_capacity is None or relay.storage_capacity <= 0:
        return None

    present_count = (
        db.query(RelayInventory)
        .filter(
            RelayInventory.relay_id == shipment.destination,
            RelayInventory.present.is_(True),
        )
        .count()
    )
    return present_count / relay.storage_capacity


def _compute_eta_penalties(
    db: Session,
    shipment: Shipment,
    *,
    status: str,
    now: datetime,
) -> tuple[int, list[dict[str, int | str]]]:
    factors: list[dict[str, int | str]] = []

    open_incidents_count = (
        db.query(Incident)
        .filter(
            Incident.shipment_id == shipment.id,
            Incident.status.in_(["open", "investigating"]),
        )
        .count()
    )
    if open_incidents_count > 0:
        incident_penalty = min(
            ETA_MAX_INCIDENT_PENALTY_HOURS,
            ETA_INCIDENT_PENALTY_BASE_HOURS
            + (open_incidents_count - 1) * ETA_INCIDENT_PENALTY_EXTRA_HOURS,
        )
        factors.append(
            {
                "code": "incident_risk",
                "label": "Incident actif",
                "hours": incident_penalty,
            }
        )

    utilization_ratio = _get_destination_utilization_ratio(db, shipment)
    if utilization_ratio is not None:
        if utilization_ratio >= 1.0:
            factors.append(
                {
                    "code": "relay_full",
                    "label": "Relais destination plein",
                    "hours": 12,
                }
            )
        elif utilization_ratio >= 0.9:
            factors.append(
                {
                    "code": "relay_near_capacity",
                    "label": "Relais destination proche saturation",
                    "hours": 6,
                }
            )

    threshold_hours = ETA_STAGNATION_THRESHOLDS_HOURS.get(status)
    if threshold_hours:
        last_event_at = (
            db.query(func.max(ShipmentEvent.created_at))
            .filter(ShipmentEvent.shipment_id == shipment.id)
            .scalar()
        )
        reference_at = last_event_at or shipment.created_at or now
        stuck_hours = max(0.0, (now - reference_at).total_seconds() / 3600.0)
        if stuck_hours > threshold_hours:
            excess = stuck_hours - threshold_hours
            blocks = max(1, int(excess // 6))
            stagnation_penalty = min(18, blocks * 3)
            factors.append(
                {
                    "code": "operational_delay",
                    "label": "Blocage operationnel",
                    "hours": stagnation_penalty,
                }
            )

    total_penalty = int(sum(int(factor["hours"]) for factor in factors))
    return total_penalty, factors


def get_shipment_eta(db: Session, shipment_id, current_user: User) -> dict:
    shipment = get_shipment(db, shipment_id, current_user)
    if not shipment:
        raise ShipmentNotFoundError("Shipment not found")

    now = datetime.now(UTC)
    status = shipment.status or "created"
    if status == "delivered":
        return {
            "shipment_id": shipment.id,
            "shipment_no": shipment.shipment_no,
            "status": status,
            "estimated_delivery_at": now,
            "remaining_hours": 0,
            "base_remaining_hours": 0,
            "penalty_hours": 0,
            "confidence": "high",
            "basis": "already_delivered",
            "factors": [],
            "historical_samples": None,
            "historical_median_hours": None,
        }

    median_hours, sample_count = _get_corridor_median_hours(db, shipment)
    if median_hours is None or sample_count < ETA_MIN_CORRIDOR_SAMPLES:
        eta = _build_baseline_eta(db, shipment, now)
    else:
        start_at = shipment.created_at or now
        elapsed_hours = max(0.0, (now - start_at).total_seconds() / 3600.0)
        floor = _get_eta_floor_for_status(status)
        remaining = max(floor, int(round(median_hours - elapsed_hours)))
        estimated_at = now + timedelta(hours=remaining)

        confidence = "high" if sample_count >= 20 else "medium"
        eta = {
            "shipment_id": shipment.id,
            "shipment_no": shipment.shipment_no,
            "status": status,
            "estimated_delivery_at": estimated_at,
            "remaining_hours": remaining,
            "base_remaining_hours": remaining,
            "penalty_hours": 0,
            "confidence": confidence,
            "basis": "corridor_history_v2",
            "factors": [],
            "historical_samples": sample_count,
            "historical_median_hours": median_hours,
        }

    penalty_hours, factors = _compute_eta_penalties(db, shipment, status=status, now=now)
    base_remaining = int(eta["remaining_hours"])
    final_remaining = base_remaining + penalty_hours
    eta["base_remaining_hours"] = base_remaining
    eta["penalty_hours"] = penalty_hours
    eta["remaining_hours"] = final_remaining
    eta["estimated_delivery_at"] = now + timedelta(hours=final_remaining)
    eta["factors"] = factors
    eta["basis"] = f"{eta['basis']}+dynamic_risk_v3"
    return eta


def update_shipment_extra(
    db: Session,
    shipment_id,
    *,
    extra: dict,
    merge: bool = True,
) -> Shipment:
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise ShipmentNotFoundError("Shipment not found")

    if merge and isinstance(shipment.extra, dict):
        shipment.extra = {**shipment.extra, **extra}
    else:
        shipment.extra = extra

    db.commit()
    db.refresh(shipment)
    return shipment


def get_shipment_tracking_summary(db: Session, shipment_id, current_user: User) -> dict:
    shipment = get_shipment(db, shipment_id, current_user)
    if not shipment:
        raise ShipmentNotFoundError("Shipment not found")

    now = datetime.now(UTC)
    created_at = shipment.created_at or now
    last_event_at = (
        db.query(func.max(ShipmentEvent.created_at))
        .filter(ShipmentEvent.shipment_id == shipment.id)
        .scalar()
    ) or created_at
    elapsed_hours = max(0, int((now - created_at).total_seconds() // 3600))

    median_hours, sample_count = _get_corridor_median_hours(db, shipment)
    if median_hours is not None and sample_count >= ETA_MIN_CORRIDOR_SAMPLES:
        target_sla_hours = max(1, median_hours)
    else:
        status = shipment.status or "created"
        target_sla_hours = ETA_BASE_HOURS_BY_STATUS.get(status, 48)

    remaining_sla_hours = target_sla_hours - elapsed_hours
    open_incidents = (
        db.query(Incident.id)
        .filter(
            Incident.shipment_id == shipment.id,
            Incident.status.in_(["open", "investigating"]),
        )
        .count()
    )
    stagnation_hours = max(0, int((now - last_event_at).total_seconds() // 3600))
    threshold_hours = ETA_STAGNATION_THRESHOLDS_HOURS.get(shipment.status or "created", 12)

    risk_reasons: list[str] = []
    if remaining_sla_hours <= 0:
        sla_state = "late"
        risk_reasons.append("sla_deadline_missed")
    elif remaining_sla_hours <= 6:
        sla_state = "at_risk"
        risk_reasons.append("sla_near_deadline")
    else:
        sla_state = "on_track"
    if stagnation_hours > threshold_hours:
        risk_reasons.append("stagnation_detected")
        if sla_state == "on_track":
            sla_state = "at_risk"
    if open_incidents > 0:
        risk_reasons.append("open_incidents")
        if sla_state == "on_track":
            sla_state = "at_risk"

    eta = get_shipment_eta(db, shipment_id, current_user)
    return {
        "shipment_id": shipment.id,
        "shipment_no": shipment.shipment_no,
        "status": shipment.status,
        "created_at": shipment.created_at,
        "last_event_at": last_event_at,
        "elapsed_hours": elapsed_hours,
        "target_sla_hours": target_sla_hours,
        "remaining_sla_hours": remaining_sla_hours,
        "sla_state": sla_state,
        "open_incidents": open_incidents,
        "stagnation_hours": stagnation_hours,
        "risk_reasons": risk_reasons,
        "estimated_delivery_at": eta["estimated_delivery_at"],
        "eta_basis": eta["basis"],
    }


def list_sla_risk_shipments(
    db: Session,
    current_user: User,
    *,
    state: str | None = None,
    limit: int = 100,
) -> dict:
    limit = max(1, min(limit, 500))
    candidates = (
        _apply_visibility_scope(db.query(Shipment), current_user)
        .filter(Shipment.status.notin_(["delivered", "cancelled"]))
        .order_by(desc(Shipment.created_at))
        .limit(limit)
        .all()
    )
    items: list[dict] = []
    for shipment in candidates:
        summary = get_shipment_tracking_summary(db, shipment.id, current_user)
        if state and summary["sla_state"] != state:
            continue
        items.append(summary)
    return {
        "items": items,
        "total": len(items),
        "limit": limit,
    }


def get_shipment_timeline(db: Session, shipment_id, current_user: User) -> list[dict]:
    shipment = get_shipment(db, shipment_id, current_user)
    if not shipment:
        raise ShipmentNotFoundError("Shipment not found")

    items: list[dict] = []
    events = (
        db.query(ShipmentEvent)
        .filter(ShipmentEvent.shipment_id == shipment_id)
        .order_by(ShipmentEvent.created_at.desc())
        .all()
    )
    incidents = (
        db.query(Incident)
        .filter(Incident.shipment_id == shipment_id)
        .order_by(Incident.created_at.desc())
        .all()
    )
    incident_ids = [row.id for row in incidents]
    incident_updates = []
    if incident_ids:
        incident_updates = (
            db.query(IncidentUpdate)
            .filter(IncidentUpdate.incident_id.in_(incident_ids))
            .order_by(IncidentUpdate.created_at.desc())
            .all()
        )

    for event in events:
        items.append(
            {
                "occurred_at": event.created_at,
                "kind": "shipment_event",
                "code": event.event_type or "shipment_event",
                "status": None,
                "message": None,
                "relay_id": event.relay_id,
                "incident_id": None,
                "extra": event.extra,
            }
        )
    for incident in incidents:
        items.append(
            {
                "occurred_at": incident.created_at,
                "kind": "incident",
                "code": incident.incident_type or "incident",
                "status": incident.status,
                "message": incident.description,
                "relay_id": None,
                "incident_id": incident.id,
                "extra": incident.extra,
            }
        )
    for update in incident_updates:
        items.append(
            {
                "occurred_at": update.created_at,
                "kind": "incident_update",
                "code": "incident_update",
                "status": None,
                "message": update.message,
                "relay_id": None,
                "incident_id": update.incident_id,
                "extra": None,
            }
        )

    items.sort(key=lambda row: row["occurred_at"], reverse=True)
    return items


def auto_detect_stagnation_incidents(db: Session, *, limit: int = 200) -> dict:
    open_status_exists = db.query(IncidentStatus.code).filter(IncidentStatus.code == "open").first()
    if not open_status_exists:
        raise ValueError("Incident status 'open' is not configured")

    limit = max(1, min(limit, 500))
    candidates = (
        db.query(Shipment)
        .filter(Shipment.status.in_(list(ETA_STAGNATION_THRESHOLDS_HOURS.keys())))
        .order_by(Shipment.created_at.asc())
        .limit(limit)
        .all()
    )

    created = 0
    skipped_existing = 0
    now = datetime.now(UTC)
    for shipment in candidates:
        threshold_hours = ETA_STAGNATION_THRESHOLDS_HOURS.get(shipment.status or "created", 12)
        last_event_at = (
            db.query(func.max(ShipmentEvent.created_at))
            .filter(ShipmentEvent.shipment_id == shipment.id)
            .scalar()
        ) or shipment.created_at or now
        stagnation_hours = max(0, int((now - last_event_at).total_seconds() // 3600))
        if stagnation_hours <= threshold_hours:
            continue

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
                description=(
                    "Auto-detected operational stagnation: "
                    f"{stagnation_hours}h in status '{shipment.status}' (threshold {threshold_hours}h)."
                ),
                status="open",
                extra={
                    "auto_detect": "stagnation",
                    "stagnation_hours": stagnation_hours,
                    "threshold_hours": threshold_hours,
                    "status": shipment.status,
                },
            )
        )
        created += 1

    if created > 0:
        log_action(db, entity="incidents", action="auto_detect_stagnation")
    db.commit()
    return {
        "examined": len(candidates),
        "created": created,
        "skipped_existing": skipped_existing,
    }


def get_my_shipments_dashboard(db: Session, current_user: User) -> dict:
    now = datetime.now(UTC)
    since_30d = now - timedelta(days=30)

    sent_filter = or_(
        Shipment.sender_id == current_user.id,
        Shipment.sender_phone == current_user.phone_e164,
    )
    received_filter = Shipment.receiver_phone == current_user.phone_e164

    base_query = db.query(Shipment)
    if current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        base_query = base_query.filter(or_(sent_filter, received_filter))
    else:
        base_query = _apply_visibility_scope(base_query, current_user)

    total = base_query.count()
    sent = base_query.filter(sent_filter).count()
    received = base_query.filter(received_filter).count()
    delivered = base_query.filter(Shipment.status == "delivered").count()
    in_progress = base_query.filter(
        Shipment.status.in_(["created", "ready_for_pickup", "picked_up", "in_transit", "arrived_at_relay"])
    ).count()
    delayed_risk = base_query.filter(
        Shipment.created_at <= now - timedelta(hours=48),
        Shipment.status.in_(["picked_up", "in_transit", "arrived_at_relay", "ready_for_pickup"]),
    ).count()
    last_30d_created = base_query.filter(Shipment.created_at >= since_30d).count()

    return {
        "total": total,
        "sent": sent,
        "received": received,
        "in_progress": in_progress,
        "delivered": delivered,
        "delayed_risk": delayed_risk,
        "last_30d_created": last_30d_created,
    }
