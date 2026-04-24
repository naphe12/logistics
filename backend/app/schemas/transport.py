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
