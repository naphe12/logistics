from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.enums import UserTypeEnum
from app.schemas.auth import UserOut
from app.schemas.relays import (
    RelayCapacityOut,
    RelayCreate,
    RelayInventoryOut,
    RelayInventoryUpsert,
    RelayManagerApplicationCreate,
    RelayManagerApplicationOut,
    RelayManagerApplicationReview,
    RelayOut,
    RelayUpdate,
)
from app.services.relay_service import (
    AgentAssignmentError,
    RelayCapacityError,
    RelayConflictError,
    RelayInventoryError,
    RelayNotFoundError,
    assign_agent_to_relay,
    create_relay,
    delete_relay,
    get_relay_capacity_status,
    get_relay,
    list_relay_inventory,
    list_relay_agents,
    list_relay_manager_applications,
    list_relays,
    list_relays_with_filters,
    create_relay_manager_application,
    review_relay_manager_application,
    upsert_relay_inventory,
    unassign_agent_from_relay,
    update_relay,
)

router = APIRouter(prefix="/relays", tags=["relays"])


@router.get("", response_model=list[RelayOut])
def list_relays_endpoint(
    q: str | None = Query(default=None, min_length=1, max_length=120),
    province_id: UUID | None = Query(default=None),
    commune_id: UUID | None = Query(default=None),
    only_active: bool | None = Query(default=None),
    operational_status: str | None = Query(default=None, pattern="^(open|closed|full)$"),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    return list_relays_with_filters(
        db,
        q=q,
        province_id=province_id,
        commune_id=commune_id,
        only_active=only_active,
        operational_status=operational_status,
    )


@router.get("/public", response_model=list[RelayOut])
def list_public_relays_endpoint(
    q: str | None = Query(default=None, min_length=1, max_length=120),
    province_id: UUID | None = Query(default=None),
    commune_id: UUID | None = Query(default=None),
    operational_status: str | None = Query(default=None, pattern="^(open|closed|full)$"),
    db: Session = Depends(get_db),
):
    return list_relays_with_filters(
        db,
        q=q,
        province_id=province_id,
        commune_id=commune_id,
        only_active=True,
        operational_status=operational_status,
    )


@router.get("/{relay_id}", response_model=RelayOut)
def get_relay_endpoint(
    relay_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    relay = get_relay(db, relay_id)
    if not relay:
        raise HTTPException(status_code=404, detail="Relay not found")
    return relay


@router.post("", response_model=RelayOut)
def create_relay_endpoint(
    payload: RelayCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin)),
):
    try:
        return create_relay(db, payload)
    except RelayConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{relay_id}", response_model=RelayOut)
def update_relay_endpoint(
    relay_id: UUID,
    payload: RelayUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin)),
):
    try:
        return update_relay(db, relay_id, payload)
    except RelayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RelayConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{relay_id}")
def delete_relay_endpoint(
    relay_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin)),
):
    try:
        delete_relay(db, relay_id)
    except RelayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"detail": "Relay deleted"}


@router.get("/{relay_id}/agents", response_model=list[UserOut])
def list_relay_agents_endpoint(
    relay_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    try:
        return list_relay_agents(db, relay_id)
    except RelayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{relay_id}/agents/{user_id}", response_model=UserOut)
def assign_agent_endpoint(
    relay_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin)),
):
    try:
        return assign_agent_to_relay(db, relay_id, user_id)
    except RelayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentAssignmentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{relay_id}/agents/{user_id}", response_model=UserOut)
def unassign_agent_endpoint(
    relay_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin)),
):
    try:
        return unassign_agent_from_relay(db, relay_id, user_id)
    except RelayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentAssignmentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{relay_id}/inventory", response_model=list[RelayInventoryOut])
def list_relay_inventory_endpoint(
    relay_id: UUID,
    present_only: bool = False,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    try:
        return list_relay_inventory(db, relay_id, present_only=present_only)
    except RelayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{relay_id}/capacity", response_model=RelayCapacityOut)
def get_relay_capacity_endpoint(
    relay_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    try:
        return get_relay_capacity_status(db, relay_id)
    except RelayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{relay_id}/inventory", response_model=RelayInventoryOut)
def upsert_relay_inventory_endpoint(
    relay_id: UUID,
    payload: RelayInventoryUpsert,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    try:
        row = upsert_relay_inventory(
            db,
            relay_id,
            shipment_id=payload.shipment_id,
            present=payload.present,
        )
        return {
            "id": row.id,
            "relay_id": row.relay_id,
            "shipment_id": row.shipment_id,
            "present": row.present,
            "shipment_no": None,
            "shipment_status": None,
        }
    except RelayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RelayCapacityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RelayInventoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/manager-applications", response_model=RelayManagerApplicationOut)
def create_relay_manager_application_endpoint(
    payload: RelayManagerApplicationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    return create_relay_manager_application(
        db,
        payload,
        created_by_user_id=current_user.id,
    )


@router.get("/manager-applications", response_model=list[RelayManagerApplicationOut])
def list_relay_manager_applications_endpoint(
    status: str | None = Query(default=None, pattern="^(pending|validated|rejected|training_in_progress|trained)$"),
    relay_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return list_relay_manager_applications(
        db,
        status=status,
        relay_id=relay_id,
        limit=limit,
    )


@router.patch("/manager-applications/{application_id}", response_model=RelayManagerApplicationOut)
def review_relay_manager_application_endpoint(
    application_id: UUID,
    payload: RelayManagerApplicationReview,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    try:
        return review_relay_manager_application(
            db,
            application_id,
            payload,
            reviewed_by_user_id=current_user.id,
        )
    except RelayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
