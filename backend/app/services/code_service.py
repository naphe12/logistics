import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.ussd import ShipmentCode, ShipmentCodeAttempt
from app.enums import CodePurposeEnum


def hash_code(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_numeric_code(length: int = 4) -> str:
    alphabet = "0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_pickup_code(db: Session, shipment_id):
    raw = generate_numeric_code(4)
    row = ShipmentCode(
        shipment_id=shipment_id,
        code_hash=hash_code(raw),
        code_last4=raw,
        purpose=CodePurposeEnum.pickup,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(row)
    db.flush()
    return row, raw


def validate_pickup_code(
    db: Session,
    shipment_id,
    raw_code: str,
    *,
    consume: bool = False,
) -> tuple[bool, str, str | None]:
    now = datetime.now(UTC)
    expected_hash = hash_code(raw_code)

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
        return False, "Pickup code expired", "code_expired"

    if active_codes:
        return False, "Invalid pickup code", "code_invalid"

    return False, "No active pickup code for this shipment", "code_missing"
