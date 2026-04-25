from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums import UserTypeEnum
from app.models.relays import RelayPoint
from app.models.shipments import RelayInventory, Shipment
from app.models.users import User
from app.schemas.relays import RelayCreate, RelayUpdate
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
