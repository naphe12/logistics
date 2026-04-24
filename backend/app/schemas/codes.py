from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class PickupCodeResponse(BaseModel):
    id: UUID
    shipment_id: UUID
    code: str
    expires_at: datetime


class PickupCodeValidationRequest(BaseModel):
    code: str


class PickupCodeValidationResponse(BaseModel):
    shipment_id: UUID
    valid: bool
    message: str
    error_code: str | None = None


class PickupCodeConfirmRequest(BaseModel):
    code: str
    relay_id: UUID | None = None
    event_type: str | None = "shipment_delivered_to_receiver"


class PickupCodeConfirmResponse(BaseModel):
    shipment_id: UUID
    confirmed: bool
    status: str | None = None
    message: str
    error_code: str | None = None
