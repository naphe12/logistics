from decimal import Decimal
from pydantic import BaseModel
from uuid import UUID


class PaymentCreate(BaseModel):
    shipment_id: UUID
    amount: Decimal


class PaymentOut(BaseModel):
    id: UUID
    shipment_id: UUID | None = None
    amount: Decimal | None = None
    status: str | None = None

    class Config:
        from_attributes = True
