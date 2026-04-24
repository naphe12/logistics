from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID


class PaymentCreate(BaseModel):
    shipment_id: UUID
    amount: Decimal = Field(gt=0)
    payer_phone: str = Field(min_length=8, max_length=20)
    payment_stage: str = Field(pattern=r"^(at_send|at_delivery)$")
    provider: str = Field(min_length=2, max_length=30)


class PaymentInitiateRequest(BaseModel):
    external_ref: str | None = Field(default=None, max_length=80)


class PaymentFailRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=255)


class PaymentRefundRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=255)


class PaymentOut(BaseModel):
    id: UUID
    shipment_id: UUID | None = None
    amount: Decimal | None = None
    payer_phone: str | None = None
    payment_stage: str | None = None
    provider: str | None = None
    external_ref: str | None = None
    status: str | None = None
    failure_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class CommissionOut(BaseModel):
    id: UUID
    shipment_id: UUID | None = None
    payment_id: UUID | None = None
    commission_type: str | None = None
    beneficiary_kind: str | None = None
    beneficiary_id: UUID | None = None
    rate_pct: Decimal | None = None
    amount: Decimal | None = None
    status: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True
