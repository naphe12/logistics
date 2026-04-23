from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.codes import PickupCodeResponse
from app.services.code_service import create_pickup_code
from app.dependencies import get_current_user

router = APIRouter(prefix="/codes", tags=["codes"])


@router.post("/shipments/{shipment_id}/pickup", response_model=PickupCodeResponse)
def create_pickup_code_endpoint(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    row, raw = create_pickup_code(db, shipment_id)
    db.commit()
    db.refresh(row)
    return PickupCodeResponse(id=row.id, shipment_id=row.shipment_id, code=raw, expires_at=row.expires_at)
