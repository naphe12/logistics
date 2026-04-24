from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ShipmentSyncItem(BaseModel):
    id: UUID
    shipment_no: str
    status: str | None = None
    sender_phone: str | None = None
    receiver_name: str | None = None
    receiver_phone: str | None = None
    created_at: datetime
    updated_at: datetime
    server_version: datetime

    class Config:
        from_attributes = True


class ShipmentSyncPullResponse(BaseModel):
    server_time: datetime
    count: int
    next_cursor: datetime | None = None
    items: list[ShipmentSyncItem]


class SyncPushActionIn(BaseModel):
    client_action_id: str
    action_type: str
    method: str
    path: str
    payload: dict
    client_version: datetime | None = None
    conflict_policy: str | None = None


class SyncPushRequest(BaseModel):
    actions: list[SyncPushActionIn]


class SyncPushActionResult(BaseModel):
    client_action_id: str
    status: str
    error: str | None = None
    data: dict | None = None


class SyncPushResponse(BaseModel):
    server_time: datetime
    accepted: int
    succeeded: int
    failed: int
    results: list[SyncPushActionResult]
