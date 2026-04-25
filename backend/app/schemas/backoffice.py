from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.enums import UserTypeEnum


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


class UssdKpisOut(BaseModel):
    window_hours: int
    total_requests: int
    unique_callers: int
    menu_hits: int
    send_flow_hits: int
    track_flow_hits: int
    pickup_flow_hits: int
    pay_flow_hits: int


class AuditLogOut(BaseModel):
    id: UUID
    entity: str | None = None
    action: str | None = None
    actor_user_id: UUID | None = None
    actor_phone: str | None = None
    ip_address: str | None = None
    request_id: str | None = None
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
    claims_auto_escalate_enabled: bool
    claims_auto_escalate_interval_seconds: int
    claims_auto_escalate_limit: int
    claims_auto_escalate_stale_hours: int
    outbox_worker_enabled: bool
    outbox_interval_seconds: int
    outbox_batch_size: int
    outbox_max_attempts: int
    last_run_at: str | None = None
    last_result: dict[str, int] | None = None
    last_error: str | None = None
    last_outbox_run_at: str | None = None
    last_outbox_result: dict[str, int] | None = None
    last_outbox_error: str | None = None
    outbox_status_counts: dict[str, int] | None = None
    last_ops_alert_run_at: str | None = None
    last_ops_alert_result: dict[str, Any] | None = None
    last_ops_alert_error: str | None = None
    last_claims_escalation_run_at: str | None = None
    last_claims_escalation_result: dict[str, Any] | None = None
    last_claims_escalation_error: str | None = None


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


class DelayRiskSmsNotifyResult(BaseModel):
    examined: int
    alerts_triggered: int
    recipients_targeted: int
    notifications_queued: int
    skipped_throttled: int
    delayed_hours: int
    throttle_hours: int


class BroadcastSmsRequest(BaseModel):
    message: str = Field(min_length=1, max_length=320)
    roles: list[UserTypeEnum] = Field(
        default_factory=lambda: [
            UserTypeEnum.admin,
            UserTypeEnum.hub,
            UserTypeEnum.agent,
        ]
    )
    dry_run: bool = False
    limit: int = Field(default=1000, ge=1, le=5000)
    respect_preferences: bool = True


class BroadcastSmsResult(BaseModel):
    scanned_users: int
    recipients_count: int
    notifications_queued: int
    skipped_no_phone: int
    skipped_render_errors: int
    dry_run: bool
    sample_phones: list[str] = Field(default_factory=list)
    sample_messages: list[str] = Field(default_factory=list)


class BroadcastSmsPreviewItem(BaseModel):
    phone: str
    role: UserTypeEnum
    rendered_message: str


class BroadcastSmsPreviewResult(BaseModel):
    scanned_users: int
    recipients_count: int
    skipped_no_phone: int
    skipped_render_errors: int
    items: list[BroadcastSmsPreviewItem] = Field(default_factory=list)


class ScheduleSmsCampaignRequest(BaseModel):
    message: str = Field(min_length=1, max_length=320)
    send_at: datetime
    roles: list[UserTypeEnum] = Field(
        default_factory=lambda: [
            UserTypeEnum.admin,
            UserTypeEnum.hub,
            UserTypeEnum.agent,
        ]
    )
    campaign_name: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=1000, ge=1, le=5000)
    respect_preferences: bool = True


class ScheduleSmsCampaignResult(BaseModel):
    campaign_id: str
    campaign_name: str | None = None
    send_at: datetime
    scanned_users: int
    recipients_count: int
    scheduled_count: int
    skipped_no_phone: int
    skipped_preferences: int
    skipped_render_errors: int


class ScheduledSmsCampaignOut(BaseModel):
    campaign_id: str
    campaign_name: str | None = None
    send_at: datetime
    recipients_count: int
    created_at: datetime | None = None


class CancelSmsCampaignResult(BaseModel):
    campaign_id: str
    cancelled_count: int


class ScheduledSmsCampaignRecipientOut(BaseModel):
    notification_id: UUID
    phone: str | None = None
    delivery_status: str | None = None
    attempts_count: int | None = None
    next_retry_at: datetime | None = None
    created_at: datetime | None = None


class ScheduledSmsCampaignDetailOut(BaseModel):
    campaign_id: str
    campaign_name: str | None = None
    send_at: datetime | None = None
    total: int
    queued: int
    cancelled: int
    items: list[ScheduledSmsCampaignRecipientOut] = Field(default_factory=list)


class RescheduleSmsCampaignResult(BaseModel):
    campaign_id: str
    send_at: datetime
    rescheduled_count: int


class SmsCampaignHistoryOut(BaseModel):
    campaign_id: str
    campaign_name: str | None = None
    total: int
    queued: int
    processing: int
    delivered: int
    failed: int
    dead: int
    cancelled: int
    skipped: int
    created_at: datetime | None = None
    last_activity_at: datetime | None = None


class BackofficeGlobalSearchItem(BaseModel):
    entity: str
    id: str
    label: str
    status: str | None = None
    created_at: datetime | None = None
    highlights: list[str] = Field(default_factory=list)


class BackofficeGlobalSearchResponse(BaseModel):
    q: str
    total: int
    by_entity: dict[str, int]
    items: list[BackofficeGlobalSearchItem]


class BackofficeTimeseriesPoint(BaseModel):
    day: str
    shipments_created: int
    payments_created: int
    incidents_created: int
    sms_sent: int
    sms_failed: int


class BackofficeTimeseriesOut(BaseModel):
    days: int
    points: list[BackofficeTimeseriesPoint]
