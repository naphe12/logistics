from pydantic import BaseModel, Field
from uuid import UUID


class ShipmentCreate(BaseModel):
    sender_id: UUID | None = None
    sender_phone: str = Field(min_length=8, max_length=20)
    receiver_name: str = Field(min_length=2, max_length=180)
    receiver_phone: str = Field(min_length=8, max_length=20)
    origin: UUID | None = None
    destination: UUID | None = None


class ShipmentStatusUpdate(BaseModel):
    status: str
    relay_id: UUID | None = None
    event_type: str


class ShipmentOut(BaseModel):
    id: UUID
    shipment_no: str
    sender_phone: str | None = None
    receiver_name: str | None = None
    receiver_phone: str | None = None
    status: str | None = None

    class Config:
        from_attributes = True
