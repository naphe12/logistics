from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.enums import UserTypeEnum
from app.models.shipments import Shipment, ShipmentEvent
from app.schemas.codes import (
    PickupCodeConfirmRequest,
    PickupCodeConfirmResponse,
    PickupCodeResponse,
    PickupCodeValidationRequest,
    PickupCodeValidationResponse,
)
from app.services.code_service import create_pickup_code, validate_pickup_code
from app.realtime.events import emit_shipment_status_update
from app.dependencies import require_roles

router = APIRouter(prefix="/codes", tags=["codes"])


def _get_shipment_or_404(db: Session, shipment_id: UUID) -> Shipment:
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment


@router.post("/shipments/{shipment_id}/pickup", response_model=PickupCodeResponse)
def create_pickup_code_endpoint(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(
        require_roles(
            UserTypeEnum.agent,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    shipment = _get_shipment_or_404(db, shipment_id)
    row, raw = create_pickup_code(db, shipment_id)
    shipment.status = "ready_for_pickup"
    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            relay_id=shipment.destination,
            event_type="shipment_ready_for_pickup",
        )
    )
    db.commit()
    db.refresh(row)
    emit_shipment_status_update(
        shipment_id=shipment.id,
        status=shipment.status or "ready_for_pickup",
        event_type="shipment_ready_for_pickup",
        relay_id=shipment.destination,
    )
    return PickupCodeResponse(id=row.id, shipment_id=row.shipment_id, code=raw, expires_at=row.expires_at)


@router.post(
    "/shipments/{shipment_id}/pickup/validate",
    response_model=PickupCodeValidationResponse,
)
def validate_pickup_code_endpoint(
    shipment_id: UUID,
    payload: PickupCodeValidationRequest,
    db: Session = Depends(get_db),
    _user=Depends(
        require_roles(
            UserTypeEnum.agent,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    _get_shipment_or_404(db, shipment_id)
    valid, message, error_code = validate_pickup_code(db, shipment_id, payload.code, consume=False)
    db.commit()
    return PickupCodeValidationResponse(
        shipment_id=shipment_id,
        valid=valid,
        message=message,
        error_code=error_code,
    )


@router.post(
    "/shipments/{shipment_id}/pickup/confirm",
    response_model=PickupCodeConfirmResponse,
)
def confirm_pickup_code_endpoint(
    shipment_id: UUID,
    payload: PickupCodeConfirmRequest,
    db: Session = Depends(get_db),
    _user=Depends(
        require_roles(
            UserTypeEnum.agent,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    shipment = _get_shipment_or_404(db, shipment_id)
    valid, message, error_code = validate_pickup_code(db, shipment_id, payload.code, consume=True)
    if not valid:
        db.commit()
        return PickupCodeConfirmResponse(
            shipment_id=shipment_id,
            confirmed=False,
            status=shipment.status,
            message=message,
            error_code=error_code,
        )

    shipment.status = "delivered"
    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            relay_id=payload.relay_id,
            event_type=payload.event_type or "shipment_delivered_to_receiver",
        )
    )
    db.commit()
    db.refresh(shipment)
    emit_shipment_status_update(
        shipment_id=shipment.id,
        status=shipment.status or "delivered",
        event_type=payload.event_type or "shipment_delivered_to_receiver",
        relay_id=payload.relay_id,
    )
    return PickupCodeConfirmResponse(
        shipment_id=shipment_id,
        confirmed=True,
        status=shipment.status,
        message="Pickup confirmed and shipment delivered",
        error_code=None,
    )
