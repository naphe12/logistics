from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class MetricItem(BaseModel):
    key: str
    value: int


class BackofficeOverview(BaseModel):
    shipments_total: int
    shipments_today: int
    payments_total: int
    payments_failed_24h: int
    incidents_open: int
    incidents_total: int
    notifications_failed_24h: int
    notifications_pending: int
    notifications_dead: int
    ussd_requests_24h: int
    trips_in_progress: int
    auto_assign_accepted_24h: int
    auto_assign_rejected_24h: int
    auto_assign_total_24h: int
    auto_assign_acceptance_rate_24h: int
    shipment_status_breakdown: list[MetricItem]


class SmsLogOut(BaseModel):
    id: UUID
    phone: str | None = None
    message: str | None = None
    delivery_status: str | None = None
    error_message: str | None = None
    attempts_count: int | None = None
    max_attempts: int | None = None
    next_retry_at: datetime | None = None
    last_attempt_at: datetime | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class UssdLogOut(BaseModel):
    id: UUID
    session_id: UUID | None = None
    payload: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: UUID
    entity: str | None = None
    action: str | None = None
    actor_user_id: UUID | None = None
    actor_phone: str | None = None
    ip_address: str | None = None
    endpoint: str | None = None
    method: str | None = None
    status_code: int | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class ErrorLogOut(BaseModel):
    source: str
    record: dict[str, Any]


class SmsDispatchResult(BaseModel):
    scanned: int
    delivered: int
    failed: int
    dead: int


class SmsWorkerStatusOut(BaseModel):
    running: bool
    enabled: bool
    interval_seconds: int
    batch_size: int
    leader_lock_enabled: bool
    leader_lock_key: int
    leader_acquired: bool
    leader_mode: str
    ops_alert_autonotify_enabled: bool
    ops_alert_interval_seconds: int
    ops_alert_max_per_hour: int
    last_run_at: str | None = None
    last_result: dict[str, int] | None = None
    last_error: str | None = None
    last_ops_alert_run_at: str | None = None
    last_ops_alert_result: dict[str, Any] | None = None
    last_ops_alert_error: str | None = None


class BackofficeAlertOut(BaseModel):
    code: str
    severity: str
    title: str
    details: str
    context: dict[str, Any]


class AutoDetectIncidentsResult(BaseModel):
    examined: int
    created: int
    skipped_existing: int
    delayed_hours: int


class CriticalAlertsSmsNotifyResult(BaseModel):
    alerts_considered: int
    critical_count: int
    recipients_count: int
    sent_count: int
    skipped_reason: str | None = None
    throttle_minutes: int
    max_per_hour: int
