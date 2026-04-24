from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.enums import UserTypeEnum
from app.schemas.backoffice import (
    AutoDetectIncidentsResult,
    AuditLogOut,
    BackofficeAlertOut,
    BackofficeOverview,
    CriticalAlertsSmsNotifyResult,
    ErrorLogOut,
    SmsDispatchResult,
    SmsLogOut,
    SmsWorkerStatusOut,
    UssdLogOut,
)
from app.services.backoffice_service import (
    get_backoffice_overview,
    list_operational_alerts,
    list_audit_logs,
    list_recent_errors,
    list_sms_logs,
    list_ussd_logs,
    notify_critical_alerts_sms,
    auto_detect_delay_incidents,
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


@router.post("/sms/dispatch", response_model=SmsDispatchResult)
def dispatch_sms_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return process_pending_sms(db, limit=limit)


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
