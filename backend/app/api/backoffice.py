from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.enums import UserTypeEnum
from app.schemas.backoffice import (
    AutoDetectIncidentsResult,
    AuditLogOut,
    BackofficeAlertOut,
    BackofficeGlobalSearchResponse,
    BackofficeOverview,
    BackofficeTimeseriesOut,
    BroadcastSmsPreviewResult,
    BroadcastSmsRequest,
    BroadcastSmsResult,
    CancelSmsCampaignResult,
    DelayRiskSmsNotifyResult,
    ScheduleSmsCampaignRequest,
    ScheduleSmsCampaignResult,
    ScheduledSmsCampaignOut,
    ScheduledSmsCampaignDetailOut,
    RescheduleSmsCampaignResult,
    SmsCampaignHistoryOut,
    CriticalAlertsSmsNotifyResult,
    ErrorLogOut,
    SmsDispatchResult,
    SmsLogOut,
    UssdKpisOut,
    SmsWorkerStatusOut,
    UssdLogOut,
)
from app.services.backoffice_service import (
    broadcast_sms_to_roles,
    get_backoffice_overview,
    list_operational_alerts,
    list_audit_logs,
    list_recent_errors,
    list_sms_logs,
    list_ussd_logs,
    get_ussd_kpis,
    notify_critical_alerts_sms,
    notify_delay_risk_customers_sms,
    preview_broadcast_sms_to_roles,
    schedule_sms_campaign_to_roles,
    list_scheduled_sms_campaigns,
    cancel_scheduled_sms_campaign,
    get_scheduled_sms_campaign,
    reschedule_sms_campaign,
    list_sms_campaign_history,
    auto_detect_delay_incidents,
    global_search,
    get_backoffice_timeseries,
)
from app.services.notification_service import process_pending_sms
from app.services.sms_worker_service import get_sms_queue_worker_status

router = APIRouter(prefix="/backoffice", tags=["backoffice"])


@router.get("/overview", response_model=BackofficeOverview)
def backoffice_overview_endpoint(
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return get_backoffice_overview(db)


@router.get("/stats/timeseries", response_model=BackofficeTimeseriesOut)
def backoffice_timeseries_endpoint(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return get_backoffice_timeseries(db, days=days)


@router.get("/logs/sms", response_model=list[SmsLogOut])
def sms_logs_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return list_sms_logs(db, limit=limit)


@router.get("/logs/ussd", response_model=list[UssdLogOut])
def ussd_logs_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return list_ussd_logs(db, limit=limit)


@router.get("/kpis/ussd", response_model=UssdKpisOut)
def ussd_kpis_endpoint(
    window_hours: int = Query(default=24, ge=1, le=720),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return get_ussd_kpis(db, window_hours=window_hours)


@router.get("/logs/audit", response_model=list[AuditLogOut])
def audit_logs_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return list_audit_logs(db, limit=limit)


@router.get("/errors/recent", response_model=list[ErrorLogOut])
def recent_errors_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return list_recent_errors(db, limit=limit)


@router.get("/search/global", response_model=BackofficeGlobalSearchResponse)
def global_search_endpoint(
    q: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    return global_search(db, q=q, limit=limit)


@router.post("/sms/dispatch", response_model=SmsDispatchResult)
def dispatch_sms_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return process_pending_sms(db, limit=limit)


@router.post("/sms/broadcast", response_model=BroadcastSmsResult)
def broadcast_sms_endpoint(
    payload: BroadcastSmsRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return broadcast_sms_to_roles(
        db,
        message=payload.message,
        roles=payload.roles,
        dry_run=payload.dry_run,
        limit=payload.limit,
        respect_preferences=payload.respect_preferences,
    )


@router.post("/sms/broadcast/preview", response_model=BroadcastSmsPreviewResult)
def preview_broadcast_sms_endpoint(
    payload: BroadcastSmsRequest,
    preview_limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return preview_broadcast_sms_to_roles(
        db,
        message=payload.message,
        roles=payload.roles,
        limit=payload.limit,
        preview_limit=preview_limit,
    )


@router.post("/sms/campaigns/schedule", response_model=ScheduleSmsCampaignResult)
def schedule_sms_campaign_endpoint(
    payload: ScheduleSmsCampaignRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    try:
        return schedule_sms_campaign_to_roles(
            db,
            message=payload.message,
            send_at=payload.send_at,
            roles=payload.roles,
            campaign_name=payload.campaign_name,
            limit=payload.limit,
            respect_preferences=payload.respect_preferences,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sms/campaigns/scheduled", response_model=list[ScheduledSmsCampaignOut])
def list_scheduled_sms_campaigns_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return list_scheduled_sms_campaigns(db, limit=limit)


@router.post("/sms/campaigns/{campaign_id}/cancel", response_model=CancelSmsCampaignResult)
def cancel_scheduled_sms_campaign_endpoint(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return cancel_scheduled_sms_campaign(db, campaign_id=campaign_id)


@router.get("/sms/campaigns/{campaign_id}", response_model=ScheduledSmsCampaignDetailOut)
def get_scheduled_sms_campaign_endpoint(
    campaign_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    try:
        return get_scheduled_sms_campaign(db, campaign_id=campaign_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sms/campaigns/{campaign_id}/reschedule", response_model=RescheduleSmsCampaignResult)
def reschedule_sms_campaign_endpoint(
    campaign_id: str,
    send_at: datetime = Query(...),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    try:
        return reschedule_sms_campaign(db, campaign_id=campaign_id, send_at=send_at)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sms/campaigns/history", response_model=list[SmsCampaignHistoryOut])
def list_sms_campaign_history_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return list_sms_campaign_history(db, limit=limit)


@router.get("/sms/worker/status", response_model=SmsWorkerStatusOut)
def sms_worker_status_endpoint(
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return get_sms_queue_worker_status()


@router.get("/alerts", response_model=list[BackofficeAlertOut])
def operational_alerts_endpoint(
    delayed_hours: int = Query(default=48, ge=1, le=720),
    relay_utilization_warn: float = Query(default=0.9, ge=0.0, le=1.0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return list_operational_alerts(
        db,
        delayed_hours=delayed_hours,
        relay_utilization_warn=relay_utilization_warn,
        limit=limit,
    )


@router.post("/incidents/auto-detect", response_model=AutoDetectIncidentsResult)
def auto_detect_incidents_endpoint(
    delayed_hours: int = Query(default=48, ge=1, le=720),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    try:
        return auto_detect_delay_incidents(db, delayed_hours=delayed_hours, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/alerts/notify-critical", response_model=CriticalAlertsSmsNotifyResult)
def notify_critical_alerts_endpoint(
    delayed_hours: int = Query(default=48, ge=1, le=720),
    relay_utilization_warn: float = Query(default=0.9, ge=0.0, le=1.0),
    throttle_minutes: int = Query(default=30, ge=1, le=1440),
    max_recipients: int = Query(default=20, ge=1, le=200),
    max_per_hour: int = Query(default=4, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return notify_critical_alerts_sms(
        db,
        delayed_hours=delayed_hours,
        relay_utilization_warn=relay_utilization_warn,
        throttle_minutes=throttle_minutes,
        max_recipients=max_recipients,
        max_per_hour=max_per_hour,
    )


@router.post("/alerts/notify-delay-risk-customers", response_model=DelayRiskSmsNotifyResult)
def notify_delay_risk_customers_endpoint(
    delayed_hours: int = Query(default=48, ge=1, le=720),
    limit: int = Query(default=200, ge=1, le=1000),
    throttle_hours: int = Query(default=12, ge=1, le=336),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return notify_delay_risk_customers_sms(
        db,
        delayed_hours=delayed_hours,
        limit=limit,
        throttle_hours=throttle_hours,
    )
