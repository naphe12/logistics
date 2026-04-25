from calendar import monthrange
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import asc, desc, or_
from sqlalchemy.orm import Session

from app.enums import UserTypeEnum
from app.models.shipments import ShipmentSchedule
from app.models.users import User
from app.schemas.shipments import ShipmentCreate, ShipmentScheduleCreate, ShipmentScheduleUpdate
from app.services.audit_service import log_action
from app.services.shipment_service import create_shipment

SCHEDULE_FREQUENCIES = {"once", "daily", "weekly", "monthly"}


class ShipmentScheduleError(Exception):
    pass


class ShipmentScheduleNotFoundError(ShipmentScheduleError):
    pass


def _is_restricted_actor(current_user: User | None) -> bool:
    if not current_user:
        return False
    return current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}


def _apply_schedule_sender_scope(query, current_user: User | None):
    if not current_user:
        return query
    return query.filter(
        or_(
            ShipmentSchedule.sender_id == current_user.id,
            ShipmentSchedule.sender_phone == current_user.phone_e164,
        )
    )


def _apply_schedule_visibility_scope(query, current_user: User | None):
    if not _is_restricted_actor(current_user):
        return query
    return _apply_schedule_sender_scope(query, current_user)


def _sanitize_create_payload_for_actor(
    payload: ShipmentScheduleCreate,
    current_user: User | None,
) -> ShipmentScheduleCreate:
    if not _is_restricted_actor(current_user):
        return payload

    sender_phone = (payload.sender_phone or "").strip()
    if sender_phone and sender_phone != current_user.phone_e164:
        raise ShipmentScheduleError("sender_phone must match authenticated user")
    if payload.sender_id is not None and payload.sender_id != current_user.id:
        raise ShipmentScheduleError("sender_id must match authenticated user")

    return payload.model_copy(
        update={
            "sender_id": current_user.id,
            "sender_phone": current_user.phone_e164,
        }
    )


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _add_months(base: datetime, months: int, day_of_month: int | None = None) -> datetime:
    month_index = (base.month - 1) + months
    year = base.year + (month_index // 12)
    month = (month_index % 12) + 1
    max_day = monthrange(year, month)[1]
    desired_day = day_of_month if day_of_month is not None else base.day
    day = max(1, min(desired_day, max_day))
    return base.replace(year=year, month=month, day=day)


def _compute_next_run(
    *,
    frequency: str,
    interval_count: int,
    anchor: datetime,
    day_of_week: int | None,
    day_of_month: int | None,
) -> datetime | None:
    normalized = (frequency or "").strip().lower()
    interval = max(1, int(interval_count or 1))
    if normalized == "once":
        return None
    if normalized == "daily":
        return anchor + timedelta(days=interval)
    if normalized == "weekly":
        next_dt = anchor + timedelta(days=7 * interval)
        if day_of_week is None:
            return next_dt
        delta = (int(day_of_week) - next_dt.weekday()) % 7
        return next_dt + timedelta(days=delta)
    if normalized == "monthly":
        return _add_months(anchor, interval, day_of_month=day_of_month)
    raise ShipmentScheduleError(f"Unsupported frequency: {frequency}")


def _validate_schedule_rules(
    *,
    frequency: str,
    day_of_week: int | None,
    day_of_month: int | None,
    start_at: datetime,
    end_at: datetime | None,
) -> None:
    normalized = (frequency or "").strip().lower()
    if normalized not in SCHEDULE_FREQUENCIES:
        raise ShipmentScheduleError(
            "frequency must be one of: once, daily, weekly, monthly"
        )
    if normalized == "weekly" and day_of_week is None:
        raise ShipmentScheduleError("day_of_week is required for weekly frequency")
    if normalized == "monthly" and day_of_month is None:
        raise ShipmentScheduleError("day_of_month is required for monthly frequency")
    if normalized in {"once", "daily"} and day_of_week is not None:
        raise ShipmentScheduleError("day_of_week is only allowed for weekly frequency")
    if normalized in {"once", "daily", "weekly"} and day_of_month is not None:
        raise ShipmentScheduleError("day_of_month is only allowed for monthly frequency")
    if end_at is not None and _to_utc(end_at) < _to_utc(start_at):
        raise ShipmentScheduleError("end_at must be >= start_at")


def list_shipment_schedules(
    db: Session,
    *,
    active_only: bool = False,
    current_user: User | None = None,
    owned_only: bool = False,
    offset: int = 0,
    limit: int = 100,
    sort: str = "next_run_asc",
) -> tuple[list[ShipmentSchedule], int]:
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 100), 500))
    query = _apply_schedule_visibility_scope(db.query(ShipmentSchedule), current_user)
    if owned_only:
        query = _apply_schedule_sender_scope(query, current_user)
    if active_only:
        query = query.filter(ShipmentSchedule.is_active.is_(True))
    total = query.count()
    if sort == "next_run_desc":
        query = query.order_by(
            ShipmentSchedule.next_run_at.is_(None),
            desc(ShipmentSchedule.next_run_at),
            desc(ShipmentSchedule.created_at),
        )
    elif sort == "created_desc":
        query = query.order_by(desc(ShipmentSchedule.created_at))
    elif sort == "created_asc":
        query = query.order_by(asc(ShipmentSchedule.created_at))
    else:
        query = query.order_by(
            ShipmentSchedule.next_run_at.is_(None),
            asc(ShipmentSchedule.next_run_at),
            desc(ShipmentSchedule.created_at),
        )
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_shipment_schedule(
    db: Session,
    schedule_id: UUID,
    *,
    current_user: User | None = None,
) -> ShipmentSchedule | None:
    return (
        _apply_schedule_visibility_scope(db.query(ShipmentSchedule), current_user)
        .filter(ShipmentSchedule.id == schedule_id)
        .first()
    )


def create_shipment_schedule(
    db: Session,
    payload: ShipmentScheduleCreate,
    *,
    current_user: User | None = None,
) -> ShipmentSchedule:
    payload = _sanitize_create_payload_for_actor(payload, current_user)
    start_at = _to_utc(payload.start_at)
    end_at = _to_utc(payload.end_at) if payload.end_at else None
    frequency = (payload.frequency or "once").strip().lower()
    _validate_schedule_rules(
        frequency=frequency,
        day_of_week=payload.day_of_week,
        day_of_month=payload.day_of_month,
        start_at=start_at,
        end_at=end_at,
    )

    schedule = ShipmentSchedule(
        sender_id=payload.sender_id,
        sender_phone=payload.sender_phone,
        receiver_name=payload.receiver_name,
        receiver_phone=payload.receiver_phone,
        origin_relay_id=payload.origin_relay_id,
        destination_relay_id=payload.destination_relay_id,
        delivery_address_id=payload.delivery_address_id,
        delivery_note=payload.delivery_note,
        declared_value=payload.declared_value,
        insurance_opt_in=payload.insurance_opt_in,
        frequency=frequency,
        interval_count=payload.interval_count,
        day_of_week=payload.day_of_week,
        day_of_month=payload.day_of_month,
        start_at=start_at,
        next_run_at=start_at,
        end_at=end_at,
        remaining_runs=payload.remaining_runs,
        is_active=payload.is_active,
        extra=payload.extra,
    )
    db.add(schedule)
    log_action(db, entity="shipment_schedules", action="create")
    db.commit()
    db.refresh(schedule)
    return schedule


def update_shipment_schedule(
    db: Session,
    schedule_id: UUID,
    payload: ShipmentScheduleUpdate,
    *,
    current_user: User | None = None,
) -> ShipmentSchedule:
    schedule = get_shipment_schedule(db, schedule_id, current_user=current_user)
    if not schedule:
        raise ShipmentScheduleNotFoundError("Shipment schedule not found")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if field == "recompute_next_run":
            continue
        if field in {"start_at", "end_at"} and value is not None:
            setattr(schedule, field, _to_utc(value))
        else:
            setattr(schedule, field, value)

    frequency = (schedule.frequency or "").strip().lower()
    _validate_schedule_rules(
        frequency=frequency,
        day_of_week=schedule.day_of_week,
        day_of_month=schedule.day_of_month,
        start_at=schedule.start_at,
        end_at=schedule.end_at,
    )
    if payload.recompute_next_run:
        schedule.next_run_at = schedule.start_at

    log_action(db, entity="shipment_schedules", action="update")
    db.commit()
    db.refresh(schedule)
    return schedule


def run_due_shipment_schedules(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> dict:
    now_utc = _to_utc(now) if now else datetime.now(UTC)
    limit = max(1, min(limit, 500))

    due_rows = (
        db.query(ShipmentSchedule)
        .filter(
            ShipmentSchedule.is_active.is_(True),
            ShipmentSchedule.next_run_at.is_not(None),
            ShipmentSchedule.next_run_at <= now_utc,
        )
        .order_by(ShipmentSchedule.next_run_at.asc())
        .limit(limit)
        .all()
    )

    triggered = 0
    failed = 0
    items: list[dict] = []

    for row in due_rows:
        if row.end_at is not None and row.next_run_at and row.next_run_at > row.end_at:
            row.is_active = False
            row.next_run_at = None
            continue
        if row.remaining_runs is not None and row.remaining_runs <= 0:
            row.is_active = False
            row.next_run_at = None
            continue

        try:
            shipment = create_shipment(
                db,
                ShipmentCreate(
                    sender_id=row.sender_id,
                    sender_phone=row.sender_phone or "",
                    receiver_name=row.receiver_name or "",
                    receiver_phone=row.receiver_phone or "",
                    origin_relay_id=row.origin_relay_id,
                    destination_relay_id=row.destination_relay_id,
                    delivery_address_id=row.delivery_address_id,
                    delivery_note=row.delivery_note,
                    declared_value=row.declared_value,
                    insurance_opt_in=bool(row.insurance_opt_in),
                    extra={
                        **(row.extra or {}),
                        "schedule_id": str(row.id),
                        "schedule_frequency": row.frequency,
                        "scheduled_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
                    },
                ),
                background_tasks=None,
            )

            run_anchor = _to_utc(row.next_run_at or now_utc)
            row.last_run_at = now_utc
            row.last_error = None
            if row.remaining_runs is not None:
                row.remaining_runs = max(0, int(row.remaining_runs) - 1)

            next_run = _compute_next_run(
                frequency=row.frequency or "once",
                interval_count=int(row.interval_count or 1),
                anchor=run_anchor,
                day_of_week=row.day_of_week,
                day_of_month=row.day_of_month,
            )
            if row.remaining_runs is not None and row.remaining_runs <= 0:
                next_run = None
            if next_run is not None and row.end_at is not None and next_run > _to_utc(row.end_at):
                next_run = None

            row.next_run_at = next_run
            if next_run is None:
                row.is_active = False

            triggered += 1
            items.append(
                {
                    "schedule_id": row.id,
                    "success": True,
                    "shipment_id": shipment.id,
                    "error": None,
                }
            )
        except Exception as exc:
            failed += 1
            row.last_error = str(exc)[:1000]
            items.append(
                {
                    "schedule_id": row.id,
                    "success": False,
                    "shipment_id": None,
                    "error": str(exc),
                }
            )

    if due_rows:
        log_action(db, entity="shipment_schedules", action="run_due", status_code=triggered)
    db.commit()
    return {
        "examined": len(due_rows),
        "triggered": triggered,
        "failed": failed,
        "items": items,
    }
