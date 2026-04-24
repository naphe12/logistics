from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
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
    list_relays,
    upsert_relay_inventory,
    unassign_agent_from_relay,
    update_relay,
)

router = APIRouter(prefix="/relays", tags=["relays"])


@router.get("", response_model=list[RelayOut])
def list_relays_endpoint(
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    return list_relays(db)


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
