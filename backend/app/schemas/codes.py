from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class PickupCodeResponse(BaseModel):
    id: UUID
    shipment_id: UUID
    code: str
    expires_at: datetime
