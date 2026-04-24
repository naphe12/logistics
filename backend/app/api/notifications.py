from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.enums import UserTypeEnum
from app.models.users import User
from app.schemas.notifications import (
    NotificationBulkRetryResultOut,
    NotificationListPageOut,
    NotificationOut,
    NotificationStatsOut,
)
from app.services.notification_service import (
    get_notification_stats,
    list_notifications_page,
    retry_notifications_bulk,
    retry_notification_send,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/my", response_model=NotificationListPageOut)
def list_my_notifications_endpoint(
    delivery_status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    return list_notifications_page(
        db,
        phone=current_user.phone_e164,
        delivery_status=delivery_status,
        offset=offset,
        limit=limit,
    )


@router.get("/my/stats", response_model=NotificationStatsOut)
def my_notifications_stats_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserTypeEnum.customer,
            UserTypeEnum.business,
            UserTypeEnum.agent,
            UserTypeEnum.driver,
            UserTypeEnum.hub,
            UserTypeEnum.admin,
        )
    ),
):
    return get_notification_stats(db, phone=current_user.phone_e164)


@router.get("", response_model=NotificationListPageOut)
def list_notifications_endpoint(
    phone: str | None = Query(default=None),
    delivery_status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    return list_notifications_page(
        db,
        phone=phone,
        delivery_status=delivery_status,
        offset=offset,
        limit=limit,
    )


@router.post("/{notification_id}/retry", response_model=NotificationOut)
def retry_notification_endpoint(
    notification_id: UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    try:
        return retry_notification_send(db, notification_id)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=422, detail=message) from exc


@router.post("/retry-bulk", response_model=NotificationBulkRetryResultOut)
def retry_notifications_bulk_endpoint(
    statuses: list[str] | None = Query(default=None),
    phone: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub, UserTypeEnum.agent)),
):
    return retry_notifications_bulk(
        db,
        statuses=statuses,
        phone=phone,
        limit=limit,
    )
