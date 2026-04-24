from datetime import UTC, datetime, timedelta

import requests
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from app.config import (
    AFRICASTALKING_BASE_URL,
    SMS_API_KEY,
    SMS_MAX_RETRIES,
    SMS_PROVIDER,
    SMS_RETRY_BASE_SECONDS,
    SMS_SENDER_ID,
    SMS_USERNAME,
)
from app.database import SessionLocal
from app.models.notifications import Notification
from app.models.users import User
from app.enums import NotificationChannelEnum
from app.services.user_preferences_service import is_sms_allowed


class SMSProviderError(Exception):
    pass


def _now_utc() -> datetime:
    return datetime.now(UTC)


class SMSService:
    def send(self, to: str, message: str) -> dict:
        if SMS_PROVIDER == "log":
            return {"status": "mocked", "to": to, "message": message}

        if SMS_PROVIDER == "africastalking":
            headers = {
                "apiKey": SMS_API_KEY,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            data = {
                "username": SMS_USERNAME,
                "to": to,
                "message": message,
                "from": SMS_SENDER_ID,
            }
            response = requests.post(AFRICASTALKING_BASE_URL, headers=headers, data=data, timeout=20)
            if response.status_code >= 400:
                raise SMSProviderError(response.text)
            return response.json()

        raise SMSProviderError(f"Unsupported SMS_PROVIDER={SMS_PROVIDER}")


def _schedule_next_retry(notification: Notification) -> None:
    delay = SMS_RETRY_BASE_SECONDS * (2 ** max(0, notification.attempts_count - 1))
    notification.next_retry_at = _now_utc() + timedelta(seconds=delay)


def _attempt_notification_send(db: Session, notification: Notification) -> str:
    service = SMSService()
    notification.last_attempt_at = _now_utc()
    notification.attempts_count += 1
    notification.delivery_status = "processing"
    db.flush()

    try:
        service.send(to=notification.phone or "", message=notification.message or "")
        notification.delivery_status = "delivered"
        notification.error_message = None
        notification.next_retry_at = None
        return "delivered"
    except Exception as exc:
        notification.error_message = str(exc)[:2000]
        if notification.attempts_count >= notification.max_attempts:
            notification.delivery_status = "dead"
            notification.next_retry_at = None
            return "dead"
        notification.delivery_status = "failed"
        _schedule_next_retry(notification)
        return "failed"


def process_pending_sms(db: Session, *, limit: int = 100) -> dict[str, int]:
    now = _now_utc()
    candidates = (
        db.query(Notification)
        .filter(
            Notification.channel == NotificationChannelEnum.sms,
            Notification.delivery_status.in_(["queued", "failed"]),
            Notification.attempts_count < Notification.max_attempts,
            ((Notification.next_retry_at.is_(None)) | (Notification.next_retry_at <= now)),
        )
        .order_by(Notification.created_at.asc())
        .limit(limit)
        .all()
    )
    result = {"scanned": len(candidates), "delivered": 0, "failed": 0, "dead": 0}
    for notification in candidates:
        outcome = _attempt_notification_send(db, notification)
        result[outcome] += 1
    db.commit()
    return result


def _process_single_sms_background(notification_id) -> None:
    db = SessionLocal()
    try:
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            return
        if notification.delivery_status == "delivered":
            return
        _attempt_notification_send(db, notification)
        db.commit()
    finally:
        db.close()


def list_notifications_page(
    db: Session,
    *,
    phone: str | None = None,
    delivery_status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    offset = max(0, offset)
    limit = max(1, min(limit, 200))
    query = db.query(Notification)
    if phone:
        query = query.filter(Notification.phone == phone)
    if delivery_status:
        query = query.filter(Notification.delivery_status == delivery_status)
    total = query.count()
    items = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


def get_notification_stats(db: Session, *, phone: str | None = None) -> dict:
    query = db.query(Notification)
    if phone:
        query = query.filter(Notification.phone == phone)
    total = query.count()
    delivered = query.filter(Notification.delivery_status == "delivered").count()
    pending = query.filter(Notification.delivery_status.in_(["queued", "processing"])).count()
    failed = query.filter(Notification.delivery_status == "failed").count()
    dead = query.filter(Notification.delivery_status == "dead").count()
    return {
        "total": total,
        "delivered": delivered,
        "pending": pending,
        "failed": failed,
        "dead": dead,
    }


def retry_notification_send(db: Session, notification_id) -> Notification:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise ValueError("Notification not found")
    if notification.channel != NotificationChannelEnum.sms:
        raise ValueError("Only SMS notifications can be retried")
    if notification.delivery_status == "delivered":
        return notification
    if notification.attempts_count >= notification.max_attempts:
        notification.attempts_count = 0
    notification.delivery_status = "queued"
    notification.next_retry_at = _now_utc()
    notification.error_message = None
    _attempt_notification_send(db, notification)
    db.commit()
    db.refresh(notification)
    return notification


def retry_notifications_bulk(
    db: Session,
    *,
    statuses: list[str] | None = None,
    phone: str | None = None,
    limit: int = 200,
) -> dict[str, int]:
    allowed_statuses = {"failed", "dead", "queued"}
    selected_statuses = [status for status in (statuses or ["failed", "dead"]) if status in allowed_statuses]
    if not selected_statuses:
        return {"scanned": 0, "retried": 0, "delivered": 0, "failed": 0, "dead": 0}

    limit = max(1, min(limit, 1000))
    query = db.query(Notification).filter(
        Notification.channel == NotificationChannelEnum.sms,
        Notification.delivery_status.in_(selected_statuses),
    )
    if phone:
        query = query.filter(Notification.phone == phone)
    rows = query.order_by(Notification.created_at.asc()).limit(limit).all()

    result = {"scanned": len(rows), "retried": 0, "delivered": 0, "failed": 0, "dead": 0}
    for notification in rows:
        if notification.attempts_count >= notification.max_attempts:
            notification.attempts_count = 0
        notification.delivery_status = "queued"
        notification.next_retry_at = _now_utc()
        notification.error_message = None
        outcome = _attempt_notification_send(db, notification)
        result["retried"] += 1
        if outcome in result:
            result[outcome] += 1

    db.commit()
    return result


def queue_and_send_sms(
    db: Session,
    to: str,
    message: str,
    background_tasks: BackgroundTasks | None = None,
    respect_preferences: bool = True,
) -> Notification:
    now = _now_utc()
    user = db.query(User).filter(User.phone_e164 == to).first() if respect_preferences else None
    if respect_preferences and not is_sms_allowed(user):
        notification = Notification(
            phone=to,
            message=message,
            channel=NotificationChannelEnum.sms,
            delivery_status="skipped",
            error_message="Skipped due to user notification preferences",
            attempts_count=0,
            max_attempts=SMS_MAX_RETRIES,
            next_retry_at=None,
            last_attempt_at=None,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    notification = Notification(
        phone=to,
        message=message,
        channel=NotificationChannelEnum.sms,
        delivery_status="queued",
        attempts_count=0,
        max_attempts=SMS_MAX_RETRIES,
        next_retry_at=now,
        last_attempt_at=None,
    )
    db.add(notification)
    db.flush()

    if background_tasks is not None:
        db.commit()
        db.refresh(notification)
        background_tasks.add_task(_process_single_sms_background, notification.id)
    else:
        _attempt_notification_send(db, notification)
        db.commit()
        db.refresh(notification)
    return notification
