import uuid
from datetime import UTC, datetime, timedelta
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func, or_
from app.models.shipments import Shipment, ShipmentEvent
from app.models.statuses import ShipmentStatus
from app.schemas.shipments import ShipmentBulkStatusItem, ShipmentCreate, ShipmentStatusUpdate
from app.services.code_service import create_pickup_code
from app.services.notification_service import queue_and_send_sms
from app.enums import UserTypeEnum
from app.models.users import User


class ShipmentNotFoundError(Exception):
    pass


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
    shipment = Shipment(
        shipment_no=generate_shipment_no(),
        sender_id=payload.sender_id,
        sender_phone=payload.sender_phone,
        receiver_name=payload.receiver_name,
        receiver_phone=payload.receiver_phone,
        origin=payload.origin,
        destination=payload.destination,
        status="created",
    )
    db.add(shipment)
    db.flush()

    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            relay_id=payload.origin,
            event_type="shipment_created",
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
        )
    )
    db.commit()
    db.refresh(shipment)
    return shipment


def create_shipment_event(
    db: Session,
    shipment_id,
    *,
    event_type: str,
    relay_id=None,
    status: str | None = None,
) -> ShipmentEvent:
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise ShipmentNotFoundError("Shipment not found")

    event = ShipmentEvent(
        shipment_id=shipment.id,
        relay_id=relay_id,
        event_type=event_type,
    )
    db.add(event)

    if status is not None:
        shipment.status = status

    db.commit()
    db.refresh(event)
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

    if sort == "created_at_asc":
        query = query.order_by(asc(Shipment.created_at))
    else:
        query = query.order_by(desc(Shipment.created_at))

    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


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

        shipment.status = item.status
        db.add(
            ShipmentEvent(
                shipment_id=shipment.id,
                relay_id=item.relay_id,
                event_type=item.event_type,
            )
        )
        results.append({"shipment_id": item.shipment_id, "success": True, "error": None})
        succeeded += 1

    db.commit()
    failed = len(items) - succeeded
    return {
        "total": len(items),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
