from uuid import UUID
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.enums import UserTypeEnum
from app.models.users import User
from app.schemas.shipments import (
    ShipmentBulkStatusUpdateRequest,
    ShipmentBulkStatusUpdateResponse,
    ShipmentCreate,
    ShipmentEventCreate,
    ShipmentEventOut,
    ShipmentListPage,
    ShipmentOut,
    ShipmentStatusOut,
    ShipmentOverviewStats,
    ShipmentTimeseriesStats,
    ShipmentStatusUpdate,
)
from app.services.shipment_service import (
    bulk_update_shipment_status,
    create_shipment_event,
    create_shipment,
    get_shipment,
    get_shipment_overview_stats,
    get_shipment_timeseries_stats,
    list_shipment_events,
    list_my_shipments,
    list_shipments,
    list_shipment_statuses,
    shipment_status_exists,
    update_shipment_status,
    ShipmentNotFoundError,
)
from app.dependencies import get_current_user, require_roles

router = APIRouter(prefix="/shipments", tags=["shipments"])


def _validate_status_or_422(db: Session, status_value: str) -> None:
    if not shipment_status_exists(db, status_value):
        raise HTTPException(
            status_code=422,
            detail=f"Unknown shipment status: {status_value}",
        )


def _validate_bulk_statuses_or_422(db: Session, payload: ShipmentBulkStatusUpdateRequest) -> None:
    known_statuses = {row.code for row in list_shipment_statuses(db)}
    invalid_statuses = sorted({item.status for item in payload.items if item.status not in known_statuses})
    if invalid_statuses:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown shipment status(es): {', '.join(invalid_statuses)}",
        )


@router.post("", response_model=ShipmentOut)
def create_shipment_endpoint(
    payload: ShipmentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user=Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.admin,
        )
    ),
):
    return create_shipment(db, payload, background_tasks=background_tasks)


@router.get("", response_model=list[ShipmentOut])
def list_shipments_endpoint(
    status: str | None = Query(default=None),
    sender_phone: str | None = Query(default=None),
    receiver_phone: str | None = Query(default=None),
    shipment_no: str | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=100),
    sort: Literal["created_at_desc", "created_at_asc"] = Query(default="created_at_desc"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    if status:
        _validate_status_or_422(db, status)

    return list_shipments(
        db,
        current_user,
        status=status,
        sender_phone=sender_phone,
        receiver_phone=receiver_phone,
        shipment_no=shipment_no,
        q=q,
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get("/stats/overview", response_model=ShipmentOverviewStats)
def shipment_overview_stats_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    return get_shipment_overview_stats(db, current_user)


@router.get("/stats/timeseries", response_model=ShipmentTimeseriesStats)
def shipment_timeseries_stats_endpoint(
    days: int = Query(default=30, ge=1, le=365),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    if status:
        _validate_status_or_422(db, status)
    return get_shipment_timeseries_stats(db, current_user, days=days, status=status)


@router.get("/my", response_model=ShipmentListPage)
def list_my_shipments_endpoint(
    direction: Literal["all", "sent", "received"] = Query(default="all"),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=100),
    sort: Literal["created_at_desc", "created_at_asc"] = Query(default="created_at_desc"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    if status:
        _validate_status_or_422(db, status)

    items, total = list_my_shipments(
        db,
        current_user,
        direction=direction,
        status=status,
        q=q,
        sort=sort,
        offset=offset,
        limit=limit,
    )
    return ShipmentListPage(items=items, total=total, offset=offset, limit=limit)


@router.get("/statuses", response_model=list[ShipmentStatusOut])
def list_shipment_statuses_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    return list_shipment_statuses(db)


@router.post("/status/bulk", response_model=ShipmentBulkStatusUpdateResponse)
def bulk_update_shipment_status_endpoint(
    payload: ShipmentBulkStatusUpdateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(
        require_roles(
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    _validate_bulk_statuses_or_422(db, payload)
    return bulk_update_shipment_status(
        db,
        payload.items,
        continue_on_error=payload.continue_on_error,
    )


@router.get("/{shipment_id}", response_model=ShipmentOut)
def get_shipment_endpoint(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    shipment = get_shipment(db, shipment_id, current_user)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment


@router.get("/{shipment_id}/events", response_model=list[ShipmentEventOut])
def list_shipment_events_endpoint(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    try:
        return list_shipment_events(db, shipment_id, current_user)
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{shipment_id}/events", response_model=ShipmentEventOut)
def create_shipment_event_endpoint(
    shipment_id: UUID,
    payload: ShipmentEventCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(
        require_roles(
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    if payload.status:
        _validate_status_or_422(db, payload.status)

    try:
        return create_shipment_event(
            db,
            shipment_id,
            event_type=payload.event_type,
            relay_id=payload.relay_id,
            status=payload.status,
        )
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{shipment_id}/status", response_model=ShipmentOut)
def update_shipment_status_endpoint(
    shipment_id: UUID,
    payload: ShipmentStatusUpdate,
    db: Session = Depends(get_db),
    _user=Depends(
        require_roles(
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    _validate_status_or_422(db, payload.status)

    try:
        return update_shipment_status(db, shipment_id, payload)
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
