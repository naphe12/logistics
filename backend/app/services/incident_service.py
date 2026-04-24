from uuid import UUID

from sqlalchemy.orm import Session

from app.models.incidents import Claim, Incident, IncidentUpdate
from app.models.shipments import Shipment
from app.models.statuses import IncidentStatus
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
) -> list[Incident]:
    query = db.query(Incident)
    if shipment_id is not None:
        query = query.filter(Incident.shipment_id == shipment_id)
    if status:
        query = query.filter(Incident.status == status)
    if incident_type:
        query = query.filter(Incident.incident_type == incident_type)
    return query.order_by(Incident.created_at.desc()).all()


def get_incident(db: Session, incident_id: UUID) -> Incident | None:
    return db.query(Incident).filter(Incident.id == incident_id).first()


def create_incident(db: Session, payload: IncidentCreate) -> Incident:
    shipment = db.query(Shipment).filter(Shipment.id == payload.shipment_id).first()
    if not shipment:
        raise IncidentValidationError("Shipment not found")
    _require_incident_status_exists(db, "open")

    incident = Incident(
        shipment_id=payload.shipment_id,
        incident_type=payload.incident_type,
        description=payload.description,
        status="open",
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


def list_incident_updates(db: Session, incident_id: UUID) -> list[IncidentUpdate]:
    incident = get_incident(db, incident_id)
    if not incident:
        raise IncidentNotFoundError("Incident not found")
    return (
        db.query(IncidentUpdate)
        .filter(IncidentUpdate.incident_id == incident_id)
        .order_by(IncidentUpdate.created_at.desc())
        .all()
    )


def create_claim(db: Session, payload: ClaimCreate) -> Claim:
    incident = get_incident(db, payload.incident_id)
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
) -> list[Claim]:
    query = db.query(Claim)
    if incident_id is not None:
        query = query.filter(Claim.incident_id == incident_id)
    if shipment_id is not None:
        query = query.filter(Claim.shipment_id == shipment_id)
    if status:
        query = query.filter(Claim.status == status)
    return query.order_by(Claim.created_at.desc()).all()


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
