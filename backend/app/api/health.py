from datetime import UTC, datetime

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.config import APP_VERSION
from app.database import SessionLocal
from app.services.sms_worker_service import get_sms_queue_worker_status

router = APIRouter(tags=["health"])

STARTED_AT = datetime.now(UTC)


def _db_checks() -> tuple[bool, dict]:
    db = SessionLocal()
    details = {
        "reachable": False,
        "alembic_version": None,
        "error": None,
    }
    try:
        db.execute(text("SELECT 1"))
        details["reachable"] = True
        version_row = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
        details["alembic_version"] = version_row[0] if version_row else None
        return True, details
    except Exception as exc:
        details["error"] = str(exc)[:500]
        return False, details
    finally:
        db.close()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/live")
def health_live():
    now = datetime.now(UTC)
    uptime_seconds = int((now - STARTED_AT).total_seconds())
    return {
        "status": "ok",
        "app_version": APP_VERSION,
        "started_at": STARTED_AT.isoformat(),
        "now": now.isoformat(),
        "uptime_seconds": uptime_seconds,
    }


@router.get("/health/ready")
def health_ready(response: Response):
    db_ok, db_details = _db_checks()
    worker = get_sms_queue_worker_status()
    ready = db_ok
    response.status_code = 200 if ready else 503
    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "app_version": APP_VERSION,
        "checks": {
            "database": db_details,
            "sms_worker": worker,
        },
    }
