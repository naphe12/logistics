from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums import UserTypeEnum
from app.models.relays import RelayPoint
from app.models.users import User
from app.schemas.relays import RelayCreate, RelayUpdate


class RelayError(Exception):
    pass


class RelayNotFoundError(RelayError):
    pass


class RelayConflictError(RelayError):
    pass


class AgentAssignmentError(RelayError):
    pass


def list_relays(db: Session) -> list[RelayPoint]:
    return db.query(RelayPoint).order_by(RelayPoint.name.asc()).all()


def get_relay(db: Session, relay_id: UUID) -> RelayPoint | None:
    return db.query(RelayPoint).filter(RelayPoint.id == relay_id).first()


def create_relay(db: Session, payload: RelayCreate) -> RelayPoint:
    relay = RelayPoint(**payload.model_dump())
    db.add(relay)
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
    db.commit()
    db.refresh(user)
    return user
