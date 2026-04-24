import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.services.audit_service import log_action

IDEMPOTENCY_TTL_HOURS = 24


def _fingerprint(operation: str, key: str, actor_user_id: UUID | None) -> str:
    raw = f"{operation}|{key.strip()}|{actor_user_id or 'anon'}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"idem:{digest[:32]}"


def has_processed_idempotency_key(
    db: Session,
    *,
    operation: str,
    key: str,
    actor_user_id: UUID | None,
) -> bool:
    fp = _fingerprint(operation, key, actor_user_id)
    since = datetime.now(UTC) - timedelta(hours=IDEMPOTENCY_TTL_HOURS)
    row = (
        db.query(AuditLog.id)
        .filter(
            AuditLog.entity == "idempotency",
            AuditLog.action == "processed",
            AuditLog.endpoint == fp,
            AuditLog.method == operation,
            AuditLog.created_at >= since,
        )
        .first()
    )
    return row is not None


def mark_processed_idempotency_key(
    db: Session,
    *,
    operation: str,
    key: str,
    actor_user_id: UUID | None,
    actor_phone: str | None = None,
) -> None:
    fp = _fingerprint(operation, key, actor_user_id)
    log_action(
        db,
        entity="idempotency",
        action="processed",
        actor_user_id=actor_user_id,
        actor_phone=actor_phone,
        endpoint=fp,
        method=operation,
        status_code=200,
    )
