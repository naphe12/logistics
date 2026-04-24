from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from typing import Any

from app.schemas.shipments import ShipmentOut


class TripCreate(BaseModel):
    route_id: UUID | None = None
    vehicle_id: UUID | None = None
    status: str = Field(default="planned", min_length=2, max_length=20)
    extra: dict[str, Any] | None = None


class TripUpdate(BaseModel):
    route_id: UUID | None = None
    vehicle_id: UUID | None = None
    status: str | None = Field(default=None, min_length=2, max_length=20)
    extra: dict[str, Any] | None = None


class TripOut(BaseModel):
    id: UUID
    route_id: UUID | None = None
    vehicle_id: UUID | None = None
    status: str | None = None
    extra: dict[str, Any] | None = None

    class Config:
        from_attributes = True


class ManifestOut(BaseModel):
    id: UUID
    trip_id: UUID | None = None

    class Config:
        from_attributes = True


class ManifestShipmentAddRequest(BaseModel):
    shipment_id: UUID


class ManifestShipmentOut(BaseModel):
    id: UUID
    manifest_id: UUID | None = None
    shipment_id: UUID | None = None

    class Config:
        from_attributes = True


class TripManifestView(BaseModel):
    trip: TripOut
    manifest: ManifestOut
    shipments: list[ShipmentOut]


class TripScanRequest(BaseModel):
    relay_id: UUID | None = None
    event_type: str | None = Field(default=None, min_length=2, max_length=60)


class TripScanResponse(BaseModel):
    trip_id: UUID
    status: str | None = None
    updated_shipments: int
    scanned_at: datetime


class GroupingShipmentCandidate(BaseModel):
    shipment_id: UUID
    shipment_no: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    origin: UUID | None = None
    destination: UUID | None = None


class GroupingSuggestion(BaseModel):
    key: str
    origin: UUID | None = None
    destination: UUID | None = None
    candidate_count: int
    shipments: list[GroupingShipmentCandidate]


class GroupingSuggestionResponse(BaseModel):
    generated_at: datetime
    max_group_size: int
    total_candidates: int
    total_groups: int
    suggestions: list[GroupingSuggestion]


class PriorityShipmentCandidate(BaseModel):
    shipment_id: UUID
    shipment_no: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    origin: UUID | None = None
    destination: UUID | None = None
    priority_score: int
    reasons: list[str] = Field(default_factory=list)


class PrioritySuggestionResponse(BaseModel):
    generated_at: datetime
    total_candidates: int
    max_results: int
    suggestions: list[PriorityShipmentCandidate]


class TripAutoAssignPriorityRequest(BaseModel):
    target_manifest_size: int = Field(default=20, ge=1, le=500)
    max_add: int = Field(default=10, ge=1, le=200)
    candidate_limit: int = Field(default=500, ge=1, le=1000)
    vehicle_capacity: int | None = Field(default=None, ge=1, le=1000)


class TripAutoAssignPriorityItem(BaseModel):
    shipment_id: UUID
    shipment_no: str | None = None
    priority_score: int
    reasons: list[str] = Field(default_factory=list)


class TripAutoAssignPriorityResponse(BaseModel):
    trip_id: UUID
    manifest_id: UUID
    before_count: int
    after_count: int
    target_manifest_size: int
    requested_max_add: int
    added_count: int
    rejected_count: int
    total_priority_candidates: int
    added: list[TripAutoAssignPriorityItem] = Field(default_factory=list)
    rejected: list[TripAutoAssignPriorityItem] = Field(default_factory=list)


class TripExtraUpdate(BaseModel):
    extra: dict[str, Any]
    merge: bool = True


class TripOpsSummaryOut(BaseModel):
    trip_id: UUID
    manifest_id: UUID | None = None
    status: str | None = None
    vehicle_capacity: int
    manifest_count: int
    load_ratio: float
    blocked_count: int
    critical_incident_count: int
    at_risk_count: int
    status_breakdown: dict[str, int] = Field(default_factory=dict)
    blocked_shipment_ids: list[UUID] = Field(default_factory=list)


class TripIncidentReplanRequest(BaseModel):
    max_replace: int = Field(default=5, ge=1, le=200)
    candidate_limit: int = Field(default=500, ge=1, le=1000)
    vehicle_capacity: int | None = Field(default=None, ge=1, le=1000)
    dry_run: bool = False


class TripIncidentReplanItem(BaseModel):
    shipment_id: UUID
    shipment_no: str | None = None
    reasons: list[str] = Field(default_factory=list)


class TripIncidentReplanResponse(BaseModel):
    trip_id: UUID
    manifest_id: UUID
    before_count: int
    after_count: int
    removed_count: int
    added_count: int
    dry_run: bool
    removed: list[TripIncidentReplanItem] = Field(default_factory=list)
    added: list[TripAutoAssignPriorityItem] = Field(default_factory=list)
