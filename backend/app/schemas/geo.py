from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ProvinceOut(BaseModel):
    id: UUID
    name: str

    class Config:
        from_attributes = True


class ProvinceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class CommuneOut(BaseModel):
    id: UUID
    province_id: UUID
    name: str

    class Config:
        from_attributes = True


class CommuneCreate(BaseModel):
    province_id: UUID
    name: str = Field(min_length=2, max_length=120)


class CommuneBulkItem(BaseModel):
    province_name: str = Field(min_length=2, max_length=120)
    commune_name: str = Field(min_length=2, max_length=120)


class CommuneBulkUpsertRequest(BaseModel):
    items: list[CommuneBulkItem] = Field(min_length=1, max_length=2000)


class CommuneBulkUpsertResult(BaseModel):
    scanned: int
    created: int
    updated: int
    skipped_missing_province: int


class AddressCreate(BaseModel):
    province_id: UUID
    commune_id: UUID
    zone: str | None = Field(default=None, max_length=120)
    colline: str | None = Field(default=None, max_length=120)
    quartier: str | None = Field(default=None, max_length=120)
    landmark: str | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    raw_input: str | None = None
    address_line: str | None = None


class AddressOut(BaseModel):
    id: UUID
    province_id: UUID | None = None
    commune_id: UUID | None = None
    province: str | None = None
    commune: str | None = None
    zone: str | None = None
    colline: str | None = None
    quartier: str | None = None
    landmark: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    raw_input: str | None = None
    address_line: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True
