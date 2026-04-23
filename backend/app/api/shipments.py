from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.shipments import ShipmentCreate, ShipmentOut, ShipmentStatusUpdate
from app.services.shipment_service import create_shipment, update_shipment_status, ShipmentNotFoundError
from app.dependencies import get_current_user

router = APIRouter(prefix="/shipments", tags=["shipments"])


@router.post("", response_model=ShipmentOut)
def create_shipment_endpoint(
    payload: ShipmentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return create_shipment(db, payload, background_tasks=background_tasks)


@router.patch("/{shipment_id}/status", response_model=ShipmentOut)
def update_shipment_status_endpoint(
    shipment_id: UUID,
    payload: ShipmentStatusUpdate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    try:
        return update_shipment_status(db, shipment_id, payload)
    except ShipmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
