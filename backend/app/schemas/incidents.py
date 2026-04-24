from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    shipment_id: UUID
    incident_type: str = Field(pattern=r"^(lost|damaged|delayed|claim)$")
    description: str = Field(min_length=4, max_length=4000)


class IncidentUpdateStatusRequest(BaseModel):
    status: str = Field(min_length=2, max_length=40)


class IncidentAddUpdateRequest(BaseModel):
    message: str = Field(min_length=2, max_length=4000)


class IncidentOut(BaseModel):
    id: UUID
    shipment_id: UUID | None = None
    incident_type: str | None = None
    description: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class IncidentUpdateOut(BaseModel):
    id: UUID
    incident_id: UUID | None = None
    message: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class ClaimCreate(BaseModel):
    incident_id: UUID
    shipment_id: UUID
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=2, max_length=4000)


class ClaimUpdateStatusRequest(BaseModel):
    status: str = Field(pattern=r"^(submitted|reviewing|approved|rejected|paid)$")
    resolution_note: str | None = Field(default=None, max_length=4000)
    refunded_payment_id: UUID | None = None


class ClaimOut(BaseModel):
    id: UUID
    incident_id: UUID | None = None
    shipment_id: UUID | None = None
    amount: Decimal | None = None
    status: str | None = None
    reason: str | None = None
    resolution_note: str | None = None
    refunded_payment_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
