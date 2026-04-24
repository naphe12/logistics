import json
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.enums import UserTypeEnum
from app.models.incidents import Incident
from app.models.shipments import Shipment, ShipmentEvent
from app.models.sync import SyncActionLog
from app.models.users import User
from app.realtime.events import emit_shipment_status_update
from app.schemas.shipments import ShipmentCreate
from app.services.code_service import validate_pickup_code
from app.services.shipment_service import create_shipment

PICKUP_VALIDATE_PATH = re.compile(r"^/codes/shipments/([0-9a-fA-F-]{36})/pickup/validate$")
PICKUP_CONFIRM_PATH = re.compile(r"^/codes/shipments/([0-9a-fA-F-]{36})/pickup/confirm$")


def _extract_shipment_id_from_path(path: str, pattern: re.Pattern[str]) -> UUID:
    match = pattern.match(path.strip())
    if not match:
        raise ValueError("Invalid path for action")
    return UUID(match.group(1))


def _require_roles(current_user: User, allowed: set[UserTypeEnum]) -> None:
    if current_user.user_type not in allowed:
        raise PermissionError("Forbidden for current user role")


def _shipment_snapshot(shipment: Shipment) -> dict:
    return {
        "id": str(shipment.id),
        "shipment_id": str(shipment.id),
        "shipment_no": shipment.shipment_no,
        "status": shipment.status,
        "updated_at": shipment.updated_at.isoformat() if shipment.updated_at else None,
        "server_version": shipment.updated_at.isoformat() if shipment.updated_at else None,
    }


def _resolve_conflict_policy(conflict_policy: str | None) -> str:
    policy = (conflict_policy or "server_wins").strip().lower()
    if policy not in {"server_wins", "client_wins", "manual_review"}:
        return "server_wins"
    return policy


def _get_or_create_sync_conflict_incident(db: Session, shipment: Shipment, message: str) -> Incident:
    existing = (
        db.query(Incident)
        .filter(
            Incident.shipment_id == shipment.id,
            Incident.incident_type == "sync_conflict",
            Incident.status.in_(["open", "investigating"]),
        )
        .order_by(Incident.created_at.desc())
        .first()
    )
    if existing:
        return existing
    incident = Incident(
        shipment_id=shipment.id,
        incident_type="sync_conflict",
        description=message,
        status="open",
    )
    db.add(incident)
    db.flush()
    return incident


def _is_version_conflict(shipment: Shipment, client_version: datetime | None) -> bool:
    if client_version is None or shipment.updated_at is None:
        return False
    return client_version < shipment.updated_at


def _process_create_shipment(db: Session, current_user: User, payload: dict) -> dict:
    _require_roles(
        current_user,
        {UserTypeEnum.customer, UserTypeEnum.business, UserTypeEnum.agent, UserTypeEnum.admin},
    )
    shipment_payload = ShipmentCreate.model_validate(payload)
    shipment = create_shipment(db, shipment_payload, background_tasks=None)
    db.commit()
    db.refresh(shipment)
    return {
        "id": str(shipment.id),
        "shipment_id": str(shipment.id),
        "shipment_no": shipment.shipment_no,
        "status": shipment.status,
        "updated_at": shipment.updated_at.isoformat() if shipment.updated_at else None,
        "server_version": shipment.updated_at.isoformat() if shipment.updated_at else None,
    }


def _process_pickup_validate(db: Session, current_user: User, path: str, payload: dict) -> dict:
    _require_roles(current_user, {UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.admin})
    shipment_id = _extract_shipment_id_from_path(path, PICKUP_VALIDATE_PATH)
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise ValueError("Shipment not found")
    code = str(payload.get("code") or "")
    if not code:
        raise ValueError("Missing code")
    valid, message, error_code = validate_pickup_code(db, shipment_id, code, consume=False)
    db.commit()
    return {
        "id": str(shipment_id),
        "shipment_id": str(shipment_id),
        "valid": valid,
        "message": message,
        "error_code": error_code,
        "updated_at": shipment.updated_at.isoformat() if shipment.updated_at else None,
        "server_version": shipment.updated_at.isoformat() if shipment.updated_at else None,
    }


def _process_pickup_confirm(
    db: Session,
    current_user: User,
    path: str,
    payload: dict,
    *,
    client_version: datetime | None,
    conflict_policy: str | None,
) -> dict:
    _require_roles(current_user, {UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.admin})
    shipment_id = _extract_shipment_id_from_path(path, PICKUP_CONFIRM_PATH)
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise ValueError("Shipment not found")
    policy = _resolve_conflict_policy(conflict_policy)
    if _is_version_conflict(shipment, client_version):
        if policy == "client_wins":
            pass
        elif policy == "manual_review":
            incident = _get_or_create_sync_conflict_incident(
                db,
                shipment,
                "Sync version conflict requires manual review",
            )
            return {
                "__sync_status": "conflict_manual_review",
                "message": "Version conflict requires manual review",
                "server": _shipment_snapshot(shipment),
                "client_version": client_version.isoformat() if client_version else None,
                "incident_id": str(incident.id),
            }
        else:
            return {
                "__sync_status": "conflict_server_wins",
                "message": "Version conflict resolved by server version",
                "server": _shipment_snapshot(shipment),
                "client_version": client_version.isoformat() if client_version else None,
            }
    code = str(payload.get("code") or "")
    if not code:
        raise ValueError("Missing code")
    valid, message, error_code = validate_pickup_code(db, shipment_id, code, consume=True)
    if not valid:
        db.commit()
        return {
            "id": str(shipment_id),
            "shipment_id": str(shipment_id),
            "confirmed": False,
            "status": shipment.status,
            "message": message,
            "error_code": error_code,
            "updated_at": shipment.updated_at.isoformat() if shipment.updated_at else None,
            "server_version": shipment.updated_at.isoformat() if shipment.updated_at else None,
        }

    relay_id_raw = payload.get("relay_id")
    relay_id = UUID(str(relay_id_raw)) if relay_id_raw else None
    event_type = str(payload.get("event_type") or "shipment_delivered_to_receiver")
    shipment.status = "delivered"
    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            relay_id=relay_id,
            event_type=event_type,
        )
    )
    db.commit()
    db.refresh(shipment)
    emit_shipment_status_update(
        shipment_id=shipment.id,
        status=shipment.status or "delivered",
        event_type=event_type,
        relay_id=relay_id,
    )
    return {
        "id": str(shipment_id),
        "shipment_id": str(shipment_id),
        "confirmed": True,
        "status": shipment.status,
        "message": "Pickup confirmed and shipment delivered",
        "error_code": None,
        "updated_at": shipment.updated_at.isoformat() if shipment.updated_at else None,
        "server_version": shipment.updated_at.isoformat() if shipment.updated_at else None,
    }


def apply_sync_action(
    db: Session,
    current_user: User,
    *,
    client_action_id: str,
    action_type: str,
    method: str,
    path: str,
    payload: dict,
    client_version: datetime | None = None,
    conflict_policy: str | None = None,
) -> dict:
    existing = (
        db.query(SyncActionLog)
        .filter(SyncActionLog.client_action_id == client_action_id)
        .first()
    )
    if existing and existing.status in {"success", "conflict"}:
        try:
            cached = json.loads(existing.response_json or "{}")
        except json.JSONDecodeError:
            cached = {}
        return {"status": "replayed", "data": cached}

    action_type = action_type.strip()
    method = method.strip().upper()
    path = path.strip()

    if existing is None:
        existing = SyncActionLog(
            client_action_id=client_action_id,
            user_id=current_user.id,
            action_type=action_type,
            method=method,
            path=path,
            status="processing",
            attempts=1,
            error_message=None,
            response_json=None,
        )
        db.add(existing)
    else:
        existing.attempts += 1
        existing.status = "processing"
        existing.error_message = None
    db.flush()

    try:
        if action_type == "create_shipment" and method == "POST" and path == "/shipments":
            data = _process_create_shipment(db, current_user, payload)
        elif action_type == "pickup_validate" and method == "POST":
            data = _process_pickup_validate(db, current_user, path, payload)
        elif action_type == "pickup_confirm" and method == "POST":
            data = _process_pickup_confirm(
                db,
                current_user,
                path,
                payload,
                client_version=client_version,
                conflict_policy=conflict_policy,
            )
        else:
            raise ValueError("Unsupported sync action")

        sync_status = str(data.pop("__sync_status", "applied"))
        existing.status = "conflict" if sync_status.startswith("conflict_") else "success"
        existing.response_json = json.dumps(data, ensure_ascii=True)
        existing.updated_at = datetime.now(UTC)
        db.commit()
        return {"status": sync_status, "data": data}
    except Exception as exc:
        db.rollback()
        retry = (
            db.query(SyncActionLog)
            .filter(SyncActionLog.client_action_id == client_action_id)
            .first()
        )
        if retry:
            retry.status = "failed"
            retry.error_message = str(exc)
            retry.updated_at = datetime.now(UTC)
        else:
            db.add(
                SyncActionLog(
                    client_action_id=client_action_id,
                    user_id=current_user.id,
                    action_type=action_type,
                    method=method,
                    path=path,
                    status="failed",
                    attempts=1,
                    error_message=str(exc),
                    response_json=None,
                )
            )
        db.commit()
        return {"status": "failed", "error": str(exc)}
