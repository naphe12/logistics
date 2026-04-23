import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.ussd import ShipmentCode
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
