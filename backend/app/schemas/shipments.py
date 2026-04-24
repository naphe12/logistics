from pydantic import BaseModel, Field
from uuid import UUID
from datetime import date, datetime


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


class ShipmentEventCreate(BaseModel):
    event_type: str = Field(min_length=2, max_length=60)
    relay_id: UUID | None = None
    status: str | None = Field(default=None, min_length=2, max_length=40)


class ShipmentBulkStatusItem(BaseModel):
    shipment_id: UUID
    status: str = Field(min_length=2, max_length=40)
    event_type: str = Field(min_length=2, max_length=60)
    relay_id: UUID | None = None


class ShipmentBulkStatusUpdateRequest(BaseModel):
    items: list[ShipmentBulkStatusItem] = Field(min_length=1, max_length=200)
    continue_on_error: bool = True


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
    status: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ShipmentEventOut(BaseModel):
    id: UUID
    shipment_id: UUID
    relay_id: UUID | None = None
    event_type: str | None = None
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
