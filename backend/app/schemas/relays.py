from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class RelayBase(BaseModel):
    relay_code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=180)
    type: str = Field(min_length=2, max_length=30)
    opening_hours: str | None = Field(default=None, max_length=120)
    storage_capacity: int | None = Field(default=None, ge=0)
    is_active: bool = True


class RelayCreate(RelayBase):
    province_id: UUID | None = None
    commune_id: UUID | None = None
    address_id: UUID | None = None


class RelayUpdate(BaseModel):
    relay_code: str | None = Field(default=None, min_length=2, max_length=30)
    name: str | None = Field(default=None, min_length=2, max_length=180)
    type: str | None = Field(default=None, min_length=2, max_length=30)
    opening_hours: str | None = Field(default=None, max_length=120)
    storage_capacity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    province_id: UUID | None = None
    commune_id: UUID | None = None
    address_id: UUID | None = None


class RelayOut(BaseModel):
    id: UUID
    relay_code: str | None = None
    name: str | None = None
    type: str | None = None
    province_id: UUID | None = None
    commune_id: UUID | None = None
    address_id: UUID | None = None
    opening_hours: str | None = None
    storage_capacity: int | None = None
    is_active: bool
    current_present: int | None = None
    available: int | None = None
    utilization_ratio: float | None = None
    operational_status: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    quartier: str | None = None
    commune_name: str | None = None
    province_name: str | None = None
    landmark: str | None = None
    manager_phone: str | None = None

    class Config:
        from_attributes = True


class RelayManagerApplicationCreate(BaseModel):
    relay_id: UUID | None = None
    manager_name: str = Field(min_length=2, max_length=180)
    manager_phone: str = Field(min_length=8, max_length=20)
    manager_email: str | None = Field(default=None, max_length=180)
    notes: str | None = None


class RelayManagerApplicationReview(BaseModel):
    status: str = Field(pattern="^(pending|validated|rejected|training_in_progress|trained)$")
    training_completed: bool = False
    notes: str | None = None


class RelayManagerApplicationOut(BaseModel):
    id: UUID
    relay_id: UUID | None = None
    manager_name: str
    manager_phone: str
    manager_email: str | None = None
    notes: str | None = None
    status: str
    training_completed: bool
    created_by_user_id: UUID | None = None
    reviewed_by_user_id: UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class RelayInventoryUpsert(BaseModel):
    shipment_id: UUID
    present: bool = True


class RelayInventoryOut(BaseModel):
    id: UUID
    relay_id: UUID | None = None
    shipment_id: UUID | None = None
    present: bool
    shipment_no: str | None = None
    shipment_status: str | None = None


class RelayCapacityOut(BaseModel):
    relay_id: UUID
    storage_capacity: int | None = None
    current_present: int
    available: int | None = None
    is_full: bool
    utilization_ratio: float | None = None
