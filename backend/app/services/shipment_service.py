import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.shipments import Shipment, ShipmentEvent
from app.schemas.shipments import ShipmentCreate, ShipmentStatusUpdate
from app.services.code_service import create_pickup_code
from app.services.notification_service import queue_and_send_sms


class ShipmentNotFoundError(Exception):
    pass


def generate_shipment_no() -> str:
    return f"PBL-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def create_shipment(db: Session, payload: ShipmentCreate) -> Shipment:
    shipment = Shipment(
        shipment_no=generate_shipment_no(),
        sender_id=payload.sender_id,
        sender_phone=payload.sender_phone,
        receiver_name=payload.receiver_name,
        receiver_phone=payload.receiver_phone,
        origin=payload.origin,
        destination=payload.destination,
        status="created",
    )
    db.add(shipment)
    db.flush()

    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            relay_id=payload.origin,
            event_type="shipment_created",
        )
    )

    _, raw_pickup_code = create_pickup_code(db, shipment.id)

    queue_and_send_sms(
        db,
        payload.sender_phone,
        f"Colis {shipment.shipment_no} cree avec succes.",
    )
    queue_and_send_sms(
        db,
        payload.receiver_phone,
        f"Votre colis {shipment.shipment_no} est enregistre. Code retrait: {raw_pickup_code}.",
    )

    db.refresh(shipment)
    return shipment


def update_shipment_status(db: Session, shipment_id, payload: ShipmentStatusUpdate) -> Shipment:
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise ShipmentNotFoundError("Shipment not found")

    shipment.status = payload.status
    db.add(
        ShipmentEvent(
            shipment_id=shipment.id,
            relay_id=payload.relay_id,
            event_type=payload.event_type,
        )
    )
    db.commit()
    db.refresh(shipment)
    return shipment
