from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def log_action(
    db: Session,
    *,
    entity: str,
    action: str,
    actor_user_id=None,
    actor_phone: str | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
    endpoint: str | None = None,
    method: str | None = None,
    status_code: int | None = None,
) -> None:
    db.add(
        AuditLog(
            entity=entity,
            action=action,
            actor_user_id=actor_user_id,
            actor_phone=actor_phone,
            ip_address=ip_address,
            request_id=request_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
        )
    )
