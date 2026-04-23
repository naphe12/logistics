import requests
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from app.config import SMS_PROVIDER, SMS_API_KEY, SMS_USERNAME, SMS_SENDER_ID, AFRICASTALKING_BASE_URL
from app.models.notifications import Notification
from app.enums import NotificationChannelEnum


class SMSProviderError(Exception):
    pass


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


def _send_sms_background(to: str, message: str) -> None:
    service = SMSService()
    service.send(to=to, message=message)


def queue_and_send_sms(
    db: Session,
    to: str,
    message: str,
    background_tasks: BackgroundTasks | None = None,
) -> Notification:
    notification = Notification(phone=to, message=message, channel=NotificationChannelEnum.sms)
    db.add(notification)
    db.flush()

    if background_tasks is not None:
        background_tasks.add_task(_send_sms_background, to, message)
    else:
        service = SMSService()
        service.send(to=to, message=message)

    db.commit()
    db.refresh(notification)
    return notification
