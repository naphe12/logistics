from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import USSD_CREATE_MAX_PER_WINDOW, USSD_CREATE_WINDOW_SECONDS
from app.enums import CodePurposeEnum
from app.models.shipments import Shipment
from app.models.ussd import ShipmentCode, UssdLog, UssdSession
from app.schemas.shipments import ShipmentCreate
from app.services.shipment_service import create_shipment


def _menu() -> str:
    return "CON Logix\n1. Envoyer colis\n2. Suivre colis\n3. Recevoir code retrait"


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


def _get_visible_shipment(db: Session, phone: str, shipment_no: str) -> Shipment | None:
    return (
        db.query(Shipment)
        .filter(
            Shipment.shipment_no == shipment_no,
            or_(Shipment.sender_phone == phone, Shipment.receiver_phone == phone),
        )
        .first()
    )


def _active_pickup_code(db: Session, shipment_id) -> ShipmentCode | None:
    now = datetime.now(UTC)
    return (
        db.query(ShipmentCode)
        .filter(
            ShipmentCode.shipment_id == shipment_id,
            ShipmentCode.purpose == CodePurposeEnum.pickup,
            ShipmentCode.expires_at >= now,
        )
        .order_by(ShipmentCode.expires_at.desc())
        .first()
    )


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


def _route_send_shipment(db: Session, phone: str, parts: list[str]) -> str:
    if len(parts) == 1:
        return "CON Nom du destinataire:\n0. Retour"

    receiver_name = parts[1].strip()
    if len(receiver_name) < 2:
        return "CON Nom invalide.\nNom du destinataire:\n0. Retour"

    if len(parts) == 2:
        return "CON Telephone destinataire (format +257...):\n0. Retour"

    receiver_phone = _normalize_phone(parts[2].strip())
    if not _is_valid_phone(receiver_phone):
        return "CON Telephone invalide.\nTelephone destinataire (+257...):\n0. Retour"

    if len(parts) == 3:
        return (
            f"CON Confirmer envoi?\nDest: {receiver_name}\nTel: {receiver_phone}\n"
            "1. Confirmer\n0. Retour"
        )

    if parts[3].strip() != "1":
        return "CON Confirmation invalide.\n1. Confirmer\n0. Retour"

    if _create_rate_limited(db, phone):
        return "END Limite de creation atteinte. Reessayez plus tard."

    payload = ShipmentCreate(
        sender_phone=phone,
        receiver_name=receiver_name,
        receiver_phone=receiver_phone,
        origin=None,
        destination=None,
    )
    shipment = create_shipment(db, payload, background_tasks=None)
    return f"END Colis cree: {shipment.shipment_no}"


def _route_track_shipment(db: Session, phone: str, parts: list[str]) -> str:
    if len(parts) == 1:
        return "CON Numero du colis (ex: PBL-20260424-ABC12345):\n0. Retour"

    shipment_no = parts[1].strip().upper()
    if not shipment_no:
        return "CON Numero invalide.\nNumero du colis:\n0. Retour"

    shipment = _get_visible_shipment(db, phone, shipment_no)
    if not shipment:
        return "END Colis introuvable pour ce numero."

    return f"END Colis {shipment.shipment_no}\nStatut: {shipment.status or 'unknown'}"


def _route_pickup_code(db: Session, phone: str, parts: list[str]) -> str:
    if len(parts) == 1:
        return "CON Numero du colis:\n0. Retour"

    shipment_no = parts[1].strip().upper()
    if not shipment_no:
        return "CON Numero invalide.\nNumero du colis:\n0. Retour"

    shipment = _get_visible_shipment(db, phone, shipment_no)
    if not shipment:
        return "END Colis introuvable pour ce numero."

    code = _active_pickup_code(db, shipment.id)
    if not code:
        return "END Aucun code retrait actif (expiré ou deja utilise)."

    return (
        f"END Code retrait: {code.code_last4}\n"
        f"Colis: {shipment.shipment_no}\n"
        f"Expire le: {code.expires_at.strftime('%Y-%m-%d %H:%M UTC')}"
    )


def _dispatch_parts(db: Session, phone: str, parts: list[str]) -> str:
    if not parts or parts[0] == "":
        return _menu()

    option = parts[0].strip()
    if option == "1":
        return _route_send_shipment(db, phone, parts)
    if option == "2":
        return _route_track_shipment(db, phone, parts)
    if option == "3":
        return _route_pickup_code(db, phone, parts)
    return "CON Option non disponible.\n0. Retour menu"


def handle_ussd(db: Session, session_id: str, service_code: str, phone: str, text: str) -> str:
    normalized_phone = _normalize_phone(phone)
    if not _is_valid_phone(normalized_phone):
        return "END Numero emetteur invalide"

    session = get_or_create_session(db, normalized_phone)
    db.add(UssdLog(session_id=session.id, payload=text or ""))
    db.commit()

    cleaned = (text or "").strip()
    if cleaned == "" or cleaned == "00":
        return _menu()

    parts = [segment.strip() for segment in cleaned.split("*")]

    # Global back/menu behavior:
    # - `00` always returns to root menu
    # - `0` goes one level up
    while parts and parts[-1] in {"0", "00"}:
        if parts[-1] == "00":
            return _menu()
        parts = parts[:-1]
        if not parts:
            return _menu()

    return _dispatch_parts(db, normalized_phone, parts)
