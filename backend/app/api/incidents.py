from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.enums import UserTypeEnum
from app.models.users import User
from app.schemas.incidents import (
    ClaimCreate,
    ClaimListPageOut,
    ClaimOut,
    ClaimUpdateStatusRequest,
    IncidentAutoEscalateResult,
    IncidentAddUpdateRequest,
    IncidentCreate,
    IncidentDashboardOut,
    IncidentExtraUpdate,
    IncidentListPageOut,
    IncidentOut,
    IncidentTimelineItem,
    IncidentUpdateOut,
    IncidentUpdateStatusRequest,
)
from app.services.incident_service import (
    IncidentNotFoundError,
    IncidentValidationError,
    add_incident_update,
    auto_escalate_stale_incidents,
    create_claim,
    create_incident,
    get_incident,
    get_incident_dashboard,
    get_incident_timeline,
    list_claims,
    list_claims_page,
    list_incident_statuses,
    list_incident_updates,
    list_incidents,
    list_incidents_page,
    update_claim_status,
    update_incident_extra,
    update_incident_status,
)
from app.services.idempotency_service import (
    has_processed_idempotency_key,
    mark_processed_idempotency_key,
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
    extra_key: str | None = None,
    extra_value: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    return list_incidents(
        db,
        shipment_id=shipment_id,
        status=status,
        incident_type=incident_type,
        extra_key=extra_key,
        extra_value=extra_value,
        current_user=current_user,
    )


@router.get("/page", response_model=IncidentListPageOut)
def list_incidents_page_endpoint(
    shipment_id: UUID | None = None,
    status: str | None = None,
    incident_type: str | None = None,
    extra_key: str | None = None,
    extra_value: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    return list_incidents_page(
        db,
        shipment_id=shipment_id,
        status=status,
        incident_type=incident_type,
        extra_key=extra_key,
        extra_value=extra_value,
        current_user=current_user,
        offset=offset,
        limit=limit,
    )


@router.get("/claims", response_model=list[ClaimOut])
def list_claims_endpoint(
    incident_id: UUID | None = None,
    shipment_id: UUID | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    return list_claims(
        db,
        incident_id=incident_id,
        shipment_id=shipment_id,
        status=status,
        current_user=current_user,
    )


@router.get("/claims/page", response_model=ClaimListPageOut)
def list_claims_page_endpoint(
    incident_id: UUID | None = None,
    shipment_id: UUID | None = None,
    status: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    return list_claims_page(
        db,
        incident_id=incident_id,
        shipment_id=shipment_id,
        status=status,
        current_user=current_user,
        offset=offset,
        limit=limit,
    )


@router.get("/dashboard", response_model=IncidentDashboardOut)
def incident_dashboard_endpoint(
    stale_hours: int = Query(default=24, ge=1, le=720),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    return get_incident_dashboard(db, stale_hours=stale_hours)


@router.post("/ops/auto-escalate", response_model=IncidentAutoEscalateResult)
def auto_escalate_incidents_endpoint(
    stale_hours: int = Query(default=24, ge=1, le=720),
    limit: int = Query(default=200, ge=1, le=500),
    dry_run: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    operation = "incidents_auto_escalate"
    if x_idempotency_key and has_processed_idempotency_key(
        db,
        operation=operation,
        key=x_idempotency_key,
        actor_user_id=current_user.id,
    ):
        raise HTTPException(status_code=409, detail="Duplicate idempotent request")
    try:
        result = auto_escalate_stale_incidents(
            db,
            stale_hours=stale_hours,
            limit=limit,
            dry_run=dry_run,
        )
        if x_idempotency_key:
            mark_processed_idempotency_key(
                db,
                operation=operation,
                key=x_idempotency_key,
                actor_user_id=current_user.id,
                actor_phone=current_user.phone_e164,
            )
            db.commit()
        return result
    except IncidentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/claims", response_model=ClaimOut)
def create_claim_endpoint(
    payload: ClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        return create_claim(db, payload, current_user=current_user)
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
            amount_approved=payload.amount_approved,
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
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    incident = get_incident(db, incident_id, current_user=current_user)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.get("/{incident_id}/timeline", response_model=list[IncidentTimelineItem])
def incident_timeline_endpoint(
    incident_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        return get_incident_timeline(db, incident_id, current_user=current_user)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=IncidentOut)
def create_incident_endpoint(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        return create_incident(db, payload, current_user=current_user)
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
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        return list_incident_updates(db, incident_id, current_user=current_user)
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


@router.patch("/{incident_id}/extra", response_model=IncidentOut)
def update_incident_extra_endpoint(
    incident_id: UUID,
    payload: IncidentExtraUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    try:
        return update_incident_extra(
            db,
            incident_id,
            extra=payload.extra,
            merge=payload.merge,
        )
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
