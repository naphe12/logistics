import hashlib
import math
import secrets
from datetime import datetime, timedelta, UTC

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.config import (
    OTP_EXPIRE_MINUTES,
    OTP_MAX_ATTEMPTS,
    OTP_LOCK_MINUTES,
    OTP_REQUEST_WINDOW_SECONDS,
    OTP_REQUEST_MAX_PER_WINDOW,
)
from app.enums import UserTypeEnum
from app.models.ussd import OTPCode
from app.models.users import User
from app.security import create_access_token, create_refresh_token, get_refresh_subject
from app.services.notification_service import queue_and_send_sms


class OTPError(Exception):
    pass


class OTPExpiredError(OTPError):
    pass


class OTPLockedError(OTPError):
    def __init__(self, message: str, *, retry_after_seconds: int = 0) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class OTPRequestLimitedError(OTPError):
    def __init__(self, message: str, *, retry_after_seconds: int = 0) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_otp(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _placeholder_password_hash(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"sha256${digest}"


def _generate_otp(length: int = 6) -> str:
    alphabet = "0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _normalize_phone_e164(phone: str) -> str:
    return phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")


def _get_or_create_user(db: Session, phone_e164: str) -> User:
    phone_e164 = _normalize_phone_e164(phone_e164)
    user = db.query(User).filter(User.phone_e164 == phone_e164).first()
    if user:
        return user

    user = User(
        phone_e164=phone_e164,
        user_type=UserTypeEnum.customer,
        password_hash=_placeholder_password_hash(secrets.token_urlsafe(18)),
    )
    db.add(user)
    db.flush()
    return user


def request_login_otp(
    db: Session,
    phone_e164: str,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    phone_e164 = _normalize_phone_e164(phone_e164)
    user = _get_or_create_user(db, phone_e164)
    now = _now()
    window_start = now - timedelta(seconds=OTP_REQUEST_WINDOW_SECONDS)

    recent_requests = (
        db.query(OTPCode)
        .filter(OTPCode.user_id == user.id, OTPCode.created_at >= window_start)
        .count()
    )
    if recent_requests >= OTP_REQUEST_MAX_PER_WINDOW:
        oldest_recent = (
            db.query(OTPCode)
            .filter(OTPCode.user_id == user.id, OTPCode.created_at >= window_start)
            .order_by(OTPCode.created_at.asc())
            .first()
        )
        retry_after_seconds = OTP_REQUEST_WINDOW_SECONDS
        if oldest_recent:
            elapsed = (now - oldest_recent.created_at).total_seconds()
            retry_after_seconds = max(1, math.ceil(OTP_REQUEST_WINDOW_SECONDS - elapsed))
        raise OTPRequestLimitedError(
            "Too many OTP requests. Try again later.",
            retry_after_seconds=retry_after_seconds,
        )

    db.query(OTPCode).filter(
        OTPCode.user_id == user.id,
        OTPCode.consumed_at.is_(None),
        OTPCode.expires_at > now,
    ).update({OTPCode.consumed_at: now}, synchronize_session=False)

    raw_code = _generate_otp()
    otp_row = OTPCode(
        user_id=user.id,
        code_hash=_hash_otp(raw_code),
        attempts_count=0,
        created_at=now,
        expires_at=now + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    db.add(otp_row)
    db.flush()

    queue_and_send_sms(
        db=db,
        to=phone_e164,
        message=f"Votre code OTP Logix: {raw_code}. Expire dans {OTP_EXPIRE_MINUTES} min.",
        background_tasks=background_tasks,
    )


def verify_login_otp(db: Session, phone_e164: str, code: str) -> tuple[str, str]:
    phone_e164 = _normalize_phone_e164(phone_e164)
    user = db.query(User).filter(User.phone_e164 == phone_e164).first()
    if not user:
        raise OTPError("Invalid OTP")

    otp_row = (
        db.query(OTPCode)
        .filter(OTPCode.user_id == user.id, OTPCode.consumed_at.is_(None))
        .order_by(OTPCode.created_at.desc())
        .first()
    )
    if not otp_row:
        raise OTPError("Invalid OTP")

    now = _now()
    if otp_row.locked_until and otp_row.locked_until > now:
        retry_after_seconds = max(1, math.ceil((otp_row.locked_until - now).total_seconds()))
        raise OTPLockedError(
            "OTP temporarily locked. Try again later.",
            retry_after_seconds=retry_after_seconds,
        )

    if otp_row.expires_at <= now:
        raise OTPExpiredError("OTP expired")

    if _hash_otp(code) != otp_row.code_hash:
        otp_row.attempts_count += 1
        if otp_row.attempts_count >= OTP_MAX_ATTEMPTS:
            otp_row.locked_until = now + timedelta(minutes=OTP_LOCK_MINUTES)
        db.commit()
        raise OTPError("Invalid OTP")

    otp_row.consumed_at = now
    otp_row.locked_until = None
    db.commit()

    return create_access_token(str(user.id)), create_refresh_token(str(user.id))


def login_or_create(db: Session, phone_e164: str) -> str:
    user = _get_or_create_user(db, phone_e164)
    db.commit()
    return create_access_token(str(user.id))


def refresh_access_token(db: Session, refresh_token: str) -> tuple[str, str]:
    user_id = get_refresh_subject(refresh_token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise OTPError("User not found")
    return create_access_token(str(user.id)), create_refresh_token(str(user.id))
