from uuid import UUID
from typing import Literal
import csv
from io import StringIO
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Header
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.enums import UserTypeEnum
from app.models.users import User
from app.schemas.shipments import (
    ShipmentBulkStatusUpdateRequest,
    ShipmentBulkStatusUpdateResponse,
    ShipmentCreate,
    ShipmentAutoDetectStagnationResult,
    MyShipmentsDashboardOut,
    ShipmentEventCreate,
    ShipmentEventOut,
    ShipmentSlaRiskPage,
    ShipmentTimelineItem,
    ShipmentTrackingSummaryOut,
    ShipmentListPage,
    ShipmentOut,
    ShipmentStatusOut,
    ShipmentEtaOut,
    ShipmentExtraUpdate,
    ShipmentClientSlaPage,
    ShipmentOverviewStats,
    ShipmentInsuranceQuoteOut,
    ShipmentInsurancePolicyOut,
    ShipmentPriceEstimateOut,
    ShipmentPublicTrackRequest,
    ShipmentPublicTrackOut,
    ShipmentPickupSlotUpdateRequest,
    ShipmentDeliveryProofCreateRequest,
    RelayPickupForecastOut,
    ShipmentTimeseriesStats,
    ShipmentStatusUpdate,
)
from app.services.shipment_service import (
    bulk_update_shipment_status,
    create_shipment_event,
    create_shipment,
    get_shipment,
    get_shipment_timeline,
    get_shipment_tracking_summary,
    get_shipment_overview_stats,
    get_shipment_timeseries_stats,
    list_shipment_events,
    list_my_shipments,
    list_sla_risk_shipments,
    list_my_shipments_sla_page,
    list_shipments,
    list_shipment_statuses,
    shipment_status_exists,
    auto_detect_stagnation_incidents,
    get_my_shipments_dashboard,
    get_shipment_eta,
    get_insurance_quote,
    get_insurance_policy_summary,
    get_corridor_price_estimate,
    get_public_tracking_by_shipment_no,
    update_pickup_slot,
    get_relay_pickup_forecast,
    capture_delivery_proof,
    PublicTrackingLockedError,
    update_shipment_extra,
    update_shipment_status,
    ShipmentNotFoundError,
)
from app.services.idempotency_service import (
    has_processed_idempotency_key,
    mark_processed_idempotency_key,
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


@router.get("/insurance/quote", response_model=ShipmentInsuranceQuoteOut)
def shipment_insurance_quote_endpoint(
    declared_value: float = Query(..., ge=0),
    insurance_opt_in: bool = Query(default=True),
    _user=Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.admin,
        )
    ),
):
    return get_insurance_quote(
        declared_value=declared_value,
        insurance_opt_in=insurance_opt_in,
    )


@router.get("/insurance/policy", response_model=ShipmentInsurancePolicyOut)
def shipment_insurance_policy_endpoint(
    _user=Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    return get_insurance_policy_summary()


@router.get("/pricing/estimate", response_model=ShipmentPriceEstimateOut)
def shipment_price_estimate_endpoint(
    origin_relay_id: UUID = Query(...),
    destination_relay_id: UUID = Query(...),
    declared_value: float | None = Query(default=None, ge=0),
    insurance_opt_in: bool = Query(default=False),
    db: Session = Depends(get_db),
    _user=Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    try:
        return get_corridor_price_estimate(
            db,
            origin_relay_id=origin_relay_id,
            destination_relay_id=destination_relay_id,
            declared_value=declared_value,
            insurance_opt_in=insurance_opt_in,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/public/estimate", response_model=ShipmentPriceEstimateOut)
def shipment_public_price_estimate_endpoint(
    origin_relay_id: UUID = Query(...),
    destination_relay_id: UUID = Query(...),
    declared_value: float | None = Query(default=None, ge=0),
    insurance_opt_in: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    try:
        return get_corridor_price_estimate(
            db,
            origin_relay_id=origin_relay_id,
            destination_relay_id=destination_relay_id,
            declared_value=declared_value,
            insurance_opt_in=insurance_opt_in,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/public/track", response_model=ShipmentPublicTrackOut)
def shipment_public_track_endpoint(
    payload: ShipmentPublicTrackRequest,
    db: Session = Depends(get_db),
):
    try:
        return get_public_tracking_by_shipment_no(
            db,
            shipment_no=payload.shipment_no,
            phone_e164=payload.phone_e164,
            access_code=payload.access_code,
        )
    except PublicTrackingLockedError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "message": str(exc),
                "error_code": "public_track_locked",
                "retry_after_seconds": exc.retry_after_seconds,
            },
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[ShipmentOut])
def list_shipments_endpoint(
    status: str | None = Query(default=None),
    sender_phone: str | None = Query(default=None),
    receiver_phone: str | None = Query(default=None),
    shipment_no: str | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=100),
    extra_key: str | None = Query(default=None, min_length=1, max_length=120),
    extra_value: str | None = Query(default=None, min_length=0, max_length=500),
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
        extra_key=extra_key,
        extra_value=extra_value,
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
    extra_key: str | None = Query(default=None, min_length=1, max_length=120),
    extra_value: str | None = Query(default=None, min_length=0, max_length=500),
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
        extra_key=extra_key,
        extra_value=extra_value,
        sort=sort,
        offset=offset,
        limit=limit,
    )
    return ShipmentListPage(items=items, total=total, offset=offset, limit=limit)


@router.get("/my/dashboard", response_model=MyShipmentsDashboardOut)
def my_shipments_dashboard_endpoint(
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
    return get_my_shipments_dashboard(db, current_user)


@router.get("/my/sla-summary", response_model=ShipmentClientSlaPage)
def list_my_shipments_sla_summary_endpoint(
    direction: Literal["all", "sent", "received"] = Query(default="all"),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=100),
    sort: Literal["created_at_desc", "created_at_asc"] = Query(default="created_at_desc"),
    late_only: bool = Query(default=False),
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
    return list_my_shipments_sla_page(
        db,
        current_user,
        direction=direction,
        status=status,
        q=q,
        sort=sort,
        offset=offset,
        limit=limit,
        late_only=late_only,
    )


@router.get("/my/export.csv")
def export_my_shipments_csv_endpoint(
    direction: Literal["all", "sent", "received"] = Query(default="all"),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=100),
    sort: Literal["created_at_desc", "created_at_asc"] = Query(default="created_at_desc"),
    limit: int = Query(default=5000, ge=1, le=5000),
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

    items, _total = list_my_shipments(
        db,
        current_user,
        direction=direction,
        status=status,
        q=q,
        sort=sort,
        offset=0,
        limit=limit,
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "shipment_id",
            "shipment_no",
            "status",
            "sender_phone",
            "receiver_phone",
            "receiver_name",
            "origin",
            "destination",
            "created_at",
            "updated_at",
        ]
    )
    for row in items:
        writer.writerow(
            [
                str(row.id),
                row.shipment_no or "",
                row.status or "",
                row.sender_phone or "",
                row.receiver_phone or "",
                row.receiver_name or "",
                str(row.origin) if row.origin else "",
                str(row.destination) if row.destination else "",
                row.created_at.isoformat() if row.created_at else "",
                row.updated_at.isoformat() if row.updated_at else "",
            ]
        )
    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="my_shipments.csv"'},
    )


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
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    _validate_bulk_statuses_or_422(db, payload)
    operation = "shipments_bulk_status"
    if x_idempotency_key and has_processed_idempotency_key(
        db,
        operation=operation,
        key=x_idempotency_key,
        actor_user_id=current_user.id,
    ):
        raise HTTPException(status_code=409, detail="Duplicate idempotent request")
    result = bulk_update_shipment_status(
        db,
        payload.items,
        continue_on_error=payload.continue_on_error,
        dry_run=payload.dry_run,
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


@router.get("/ops/sla-risks", response_model=ShipmentSlaRiskPage)
def list_sla_risks_endpoint(
    state: Literal["on_track", "at_risk", "late"] | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.agent,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    return list_sla_risk_shipments(
        db,
        current_user,
        state=state,
        limit=limit,
    )


@router.post("/ops/incidents/auto-detect-stagnation", response_model=ShipmentAutoDetectStagnationResult)
def auto_detect_stagnation_incidents_endpoint(
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(
        require_roles(
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    try:
        return auto_detect_stagnation_incidents(db, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/relays/{relay_id}/pickup-forecast", response_model=RelayPickupForecastOut)
def relay_pickup_forecast_endpoint(
    relay_id: UUID,
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.admin)),
):
    return get_relay_pickup_forecast(db, relay_id=relay_id, hours=hours)


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


@router.get("/{shipment_id}/tracking-summary", response_model=ShipmentTrackingSummaryOut)
def get_shipment_tracking_summary_endpoint(
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
        return get_shipment_tracking_summary(db, shipment_id, current_user)
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{shipment_id}/eta", response_model=ShipmentEtaOut)
def get_shipment_eta_endpoint(
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
        return get_shipment_eta(db, shipment_id, current_user)
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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


@router.get("/{shipment_id}/timeline", response_model=list[ShipmentTimelineItem])
def shipment_timeline_endpoint(
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
        return get_shipment_timeline(db, shipment_id, current_user)
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
            extra=payload.extra,
        )
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{shipment_id}/pickup-slot", response_model=ShipmentOut)
def update_shipment_pickup_slot_endpoint(
    shipment_id: UUID,
    payload: ShipmentPickupSlotUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    try:
        return update_pickup_slot(
            db,
            shipment_id,
            current_user,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            note=payload.note,
        )
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{shipment_id}/delivery-proof", response_model=ShipmentOut)
def create_shipment_delivery_proof_endpoint(
    shipment_id: UUID,
    payload: ShipmentDeliveryProofCreateRequest,
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
    try:
        return capture_delivery_proof(
            db,
            shipment_id,
            receiver_name=payload.receiver_name,
            signature=payload.signature,
            geo_lat=payload.geo_lat,
            geo_lng=payload.geo_lng,
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


@router.patch("/{shipment_id}/extra", response_model=ShipmentOut)
def update_shipment_extra_endpoint(
    shipment_id: UUID,
    payload: ShipmentExtraUpdate,
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
    try:
        return update_shipment_extra(
            db,
            shipment_id,
            extra=payload.extra,
            merge=payload.merge,
        )
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
