from datetime import datetime, timedelta, UTC

from sqlalchemy.orm import Session
from app.config import USSD_CREATE_MAX_PER_WINDOW, USSD_CREATE_WINDOW_SECONDS
from app.models.ussd import UssdSession, UssdLog
from app.models.shipments import Shipment
from app.schemas.shipments import ShipmentCreate
from app.services.shipment_service import create_shipment


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in phone.strip() if ch not in {" ", "-", "(", ")"})


def _is_valid_phone(phone: str) -> bool:
    normalized = _normalize_phone(phone)
    if not normalized.startswith("+"):
        return False
    digits = normalized[1:]
    return digits.isdigit() and 8 <= len(normalized) <= 20


def _create_rate_limited(db: Session, sender_phone: str) -> bool:
    window_start = datetime.now(UTC) - timedelta(seconds=USSD_CREATE_WINDOW_SECONDS)
    recent_count = (
        db.query(Shipment)
        .filter(Shipment.sender_phone == sender_phone, Shipment.created_at >= window_start)
        .count()
    )
    return recent_count >= USSD_CREATE_MAX_PER_WINDOW


def get_or_create_session(db: Session, phone: str) -> UssdSession:
    normalized_phone = _normalize_phone(phone)
    session = db.query(UssdSession).filter(UssdSession.phone == normalized_phone).first()
    if session:
        return session
    session = UssdSession(phone=normalized_phone, state={})
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def handle_ussd(db: Session, session_id: str, service_code: str, phone: str, text: str) -> str:
    normalized_phone = _normalize_phone(phone)
    if not _is_valid_phone(normalized_phone):
        return "END Numero emetteur invalide"

    session = get_or_create_session(db, normalized_phone)
    db.add(UssdLog(session_id=session.id, payload=text or ""))
    db.commit()

    if not text:
        return "CON 1. Envoyer colis\n2. Suivre colis"

    parts = text.split("*")
    option = parts[0].strip()
    if option == "1":
        if len(parts) == 1:
            return "CON Nom du destinataire:"

        receiver_name = parts[1].strip()
        if len(parts) == 2:
            if len(receiver_name) < 2:
                return "END Nom invalide"
            return "CON Telephone destinataire:"

        receiver_phone = parts[2].strip()
        normalized_receiver_phone = _normalize_phone(receiver_phone)
        if len(receiver_name) < 2 or not _is_valid_phone(normalized_receiver_phone):
            return "END Donnees invalides"
        if _create_rate_limited(db, normalized_phone):
            return "END Limite de creation atteinte. Reessayez plus tard."

        payload = ShipmentCreate(
            sender_phone=normalized_phone,
            receiver_name=receiver_name,
            receiver_phone=normalized_receiver_phone,
            origin=None,
            destination=None,
        )
        shipment = create_shipment(db, payload, background_tasks=None)
        return f"END Colis cree: {shipment.shipment_no}"

    if option == "2":
        if len(parts) == 1:
            return "CON Entrer le numero du colis:"

        shipment_no = parts[1].strip()
        if not shipment_no:
            return "END Numero invalide"

        shipment = db.query(Shipment).filter(Shipment.shipment_no == shipment_no).first()
        if not shipment:
            return "END Colis introuvable"
        return f"END Statut: {shipment.status}"

    return "END Option non disponible"
