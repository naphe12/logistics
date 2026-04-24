from pydantic import BaseModel, Field
from uuid import UUID


class RelayBase(BaseModel):
    relay_code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=180)
    type: str = Field(min_length=2, max_length=30)
    opening_hours: str | None = Field(default=None, max_length=120)
    storage_capacity: int | None = Field(default=None, ge=0)
    is_active: bool = True


class RelayCreate(RelayBase):
    address_id: UUID | None = None


class RelayUpdate(BaseModel):
    relay_code: str | None = Field(default=None, min_length=2, max_length=30)
    name: str | None = Field(default=None, min_length=2, max_length=180)
    type: str | None = Field(default=None, min_length=2, max_length=30)
    opening_hours: str | None = Field(default=None, max_length=120)
    storage_capacity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    address_id: UUID | None = None


class RelayOut(BaseModel):
    id: UUID
    relay_code: str | None = None
    name: str | None = None
    type: str | None = None
    address_id: UUID | None = None
    opening_hours: str | None = None
    storage_capacity: int | None = None
    is_active: bool

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
