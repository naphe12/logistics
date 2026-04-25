from decimal import Decimal
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import date, datetime
from typing import Any


class ShipmentCreate(BaseModel):
    sender_id: UUID | None = None
    sender_phone: str = Field(min_length=8, max_length=20)
    receiver_name: str = Field(min_length=2, max_length=180)
    receiver_phone: str = Field(min_length=8, max_length=20)
    origin_relay_id: UUID | None = None
    destination_relay_id: UUID | None = None
    delivery_address_id: UUID | None = None
    delivery_note: str | None = Field(default=None, max_length=500)
    origin: UUID | None = None
    destination: UUID | None = None
    declared_value: Decimal | None = Field(default=None, ge=0)
    insurance_opt_in: bool = False
    extra: dict[str, Any] | None = None


class ShipmentStatusUpdate(BaseModel):
    status: str
    relay_id: UUID | None = None
    event_type: str
    extra: dict[str, Any] | None = None


class ShipmentEventCreate(BaseModel):
    event_type: str = Field(min_length=2, max_length=60)
    relay_id: UUID | None = None
    status: str | None = Field(default=None, min_length=2, max_length=40)
    extra: dict[str, Any] | None = None


class ShipmentBulkStatusItem(BaseModel):
    shipment_id: UUID
    status: str = Field(min_length=2, max_length=40)
    event_type: str = Field(min_length=2, max_length=60)
    relay_id: UUID | None = None
    extra: dict[str, Any] | None = None


class ShipmentBulkStatusUpdateRequest(BaseModel):
    items: list[ShipmentBulkStatusItem] = Field(min_length=1, max_length=200)
    continue_on_error: bool = True
    dry_run: bool = False


class ShipmentBulkStatusResultItem(BaseModel):
    shipment_id: UUID
    success: bool
    error: str | None = None


class ShipmentBulkStatusUpdateResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[ShipmentBulkStatusResultItem]


class ShipmentOut(BaseModel):
    id: UUID
    shipment_no: str
    sender_phone: str | None = None
    receiver_name: str | None = None
    receiver_phone: str | None = None
    origin_relay_id: UUID | None = None
    destination_relay_id: UUID | None = None
    delivery_address_id: UUID | None = None
    delivery_note: str | None = None
    status: str | None = None
    declared_value: Decimal | None = None
    insurance_fee: Decimal | None = None
    coverage_amount: Decimal | None = None
    extra: dict[str, Any] | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ShipmentEventOut(BaseModel):
    id: UUID
    shipment_id: UUID
    relay_id: UUID | None = None
    event_type: str | None = None
    extra: dict[str, Any] | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ShipmentOverviewStats(BaseModel):
    total: int
    created_last_24h: int
    created_last_7d: int
    by_status: dict[str, int]


class ShipmentTimeseriesPoint(BaseModel):
    day: date
    created_count: int


class ShipmentTimeseriesStats(BaseModel):
    days: int
    total_created: int
    points: list[ShipmentTimeseriesPoint]


class ShipmentListPage(BaseModel):
    items: list[ShipmentOut]
    total: int
    offset: int
    limit: int


class ShipmentStatusOut(BaseModel):
    code: str
    label: str | None = None

    class Config:
        from_attributes = True


class ShipmentEtaOut(BaseModel):
    class ShipmentEtaFactor(BaseModel):
        code: str
        label: str
        hours: int

    shipment_id: UUID
    shipment_no: str | None = None
    status: str | None = None
    estimated_delivery_at: datetime
    remaining_hours: int
    base_remaining_hours: int | None = None
    penalty_hours: int = 0
    confidence: str
    basis: str
    factors: list[ShipmentEtaFactor] = Field(default_factory=list)
    historical_samples: int | None = None
    historical_median_hours: int | None = None


class ShipmentExtraUpdate(BaseModel):
    extra: dict[str, Any]
    merge: bool = True


class ShipmentTimelineItem(BaseModel):
    occurred_at: datetime
    kind: str
    code: str
    status: str | None = None
    message: str | None = None
    relay_id: UUID | None = None
    incident_id: UUID | None = None
    extra: dict[str, Any] | None = None


class ShipmentTrackingSummaryOut(BaseModel):
    shipment_id: UUID
    shipment_no: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    last_event_at: datetime | None = None
    elapsed_hours: int
    target_sla_hours: int
    remaining_sla_hours: int
    sla_state: str
    open_incidents: int
    stagnation_hours: int
    risk_reasons: list[str] = Field(default_factory=list)
    estimated_delivery_at: datetime
    eta_basis: str


class ShipmentSlaRiskPage(BaseModel):
    items: list[ShipmentTrackingSummaryOut]
    total: int
    limit: int


class ShipmentAutoDetectStagnationResult(BaseModel):
    examined: int
    created: int
    skipped_existing: int


class MyShipmentsDashboardOut(BaseModel):
    total: int
    sent: int
    received: int
    in_progress: int
    delivered: int
    delayed_risk: int
    last_30d_created: int


class ShipmentInsuranceQuoteOut(BaseModel):
    declared_value: Decimal
    insurance_opt_in: bool
    premium_rate: Decimal
    insurance_fee: Decimal
    coverage_amount: Decimal
    max_coverage: Decimal


class ShipmentInsurancePolicyOut(BaseModel):
    enabled: bool
    premium_rate: Decimal
    max_coverage_bif: Decimal
    claim_window_hours: int
    claim_review_sla_hours: int
    loss_coverage_rate: Decimal
    damage_coverage_rate: Decimal
    require_proof: bool
    prohibited_items: list[str]
