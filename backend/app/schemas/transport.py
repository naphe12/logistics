from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.shipments import ShipmentOut


class TripCreate(BaseModel):
    route_id: UUID | None = None
    vehicle_id: UUID | None = None
    status: str = Field(default="planned", min_length=2, max_length=20)


class TripUpdate(BaseModel):
    route_id: UUID | None = None
    vehicle_id: UUID | None = None
    status: str | None = Field(default=None, min_length=2, max_length=20)


class TripOut(BaseModel):
    id: UUID
    route_id: UUID | None = None
    vehicle_id: UUID | None = None
    status: str | None = None

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
