from uuid import UUID
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.incidents import Claim, Incident, IncidentUpdate
from app.models.shipments import Shipment
from app.models.statuses import IncidentStatus
from app.models.users import User
from app.enums import UserTypeEnum
from sqlalchemy import or_
from app.schemas.incidents import ClaimCreate, IncidentCreate
from app.services.audit_service import log_action


class IncidentError(Exception):
    pass


class IncidentNotFoundError(IncidentError):
    pass


class IncidentValidationError(IncidentError):
    pass


def list_incident_statuses(db: Session) -> list[IncidentStatus]:
    return db.query(IncidentStatus).order_by(IncidentStatus.code.asc()).all()


def _apply_incident_visibility(query, current_user: User | None):
    if not current_user:
        return query
    if current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        return query.join(Shipment, Shipment.id == Incident.shipment_id).filter(
            or_(
                Shipment.sender_id == current_user.id,
                Shipment.sender_phone == current_user.phone_e164,
                Shipment.receiver_phone == current_user.phone_e164,
            )
        )
    return query


def _require_incident_status_exists(db: Session, status_code: str) -> None:
    exists = db.query(IncidentStatus.code).filter(IncidentStatus.code == status_code).first()
    if not exists:
        raise IncidentValidationError(f"Unknown incident status: {status_code}")


def list_incidents(
    db: Session,
    *,
    shipment_id: UUID | None = None,
    status: str | None = None,
    incident_type: str | None = None,
    extra_key: str | None = None,
    extra_value: str | None = None,
    current_user: User | None = None,
) -> list[Incident]:
    query = _apply_incident_visibility(db.query(Incident), current_user)
    if shipment_id is not None:
        query = query.filter(Incident.shipment_id == shipment_id)
    if status:
        query = query.filter(Incident.status == status)
    if incident_type:
        query = query.filter(Incident.incident_type == incident_type)
    if extra_key and extra_value is not None:
        query = query.filter(Incident.extra[extra_key].astext == extra_value)
    return query.order_by(Incident.created_at.desc()).all()


def list_incidents_page(
    db: Session,
    *,
    shipment_id: UUID | None = None,
    status: str | None = None,
    incident_type: str | None = None,
    extra_key: str | None = None,
    extra_value: str | None = None,
    current_user: User | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    offset = max(0, offset)
    limit = max(1, min(limit, 200))
    query = _apply_incident_visibility(db.query(Incident), current_user)
    if shipment_id is not None:
        query = query.filter(Incident.shipment_id == shipment_id)
    if status:
        query = query.filter(Incident.status == status)
    if incident_type:
        query = query.filter(Incident.incident_type == incident_type)
    if extra_key and extra_value is not None:
        query = query.filter(Incident.extra[extra_key].astext == extra_value)
    total = query.count()
    items = query.order_by(Incident.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


def get_incident(db: Session, incident_id: UUID, current_user: User | None = None) -> Incident | None:
    query = _apply_incident_visibility(db.query(Incident), current_user)
    return query.filter(Incident.id == incident_id).first()


def create_incident(db: Session, payload: IncidentCreate, current_user: User | None = None) -> Incident:
    shipment = db.query(Shipment).filter(Shipment.id == payload.shipment_id).first()
    if not shipment:
        raise IncidentValidationError("Shipment not found")
    if current_user and current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        is_owner = (
            shipment.sender_id == current_user.id
            or shipment.sender_phone == current_user.phone_e164
            or shipment.receiver_phone == current_user.phone_e164
        )
        if not is_owner:
            raise IncidentValidationError("Not allowed for this shipment")
    _require_incident_status_exists(db, "open")

    incident = Incident(
        shipment_id=payload.shipment_id,
        incident_type=payload.incident_type,
        description=payload.description,
        status="open",
        extra=payload.extra,
    )
    db.add(incident)
    log_action(db, entity="incidents", action="create")
    db.commit()
    db.refresh(incident)
    return incident


def update_incident_status(db: Session, incident_id: UUID, status: str) -> Incident:
    _require_incident_status_exists(db, status)
    incident = get_incident(db, incident_id)
    if not incident:
        raise IncidentNotFoundError("Incident not found")
    incident.status = status
    log_action(db, entity="incidents", action="status_update")
    db.commit()
    db.refresh(incident)
    return incident


def add_incident_update(db: Session, incident_id: UUID, message: str) -> IncidentUpdate:
    incident = get_incident(db, incident_id)
    if not incident:
        raise IncidentNotFoundError("Incident not found")
    row = IncidentUpdate(incident_id=incident_id, message=message)
    db.add(row)
    log_action(db, entity="incident_updates", action="add")
    db.commit()
    db.refresh(row)
    return row


def list_incident_updates(db: Session, incident_id: UUID, current_user: User | None = None) -> list[IncidentUpdate]:
    incident = get_incident(db, incident_id, current_user=current_user)
    if not incident:
        raise IncidentNotFoundError("Incident not found")
    return (
        db.query(IncidentUpdate)
        .filter(IncidentUpdate.incident_id == incident_id)
        .order_by(IncidentUpdate.created_at.desc())
        .all()
    )


def create_claim(db: Session, payload: ClaimCreate, current_user: User | None = None) -> Claim:
    incident = get_incident(db, payload.incident_id, current_user=current_user)
    if not incident:
        raise IncidentValidationError("Incident not found")
    if incident.shipment_id != payload.shipment_id:
        raise IncidentValidationError("Claim shipment does not match incident shipment")
    claim = Claim(
        incident_id=payload.incident_id,
        shipment_id=payload.shipment_id,
        amount=payload.amount,
        status="submitted",
        reason=payload.reason,
    )
    db.add(claim)
    log_action(db, entity="claims", action="create")
    db.commit()
    db.refresh(claim)
    return claim


def list_claims(
    db: Session,
    *,
    incident_id: UUID | None = None,
    shipment_id: UUID | None = None,
    status: str | None = None,
    current_user: User | None = None,
) -> list[Claim]:
    query = db.query(Claim)
    if current_user and current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        query = query.join(Shipment, Shipment.id == Claim.shipment_id).filter(
            or_(
                Shipment.sender_id == current_user.id,
                Shipment.sender_phone == current_user.phone_e164,
                Shipment.receiver_phone == current_user.phone_e164,
            )
        )
    if incident_id is not None:
        query = query.filter(Claim.incident_id == incident_id)
    if shipment_id is not None:
        query = query.filter(Claim.shipment_id == shipment_id)
    if status:
        query = query.filter(Claim.status == status)
    return query.order_by(Claim.created_at.desc()).all()


def list_claims_page(
    db: Session,
    *,
    incident_id: UUID | None = None,
    shipment_id: UUID | None = None,
    status: str | None = None,
    current_user: User | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    offset = max(0, offset)
    limit = max(1, min(limit, 200))
    query = db.query(Claim)
    if current_user and current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        query = query.join(Shipment, Shipment.id == Claim.shipment_id).filter(
            or_(
                Shipment.sender_id == current_user.id,
                Shipment.sender_phone == current_user.phone_e164,
                Shipment.receiver_phone == current_user.phone_e164,
            )
        )
    if incident_id is not None:
        query = query.filter(Claim.incident_id == incident_id)
    if shipment_id is not None:
        query = query.filter(Claim.shipment_id == shipment_id)
    if status:
        query = query.filter(Claim.status == status)
    total = query.count()
    items = query.order_by(Claim.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


def update_claim_status(
    db: Session,
    claim_id: UUID,
    *,
    status: str,
    resolution_note: str | None = None,
    refunded_payment_id: UUID | None = None,
) -> Claim:
    allowed = {"submitted", "reviewing", "approved", "rejected", "paid"}
    if status not in allowed:
        raise IncidentValidationError(f"Unsupported claim status: {status}")
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise IncidentNotFoundError("Claim not found")
    claim.status = status
    if resolution_note is not None:
        claim.resolution_note = resolution_note
    if refunded_payment_id is not None:
        claim.refunded_payment_id = refunded_payment_id
    log_action(db, entity="claims", action="status_update")
    db.commit()
    db.refresh(claim)
    return claim


def update_incident_extra(
    db: Session,
    incident_id: UUID,
    *,
    extra: dict,
    merge: bool = True,
) -> Incident:
    incident = get_incident(db, incident_id)
    if not incident:
        raise IncidentNotFoundError("Incident not found")

    if merge and isinstance(incident.extra, dict):
        incident.extra = {**incident.extra, **extra}
    else:
        incident.extra = extra

    log_action(db, entity="incidents", action="extra_update")
    db.commit()
    db.refresh(incident)
    return incident


def get_incident_dashboard(
    db: Session,
    *,
    stale_hours: int = 24,
) -> dict:
    stale_hours = max(1, min(stale_hours, 24 * 30))
    cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)

    total = db.query(Incident).count()
    open_count = db.query(Incident).filter(Incident.status == "open").count()
    investigating_count = db.query(Incident).filter(Incident.status == "investigating").count()
    resolved_count = db.query(Incident).filter(Incident.status == "resolved").count()
    stale_open_count = (
        db.query(Incident)
        .filter(
            Incident.status.in_(["open", "investigating"]),
            Incident.created_at <= cutoff,
        )
        .count()
    )
    type_rows = (
        db.query(func.coalesce(Incident.incident_type, "unknown"), func.count(Incident.id))
        .group_by(Incident.incident_type)
        .all()
    )
    by_type = {str(incident_type): int(count) for incident_type, count in type_rows}

    return {
        "total": total,
        "open_count": open_count,
        "investigating_count": investigating_count,
        "resolved_count": resolved_count,
        "stale_open_count": stale_open_count,
        "by_type": by_type,
    }


def get_incident_timeline(db: Session, incident_id: UUID, current_user: User | None = None) -> list[dict]:
    incident = get_incident(db, incident_id, current_user=current_user)
    if not incident:
        raise IncidentNotFoundError("Incident not found")

    items: list[dict] = [
        {
            "occurred_at": incident.created_at or datetime.now(UTC),
            "kind": "incident_created",
            "status": incident.status,
            "message": incident.description,
            "incident_type": incident.incident_type,
            "extra": incident.extra if isinstance(incident.extra, dict) else None,
        }
    ]
    updates = (
        db.query(IncidentUpdate)
        .filter(IncidentUpdate.incident_id == incident_id)
        .order_by(IncidentUpdate.created_at.asc())
        .all()
    )
    for row in updates:
        items.append(
            {
                "occurred_at": row.created_at or datetime.now(UTC),
                "kind": "incident_update",
                "status": None,
                "message": row.message,
                "incident_type": None,
                "extra": None,
            }
        )
    items.sort(key=lambda item: item["occurred_at"])
    return items


def auto_escalate_stale_incidents(
    db: Session,
    *,
    stale_hours: int = 24,
    limit: int = 200,
    dry_run: bool = False,
) -> dict:
    stale_hours = max(1, min(stale_hours, 24 * 30))
    limit = max(1, min(limit, 500))
    _require_incident_status_exists(db, "investigating")
    cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)

    candidates = (
        db.query(Incident)
        .filter(Incident.status == "open", Incident.created_at <= cutoff)
        .order_by(Incident.created_at.asc())
        .limit(limit)
        .all()
    )

    escalated = 0
    skipped = 0
    for incident in candidates:
        last_update = (
            db.query(func.max(IncidentUpdate.created_at))
            .filter(IncidentUpdate.incident_id == incident.id)
            .scalar()
        )
        reference_time = last_update or incident.updated_at or incident.created_at
        if reference_time and reference_time > cutoff:
            skipped += 1
            continue
        escalated += 1
        if dry_run:
            continue

        incident.status = "investigating"
        extra = incident.extra if isinstance(incident.extra, dict) else {}
        extra["auto_escalation"] = {
            "stale_hours": stale_hours,
            "escalated_at": datetime.now(UTC).isoformat(),
        }
        incident.extra = extra
        db.add(
            IncidentUpdate(
                incident_id=incident.id,
                message=f"Auto-escalated after {stale_hours}h without progress.",
            )
        )

    if escalated > 0 and not dry_run:
        log_action(db, entity="incidents", action="auto_escalate_stale", status_code=escalated)
    if not dry_run:
        db.commit()

    return {
        "examined": len(candidates),
        "escalated": escalated,
        "skipped": skipped,
        "stale_hours": stale_hours,
        "dry_run": dry_run,
    }
