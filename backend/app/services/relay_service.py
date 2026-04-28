from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.enums import UserTypeEnum
from app.models.addresses import Address, Commune, Province
from app.models.relay_onboarding import RelayManagerApplication
from app.models.relays import RelayPoint
from app.models.shipments import RelayInventory, Shipment
from app.models.users import User
from app.schemas.relays import RelayCreate, RelayManagerApplicationCreate, RelayManagerApplicationReview, RelayUpdate
from app.services.audit_service import log_action


class RelayError(Exception):
    pass


class RelayNotFoundError(RelayError):
    pass


class RelayConflictError(RelayError):
    pass


class AgentAssignmentError(RelayError):
    pass


class RelayInventoryError(RelayError):
    pass


class RelayCapacityError(RelayError):
    pass


def get_relay_capacity_status(db: Session, relay_id: UUID) -> dict:
    relay = get_relay(db, relay_id)
    if not relay:
        raise RelayNotFoundError("Relay not found")

    current_present = (
        db.query(RelayInventory)
        .filter(RelayInventory.relay_id == relay_id, RelayInventory.present.is_(True))
        .count()
    )
    capacity = relay.storage_capacity
    if capacity is None:
        return {
            "relay_id": relay.id,
            "storage_capacity": None,
            "current_present": current_present,
            "available": None,
            "is_full": False,
            "utilization_ratio": None,
        }

    available = max(0, capacity - current_present)
    is_full = current_present >= capacity
    utilization_ratio = 1.0 if capacity == 0 and current_present > 0 else (current_present / capacity if capacity > 0 else 0.0)
    return {
        "relay_id": relay.id,
        "storage_capacity": capacity,
        "current_present": current_present,
        "available": available,
        "is_full": is_full,
        "utilization_ratio": utilization_ratio,
    }


def _assert_capacity_for_present(db: Session, relay: RelayPoint, shipment_id: UUID) -> None:
    if relay.storage_capacity is None:
        return

    existing_row = (
        db.query(RelayInventory)
        .filter(RelayInventory.relay_id == relay.id, RelayInventory.shipment_id == shipment_id)
        .first()
    )
    if existing_row and existing_row.present:
        return

    current_present = (
        db.query(RelayInventory)
        .filter(RelayInventory.relay_id == relay.id, RelayInventory.present.is_(True))
        .count()
    )
    if current_present >= relay.storage_capacity:
        raise RelayCapacityError(
            f"Relay capacity reached ({current_present}/{relay.storage_capacity})"
        )


def _assert_not_present_in_other_relay(
    db: Session,
    *,
    relay_id: UUID,
    shipment_id: UUID,
) -> None:
    conflict = (
        db.query(RelayInventory)
        .filter(
            RelayInventory.shipment_id == shipment_id,
            RelayInventory.relay_id != relay_id,
            RelayInventory.present.is_(True),
        )
        .first()
    )
    if conflict:
        raise RelayInventoryError(
            "Shipment is already marked present in another relay"
        )


def list_relays(db: Session) -> list[RelayPoint]:
    return db.query(RelayPoint).order_by(RelayPoint.name.asc()).all()


def list_relays_with_filters(
    db: Session,
    *,
    q: str | None = None,
    province_id=None,
    commune_id=None,
    only_active: bool | None = None,
    operational_status: str | None = None,
) -> list[dict]:
    query = db.query(RelayPoint)
    if q:
        text = f"%{q.strip()}%"
        query = query.filter(
            RelayPoint.name.ilike(text) | RelayPoint.relay_code.ilike(text) | RelayPoint.type.ilike(text)
        )
    if province_id:
        query = query.filter(RelayPoint.province_id == province_id)
    if commune_id:
        query = query.filter(RelayPoint.commune_id == commune_id)
    if only_active is not None:
        query = query.filter(RelayPoint.is_active.is_(only_active))

    relays = query.order_by(RelayPoint.name.asc()).all()
    if not relays:
        return []

    relay_ids = [row.id for row in relays]
    address_ids = [row.address_id for row in relays if row.address_id]
    counts = dict(
        db.query(RelayInventory.relay_id, func.count(RelayInventory.id))
        .filter(RelayInventory.relay_id.in_(relay_ids), RelayInventory.present.is_(True))
        .group_by(RelayInventory.relay_id)
        .all()
    )
    addresses_by_id = {}
    if address_ids:
        address_rows = db.query(Address).filter(Address.id.in_(address_ids)).all()
        addresses_by_id = {row.id: row for row in address_rows}
    commune_by_id = {}
    province_by_id = {}
    commune_ids = [row.commune_id for row in relays if row.commune_id]
    province_ids = [row.province_id for row in relays if row.province_id]
    if commune_ids:
        commune_rows = db.query(Commune).filter(Commune.id.in_(commune_ids)).all()
        commune_by_id = {row.id: row.name for row in commune_rows}
    if province_ids:
        province_rows = db.query(Province).filter(Province.id.in_(province_ids)).all()
        province_by_id = {row.id: row.name for row in province_rows}
    manager_rows = (
        db.query(User)
        .filter(User.relay_id.in_(relay_ids), User.user_type == UserTypeEnum.agent)
        .order_by(User.created_at.asc())
        .all()
    )
    manager_phone_by_relay: dict = {}
    for user in manager_rows:
        if user.relay_id and user.relay_id not in manager_phone_by_relay:
            manager_phone_by_relay[user.relay_id] = user.phone_e164

    rows: list[dict] = []
    for relay in relays:
        address = addresses_by_id.get(relay.address_id) if relay.address_id else None
        current_present = int(counts.get(relay.id, 0))
        capacity = relay.storage_capacity
        if capacity is None:
            available = None
            utilization_ratio = None
            is_full = False
        else:
            available = max(0, capacity - current_present)
            is_full = current_present >= capacity
            utilization_ratio = (
                1.0 if capacity == 0 and current_present > 0 else (current_present / capacity if capacity > 0 else 0.0)
            )

        if not relay.is_active:
            op_status = "closed"
        elif is_full:
            op_status = "full"
        else:
            op_status = "open"

        row = {
            "id": relay.id,
            "relay_code": relay.relay_code,
            "name": relay.name,
            "type": relay.type,
            "province_id": relay.province_id,
            "commune_id": relay.commune_id,
            "address_id": relay.address_id,
            "opening_hours": relay.opening_hours,
            "storage_capacity": relay.storage_capacity,
            "is_active": relay.is_active,
            "current_present": current_present,
            "available": available,
            "utilization_ratio": utilization_ratio,
            "operational_status": op_status,
            "latitude": float(address.latitude) if address and address.latitude is not None else None,
            "longitude": float(address.longitude) if address and address.longitude is not None else None,
            "quartier": address.quartier if address else None,
            "commune_name": commune_by_id.get(relay.commune_id) if relay.commune_id else (address.commune if address else None),
            "province_name": province_by_id.get(relay.province_id) if relay.province_id else (address.province if address else None),
            "landmark": address.landmark if address else None,
            "manager_phone": manager_phone_by_relay.get(relay.id),
        }
        rows.append(row)

    if operational_status:
        wanted = operational_status.strip().lower()
        rows = [row for row in rows if row.get("operational_status") == wanted]
    return rows


def create_relay_manager_application(
    db: Session,
    payload: RelayManagerApplicationCreate,
    *,
    created_by_user_id=None,
) -> RelayManagerApplication:
    row = RelayManagerApplication(
        relay_id=payload.relay_id,
        manager_name=payload.manager_name,
        manager_phone=payload.manager_phone,
        manager_email=payload.manager_email,
        notes=payload.notes,
        status="pending",
        training_completed=False,
        created_by_user_id=created_by_user_id,
    )
    db.add(row)
    log_action(db, entity="relay_manager_applications", action="create")
    db.commit()
    db.refresh(row)
    return row


def list_relay_manager_applications(
    db: Session,
    *,
    status: str | None = None,
    relay_id=None,
    limit: int = 100,
) -> list[RelayManagerApplication]:
    query = db.query(RelayManagerApplication)
    if status:
        query = query.filter(RelayManagerApplication.status == status)
    if relay_id:
        query = query.filter(RelayManagerApplication.relay_id == relay_id)
    limit = max(1, min(limit, 500))
    return query.order_by(RelayManagerApplication.created_at.desc()).limit(limit).all()


def review_relay_manager_application(
    db: Session,
    application_id,
    payload: RelayManagerApplicationReview,
    *,
    reviewed_by_user_id=None,
) -> RelayManagerApplication:
    row = db.query(RelayManagerApplication).filter(RelayManagerApplication.id == application_id).first()
    if not row:
        raise RelayNotFoundError("Relay manager application not found")
    row.status = payload.status
    row.training_completed = bool(payload.training_completed)
    if payload.notes:
        row.notes = payload.notes
    row.reviewed_by_user_id = reviewed_by_user_id
    row.reviewed_at = func.now()
    log_action(db, entity="relay_manager_applications", action="review")
    db.commit()
    db.refresh(row)
    return row


def get_relay(db: Session, relay_id: UUID) -> RelayPoint | None:
    return db.query(RelayPoint).filter(RelayPoint.id == relay_id).first()


def create_relay(db: Session, payload: RelayCreate) -> RelayPoint:
    relay = RelayPoint(**payload.model_dump())
    db.add(relay)
    log_action(db, entity="relay_points", action="create")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RelayConflictError("Relay code already exists") from exc
    db.refresh(relay)
    return relay


def update_relay(db: Session, relay_id: UUID, payload: RelayUpdate) -> RelayPoint:
    relay = get_relay(db, relay_id)
    if not relay:
        raise RelayNotFoundError("Relay not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(relay, field, value)
    log_action(db, entity="relay_points", action="update")

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RelayConflictError("Relay update conflicts with existing data") from exc
    db.refresh(relay)
    return relay


def delete_relay(db: Session, relay_id: UUID) -> None:
    relay = get_relay(db, relay_id)
    if not relay:
        raise RelayNotFoundError("Relay not found")
    db.delete(relay)
    log_action(db, entity="relay_points", action="delete")
    db.commit()


def list_relay_agents(db: Session, relay_id: UUID) -> list[User]:
    relay = get_relay(db, relay_id)
    if not relay:
        raise RelayNotFoundError("Relay not found")
    return (
        db.query(User)
        .filter(User.relay_id == relay_id, User.user_type == UserTypeEnum.agent)
        .order_by(User.created_at.desc())
        .all()
    )


def assign_agent_to_relay(db: Session, relay_id: UUID, user_id: UUID) -> User:
    relay = get_relay(db, relay_id)
    if not relay:
        raise RelayNotFoundError("Relay not found")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AgentAssignmentError("User not found")
    if user.user_type != UserTypeEnum.agent:
        raise AgentAssignmentError("Only users with agent role can be assigned to a relay")

    user.relay_id = relay_id
    log_action(db, entity="users", action="assign_relay")
    db.commit()
    db.refresh(user)
    return user


def unassign_agent_from_relay(db: Session, relay_id: UUID, user_id: UUID) -> User:
    relay = get_relay(db, relay_id)
    if not relay:
        raise RelayNotFoundError("Relay not found")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AgentAssignmentError("User not found")
    if user.relay_id != relay_id:
        raise AgentAssignmentError("User is not assigned to this relay")

    user.relay_id = None
    log_action(db, entity="users", action="unassign_relay")
    db.commit()
    db.refresh(user)
    return user


def list_relay_inventory(db: Session, relay_id: UUID, *, present_only: bool = False) -> list[dict]:
    relay = get_relay(db, relay_id)
    if not relay:
        raise RelayNotFoundError("Relay not found")

    query = (
        db.query(RelayInventory, Shipment)
        .outerjoin(Shipment, Shipment.id == RelayInventory.shipment_id)
        .filter(RelayInventory.relay_id == relay_id)
    )
    if present_only:
        query = query.filter(RelayInventory.present.is_(True))
    rows = query.order_by(RelayInventory.id.desc()).all()
    return [
        {
            "id": inventory.id,
            "relay_id": inventory.relay_id,
            "shipment_id": inventory.shipment_id,
            "present": inventory.present,
            "shipment_no": shipment.shipment_no if shipment else None,
            "shipment_status": shipment.status if shipment else None,
        }
        for inventory, shipment in rows
    ]


def upsert_relay_inventory(
    db: Session,
    relay_id: UUID,
    *,
    shipment_id: UUID,
    present: bool,
    auto_commit: bool = True,
) -> RelayInventory:
    relay = get_relay(db, relay_id)
    if not relay:
        raise RelayNotFoundError("Relay not found")
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise RelayInventoryError("Shipment not found")
    if present:
        _assert_not_present_in_other_relay(
            db,
            relay_id=relay_id,
            shipment_id=shipment_id,
        )
        _assert_capacity_for_present(db, relay, shipment_id)

    row = (
        db.query(RelayInventory)
        .filter(RelayInventory.relay_id == relay_id, RelayInventory.shipment_id == shipment_id)
        .first()
    )
    if not row:
        row = RelayInventory(relay_id=relay_id, shipment_id=shipment_id, present=present)
        db.add(row)
        log_action(db, entity="relay_inventory", action="create")
    else:
        row.present = present
        log_action(db, entity="relay_inventory", action="update")
    if auto_commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row
