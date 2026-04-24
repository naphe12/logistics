from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.enums import UserTypeEnum
from app.schemas.transport import (
    GroupingSuggestionResponse,
    ManifestShipmentAddRequest,
    PrioritySuggestionResponse,
    TripAutoAssignPriorityRequest,
    TripAutoAssignPriorityResponse,
    TripCreate,
    TripManifestView,
    TripOut,
    TripScanRequest,
    TripScanResponse,
    TripUpdate,
)
from app.services.transport_service import (
    ManifestShipmentError,
    RelaySyncError,
    TripNotFoundError,
    add_shipment_to_manifest,
    auto_assign_priority_shipments_to_trip,
    complete_trip,
    create_trip,
    get_trip_manifest_with_shipments,
    list_trips,
    remove_shipment_from_manifest,
    scan_trip_arrival,
    scan_trip_departure,
    suggest_shipment_priority_queue,
    suggest_shipment_grouping,
    update_trip,
    now_utc,
)

router = APIRouter(prefix="/transport", tags=["transport"])


@router.get("/trips", response_model=list[TripOut])
def list_trips_endpoint(
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.driver, UserTypeEnum.agent)),
):
    return list_trips(db)


@router.get("/optimizer/grouping", response_model=GroupingSuggestionResponse)
def grouping_optimizer_endpoint(
    max_group_size: int = Query(default=10, ge=1, le=100),
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    return suggest_shipment_grouping(db, max_group_size=max_group_size, limit=limit)


@router.get("/optimizer/priority", response_model=PrioritySuggestionResponse)
def priority_optimizer_endpoint(
    max_results: int = Query(default=50, ge=1, le=200),
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    return suggest_shipment_priority_queue(db, max_results=max_results, limit=limit)


@router.post("/trips", response_model=TripOut)
def create_trip_endpoint(
    payload: TripCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return create_trip(db, route_id=payload.route_id, vehicle_id=payload.vehicle_id, status=payload.status)


@router.patch("/trips/{trip_id}", response_model=TripOut)
def update_trip_endpoint(
    trip_id: UUID,
    payload: TripUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    try:
        return update_trip(
            db,
            trip_id,
            route_id=payload.route_id,
            vehicle_id=payload.vehicle_id,
            status=payload.status,
        )
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RelaySyncError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/trips/{trip_id}/manifest", response_model=TripManifestView)
def get_trip_manifest_endpoint(
    trip_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.driver, UserTypeEnum.agent)),
):
    try:
        trip, manifest, shipments = get_trip_manifest_with_shipments(db, trip_id)
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RelaySyncError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return TripManifestView(trip=trip, manifest=manifest, shipments=shipments)


@router.post("/trips/{trip_id}/manifest/shipments")
def add_manifest_shipment_endpoint(
    trip_id: UUID,
    payload: ManifestShipmentAddRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    try:
        row = add_shipment_to_manifest(db, trip_id, payload.shipment_id)
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ManifestShipmentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"detail": "Shipment added to manifest", "manifest_shipment_id": row.id}


@router.post("/trips/{trip_id}/manifest/auto-assign-priority", response_model=TripAutoAssignPriorityResponse)
def auto_assign_priority_manifest_endpoint(
    trip_id: UUID,
    payload: TripAutoAssignPriorityRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    try:
        return auto_assign_priority_shipments_to_trip(
            db,
            trip_id,
            target_manifest_size=payload.target_manifest_size,
            max_add=payload.max_add,
            candidate_limit=payload.candidate_limit,
            vehicle_capacity=payload.vehicle_capacity,
        )
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/trips/{trip_id}/manifest/shipments/{shipment_id}")
def remove_manifest_shipment_endpoint(
    trip_id: UUID,
    shipment_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    try:
        remove_shipment_from_manifest(db, trip_id, shipment_id)
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ManifestShipmentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"detail": "Shipment removed from manifest"}


@router.post("/trips/{trip_id}/scan/departure", response_model=TripScanResponse)
def scan_departure_endpoint(
    trip_id: UUID,
    payload: TripScanRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.driver, UserTypeEnum.agent)),
):
    try:
        trip, updated = scan_trip_departure(
            db,
            trip_id,
            relay_id=payload.relay_id,
            event_type=payload.event_type,
        )
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TripScanResponse(
        trip_id=trip.id,
        status=trip.status,
        updated_shipments=updated,
        scanned_at=now_utc(),
    )


@router.post("/trips/{trip_id}/scan/arrival", response_model=TripScanResponse)
def scan_arrival_endpoint(
    trip_id: UUID,
    payload: TripScanRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.driver, UserTypeEnum.agent)),
):
    try:
        trip, updated = scan_trip_arrival(
            db,
            trip_id,
            relay_id=payload.relay_id,
            event_type=payload.event_type,
        )
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TripScanResponse(
        trip_id=trip.id,
        status=trip.status,
        updated_shipments=updated,
        scanned_at=now_utc(),
    )


@router.post("/trips/{trip_id}/complete", response_model=TripOut)
def complete_trip_endpoint(
    trip_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    try:
        return complete_trip(db, trip_id)
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
