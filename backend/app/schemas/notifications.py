from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: UUID
    phone: str | None = None
    message: str | None = None
    channel: str | None = None
    delivery_status: str | None = None
    error_message: str | None = None
    attempts_count: int | None = None
    max_attempts: int | None = None
    next_retry_at: datetime | None = None
    last_attempt_at: datetime | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class NotificationListPageOut(BaseModel):
    items: list[NotificationOut]
    total: int
    offset: int
    limit: int


class NotificationStatsOut(BaseModel):
    total: int
    delivered: int
    pending: int
    failed: int
    dead: int


class NotificationBulkRetryResultOut(BaseModel):
    scanned: int
    retried: int
    delivered: int
    failed: int
    dead: int
