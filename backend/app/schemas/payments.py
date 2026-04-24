from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID
from typing import Any


class PaymentCreate(BaseModel):
    shipment_id: UUID
    amount: Decimal = Field(gt=0)
    payer_phone: str = Field(min_length=8, max_length=20)
    payment_stage: str = Field(pattern=r"^(at_send|at_delivery)$")
    provider: str = Field(min_length=2, max_length=30)
    extra: dict[str, Any] | None = None


class PaymentInitiateRequest(BaseModel):
    external_ref: str | None = Field(default=None, max_length=80)


class PaymentFailRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=255)


class PaymentRefundRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=255)
    amount: Decimal | None = Field(default=None, gt=0)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=120)


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
    extra: dict[str, Any] | None = None
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


class PaymentExtraUpdate(BaseModel):
    extra: dict[str, Any]
    merge: bool = True


class PaymentWebhookPayload(BaseModel):
    event_id: str = Field(min_length=4, max_length=120)
    event_type: str = Field(min_length=2, max_length=60, default="payment_update")
    payment_id: UUID | None = None
    external_ref: str | None = Field(default=None, max_length=80)
    status: str = Field(min_length=2, max_length=40)
    reason: str | None = Field(default=None, max_length=255)
    provider: str | None = Field(default=None, max_length=30)
    payload: dict[str, Any] | None = None


class PaymentWebhookResult(BaseModel):
    accepted: bool
    applied: bool
    payment_id: UUID | None = None
    status: str | None = None
    detail: str


class PaymentReconcileResult(BaseModel):
    scanned: int
    updated: int
    failed_ids: list[UUID] = Field(default_factory=list)


class PaymentReceiptOut(BaseModel):
    receipt_no: str
    payment_id: UUID
    shipment_id: UUID | None = None
    external_ref: str | None = None
    provider: str | None = None
    payer_phone: str | None = None
    amount: Decimal | None = None
    status: str | None = None
    payment_stage: str | None = None
    paid_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    refunded_total: Decimal | None = None
    refundable_balance: Decimal | None = None
    commissions: list[CommissionOut] = Field(default_factory=list)
    refund_events: list[dict[str, Any]] = Field(default_factory=list)


class PaymentRefundPreviewOut(BaseModel):
    payment_id: UUID
    status: str | None = None
    total_amount: Decimal
    refunded_total: Decimal
    refundable_balance: Decimal
    is_fully_refunded: bool


class PaymentRefundEventOut(BaseModel):
    idempotency_key: str | None = None
    amount: Decimal
    reason: str
    refunded_at: datetime


class PaymentRefundHistoryOut(BaseModel):
    payment_id: UUID
    total_amount: Decimal
    refunded_total: Decimal
    refundable_balance: Decimal
    events: list[PaymentRefundEventOut] = Field(default_factory=list)


class PaymentInvoiceLineOut(BaseModel):
    payment_id: UUID
    shipment_id: UUID | None = None
    shipment_no: str | None = None
    payer_phone: str | None = None
    sender_phone: str | None = None
    external_ref: str | None = None
    provider: str | None = None
    status: str | None = None
    amount: Decimal
    refunded_total: Decimal
    net_amount: Decimal
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PaymentInvoiceSummaryOut(BaseModel):
    total_payments: int
    gross_amount: Decimal
    refunded_amount: Decimal
    net_amount: Decimal
    currency: str = "BIF"
    date_from: datetime | None = None
    date_to: datetime | None = None
    sender_phone: str | None = None
    sender_id: UUID | None = None


class PaymentInvoicePageOut(BaseModel):
    summary: PaymentInvoiceSummaryOut
    lines: list[PaymentInvoiceLineOut] = Field(default_factory=list)


class PaymentListPageOut(BaseModel):
    items: list[PaymentOut]
    total: int
    offset: int
    limit: int
