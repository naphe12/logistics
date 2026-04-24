from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.enums import UserTypeEnum
from app.models.users import User
from app.schemas.incidents import (
    ClaimCreate,
    ClaimOut,
    ClaimUpdateStatusRequest,
    IncidentAddUpdateRequest,
    IncidentCreate,
    IncidentOut,
    IncidentUpdateOut,
    IncidentUpdateStatusRequest,
)
from app.services.incident_service import (
    IncidentNotFoundError,
    IncidentValidationError,
    add_incident_update,
    create_claim,
    create_incident,
    get_incident,
    list_claims,
    list_incident_statuses,
    list_incident_updates,
    list_incidents,
    update_claim_status,
    update_incident_status,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("/statuses", response_model=list[str])
def list_incident_statuses_endpoint(
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    rows = list_incident_statuses(db)
    return [row.code for row in rows]


@router.get("", response_model=list[IncidentOut])
def list_incidents_endpoint(
    shipment_id: UUID | None = None,
    status: str | None = None,
    incident_type: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    return list_incidents(db, shipment_id=shipment_id, status=status, incident_type=incident_type)


@router.get("/claims", response_model=list[ClaimOut])
def list_claims_endpoint(
    incident_id: UUID | None = None,
    shipment_id: UUID | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    return list_claims(db, incident_id=incident_id, shipment_id=shipment_id, status=status)


@router.post("/claims", response_model=ClaimOut)
def create_claim_endpoint(
    payload: ClaimCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        return create_claim(db, payload)
    except IncidentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/claims/{claim_id}/status", response_model=ClaimOut)
def update_claim_status_endpoint(
    claim_id: UUID,
    payload: ClaimUpdateStatusRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    try:
        return update_claim_status(
            db,
            claim_id,
            status=payload.status,
            resolution_note=payload.resolution_note,
            refunded_payment_id=payload.refunded_payment_id,
        )
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IncidentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident_endpoint(
    incident_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    incident = get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("", response_model=IncidentOut)
def create_incident_endpoint(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        return create_incident(db, payload)
    except IncidentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/{incident_id}/status", response_model=IncidentOut)
def update_incident_status_endpoint(
    incident_id: UUID,
    payload: IncidentUpdateStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    try:
        updated = update_incident_status(db, incident_id, payload.status)
        if payload.status == "resolved":
            actor = current_user.phone_e164 or str(current_user.id)
            add_incident_update(
                db,
                incident_id,
                f"Resolved by {actor}.",
            )
        return updated
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IncidentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{incident_id}/updates", response_model=list[IncidentUpdateOut])
def list_incident_updates_endpoint(
    incident_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        return list_incident_updates(db, incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{incident_id}/updates", response_model=IncidentUpdateOut)
def add_incident_update_endpoint(
    incident_id: UUID,
    payload: IncidentAddUpdateRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    try:
        return add_incident_update(db, incident_id, payload.message)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
