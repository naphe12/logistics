import hashlib
import secrets
from threading import Lock
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import (
    PICKUP_CODE_ATTEMPT_WINDOW_SECONDS,
    PICKUP_CODE_EXPIRE_HOURS,
    PICKUP_CODE_MAX_ATTEMPTS_PER_WINDOW,
)
from app.models.ussd import ShipmentCode, ShipmentCodeAttempt
from app.enums import CodePurposeEnum

PICKUP_CODE_ERROR_EXPIRED = "code_expired"
PICKUP_CODE_ERROR_INVALID = "code_invalid"
PICKUP_CODE_ERROR_MISSING = "code_missing"
PICKUP_CODE_ERROR_TOO_MANY_ATTEMPTS = "code_too_many_attempts"

_pickup_attempts_lock = Lock()
_pickup_attempts_by_shipment: dict[str, dict[str, object]] = {}


def hash_code(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_numeric_code(length: int = 4) -> str:
    alphabet = "0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _cleanup_pickup_attempt_windows(now: datetime) -> None:
    window_seconds = max(1, int(PICKUP_CODE_ATTEMPT_WINDOW_SECONDS))
    cutoff = now - timedelta(seconds=window_seconds)
    for key in list(_pickup_attempts_by_shipment.keys()):
        row = _pickup_attempts_by_shipment.get(key) or {}
        window_started_at = row.get("window_started_at")
        if not isinstance(window_started_at, datetime):
            _pickup_attempts_by_shipment.pop(key, None)
            continue
        if window_started_at < cutoff:
            _pickup_attempts_by_shipment.pop(key, None)


def _pickup_attempt_key(shipment_id) -> str:
    return str(shipment_id)


def _pickup_code_is_rate_limited(shipment_id, now: datetime) -> bool:
    max_attempts = max(1, int(PICKUP_CODE_MAX_ATTEMPTS_PER_WINDOW))
    with _pickup_attempts_lock:
        _cleanup_pickup_attempt_windows(now)
        row = _pickup_attempts_by_shipment.get(_pickup_attempt_key(shipment_id)) or {}
        failures = int(row.get("failures", 0))
        return failures >= max_attempts


def _register_pickup_code_failure(shipment_id, now: datetime) -> None:
    with _pickup_attempts_lock:
        _cleanup_pickup_attempt_windows(now)
        key = _pickup_attempt_key(shipment_id)
        row = _pickup_attempts_by_shipment.get(key)
        if not row:
            _pickup_attempts_by_shipment[key] = {"window_started_at": now, "failures": 1}
            return

        failures = int(row.get("failures", 0)) + 1
        row["failures"] = failures
        _pickup_attempts_by_shipment[key] = row


def _clear_pickup_code_failures(shipment_id) -> None:
    with _pickup_attempts_lock:
        _pickup_attempts_by_shipment.pop(_pickup_attempt_key(shipment_id), None)


def create_pickup_code(db: Session, shipment_id):
    now = datetime.now(UTC)
    (
        db.query(ShipmentCode)
        .filter(
            ShipmentCode.shipment_id == shipment_id,
            ShipmentCode.purpose == CodePurposeEnum.pickup,
            ShipmentCode.expires_at >= now,
        )
        .update({"expires_at": now - timedelta(seconds=1)}, synchronize_session=False)
    )

    raw = generate_numeric_code(4)
    expire_hours = max(1, int(PICKUP_CODE_EXPIRE_HOURS))
    row = ShipmentCode(
        shipment_id=shipment_id,
        code_hash=hash_code(raw),
        code_last4=raw,
        purpose=CodePurposeEnum.pickup,
        expires_at=now + timedelta(hours=expire_hours),
    )
    db.add(row)
    db.flush()
    _clear_pickup_code_failures(shipment_id)
    return row, raw


def validate_pickup_code(
    db: Session,
    shipment_id,
    raw_code: str,
    *,
    consume: bool = False,
) -> tuple[bool, str, str | None]:
    now = datetime.now(UTC)
    code_value = str(raw_code or "").strip()
    if not code_value:
        return False, "Pickup code missing", PICKUP_CODE_ERROR_MISSING

    if _pickup_code_is_rate_limited(shipment_id, now):
        return (
            False,
            "Too many attempts for this pickup code window",
            PICKUP_CODE_ERROR_TOO_MANY_ATTEMPTS,
        )

    expected_hash = hash_code(code_value)

    active_codes = (
        db.query(ShipmentCode)
        .filter(
            ShipmentCode.shipment_id == shipment_id,
            ShipmentCode.purpose == CodePurposeEnum.pickup,
            ShipmentCode.expires_at >= now,
        )
        .order_by(ShipmentCode.expires_at.desc())
        .all()
    )

    matched_code = next((row for row in active_codes if row.code_hash == expected_hash), None)
    success = matched_code is not None

    db.add(ShipmentCodeAttempt(shipment_id=shipment_id, success=success))
    if matched_code is not None:
        if consume:
            db.delete(matched_code)
        _clear_pickup_code_failures(shipment_id)
        db.flush()
        return True, "Pickup code valid", None

    expired_match = (
        db.query(ShipmentCode)
        .filter(
            ShipmentCode.shipment_id == shipment_id,
            ShipmentCode.purpose == CodePurposeEnum.pickup,
            ShipmentCode.code_hash == expected_hash,
            ShipmentCode.expires_at < now,
        )
        .order_by(ShipmentCode.expires_at.desc())
        .first()
    )

    db.flush()
    if expired_match is not None:
        _register_pickup_code_failure(shipment_id, now)
        return False, "Pickup code expired", PICKUP_CODE_ERROR_EXPIRED

    if active_codes:
        _register_pickup_code_failure(shipment_id, now)
        return False, "Invalid pickup code", PICKUP_CODE_ERROR_INVALID

    _register_pickup_code_failure(shipment_id, now)
    return False, "No active pickup code for this shipment", PICKUP_CODE_ERROR_MISSING
