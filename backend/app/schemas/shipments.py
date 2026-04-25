from decimal import Decimal
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import date, datetime
from typing import Any, Literal


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


ShipmentScheduleFrequency = Literal["once", "daily", "weekly", "monthly"]


class ShipmentScheduleCreate(BaseModel):
    sender_id: UUID | None = None
    sender_phone: str = Field(min_length=8, max_length=20)
    receiver_name: str = Field(min_length=2, max_length=180)
    receiver_phone: str = Field(min_length=8, max_length=20)
    origin_relay_id: UUID | None = None
    destination_relay_id: UUID | None = None
    delivery_address_id: UUID | None = None
    delivery_note: str | None = Field(default=None, max_length=500)
    declared_value: Decimal | None = Field(default=None, ge=0)
    insurance_opt_in: bool = False
    extra: dict[str, Any] | None = None
    frequency: ShipmentScheduleFrequency = "once"
    interval_count: int = Field(default=1, ge=1, le=365)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    start_at: datetime
    end_at: datetime | None = None
    remaining_runs: int | None = Field(default=None, ge=1, le=10000)
    is_active: bool = True


class ShipmentScheduleUpdate(BaseModel):
    receiver_name: str | None = Field(default=None, min_length=2, max_length=180)
    receiver_phone: str | None = Field(default=None, min_length=8, max_length=20)
    origin_relay_id: UUID | None = None
    destination_relay_id: UUID | None = None
    delivery_address_id: UUID | None = None
    delivery_note: str | None = Field(default=None, max_length=500)
    declared_value: Decimal | None = Field(default=None, ge=0)
    insurance_opt_in: bool | None = None
    extra: dict[str, Any] | None = None
    frequency: ShipmentScheduleFrequency | None = None
    interval_count: int | None = Field(default=None, ge=1, le=365)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    start_at: datetime | None = None
    end_at: datetime | None = None
    remaining_runs: int | None = Field(default=None, ge=1, le=10000)
    is_active: bool | None = None
    recompute_next_run: bool = False


class ShipmentScheduleOut(BaseModel):
    id: UUID
    sender_id: UUID | None = None
    sender_phone: str | None = None
    receiver_name: str | None = None
    receiver_phone: str | None = None
    origin_relay_id: UUID | None = None
    destination_relay_id: UUID | None = None
    delivery_address_id: UUID | None = None
    delivery_note: str | None = None
    declared_value: Decimal | None = None
    insurance_opt_in: bool
    frequency: ShipmentScheduleFrequency
    interval_count: int
    day_of_week: int | None = None
    day_of_month: int | None = None
    start_at: datetime
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    end_at: datetime | None = None
    remaining_runs: int | None = None
    is_active: bool
    last_error: str | None = None
    extra: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ShipmentScheduleRunItem(BaseModel):
    schedule_id: UUID
    success: bool
    shipment_id: UUID | None = None
    error: str | None = None


class ShipmentScheduleRunResult(BaseModel):
    examined: int
    triggered: int
    failed: int
    items: list[ShipmentScheduleRunItem] = Field(default_factory=list)


class ShipmentScheduleListPage(BaseModel):
    items: list[ShipmentScheduleOut]
    total: int
    offset: int
    limit: int


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


class ShipmentClientSlaItem(BaseModel):
    shipment_id: UUID
    shipment_no: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    sla_state: str
    remaining_sla_hours: int
    open_incidents: int
    risk_reasons: list[str] = Field(default_factory=list)
    estimated_delivery_at: datetime


class ShipmentClientSlaPage(BaseModel):
    items: list[ShipmentClientSlaItem]
    total: int
    offset: int
    limit: int


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


class ShipmentPriceEstimateOut(BaseModel):
    origin_relay_id: UUID | None = None
    destination_relay_id: UUID | None = None
    corridor_code: str
    base_price_bif: Decimal
    fuel_surcharge_bif: Decimal
    congestion_surcharge_bif: Decimal
    insurance_fee_bif: Decimal
    total_estimated_bif: Decimal
    currency: str = "BIF"
    confidence: str
    historical_samples: int | None = None


class ShipmentPublicTrackRequest(BaseModel):
    shipment_no: str = Field(min_length=3, max_length=80)
    phone_e164: str = Field(min_length=8, max_length=20)
    access_code: str = Field(min_length=6, max_length=12)


class ShipmentPublicTrackOut(BaseModel):
    shipment_no_masked: str
    status: str | None = None
    receiver_name_masked: str | None = None
    estimated_delivery_at: datetime
    sla_state: str
    recent_timeline: list[ShipmentTimelineItem] = Field(default_factory=list)


class ShipmentPickupSlotUpdateRequest(BaseModel):
    starts_at: datetime
    ends_at: datetime
    note: str | None = Field(default=None, max_length=240)


class ShipmentPickupMarkRequest(BaseModel):
    relay_id: UUID | None = None
    event_type: str = Field(default="shipment_picked_up", min_length=2, max_length=60)
    extra: dict[str, Any] | None = None


class ShipmentRelayTransferRequest(BaseModel):
    from_relay_id: UUID
    to_relay_id: UUID
    event_type: str = Field(default="shipment_relay_transfer", min_length=2, max_length=60)
    extra: dict[str, Any] | None = None


class ShipmentDeliveryProofCreateRequest(BaseModel):
    receiver_name: str = Field(min_length=2, max_length=180)
    signature: str = Field(min_length=2, max_length=2000)
    geo_lat: float | None = None
    geo_lng: float | None = None


class RelayPickupForecastItem(BaseModel):
    slot_hour: datetime
    planned_pickups: int


class RelayPickupForecastOut(BaseModel):
    relay_id: UUID
    hours: int
    items: list[RelayPickupForecastItem] = Field(default_factory=list)
