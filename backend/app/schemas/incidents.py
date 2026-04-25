from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    shipment_id: UUID
    incident_type: str = Field(pattern=r"^(lost|damaged|delayed|claim)$")
    description: str = Field(min_length=4, max_length=4000)
    extra: dict[str, Any] | None = None


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
    extra: dict[str, Any] | None = None
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
    amount_requested: Decimal | None = Field(default=None, gt=0)
    amount: Decimal | None = Field(default=None, gt=0)
    claim_type: str | None = Field(default=None, pattern=r"^(lost|damaged|partial_loss|other)$")
    proof_urls: list[str] = Field(default_factory=list, max_length=10)
    reason: str = Field(min_length=2, max_length=4000)


class ClaimUpdateStatusRequest(BaseModel):
    status: str = Field(pattern=r"^(submitted|reviewing|approved|rejected|paid)$")
    amount_approved: Decimal | None = Field(default=None, ge=0)
    resolution_note: str | None = Field(default=None, max_length=4000)
    refunded_payment_id: UUID | None = None


class ClaimOut(BaseModel):
    id: UUID
    incident_id: UUID | None = None
    shipment_id: UUID | None = None
    amount: Decimal | None = None
    amount_requested: Decimal | None = None
    amount_approved: Decimal | None = None
    status: str | None = None
    claim_type: str | None = None
    proof_urls: list[str] | None = None
    reason: str | None = None
    resolution_note: str | None = None
    refunded_payment_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class IncidentExtraUpdate(BaseModel):
    extra: dict[str, Any]
    merge: bool = True


class IncidentDashboardOut(BaseModel):
    total: int
    open_count: int
    investigating_count: int
    resolved_count: int
    stale_open_count: int
    by_type: dict[str, int]


class IncidentTimelineItem(BaseModel):
    occurred_at: datetime
    kind: str
    status: str | None = None
    message: str | None = None
    incident_type: str | None = None
    extra: dict[str, Any] | None = None


class IncidentAutoEscalateResult(BaseModel):
    examined: int
    escalated: int
    skipped: int
    stale_hours: int
    dry_run: bool


class IncidentListPageOut(BaseModel):
    items: list[IncidentOut]
    total: int
    offset: int
    limit: int


class ClaimListPageOut(BaseModel):
    items: list[ClaimOut]
    total: int
    offset: int
    limit: int


class ClaimOpsStatsOut(BaseModel):
    total: int
    pending: int
    pending_over_sla: int
    stale_hours: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    requested_total: Decimal
    approved_total: Decimal
    paid_total: Decimal
    avg_resolution_hours: float | None = None
