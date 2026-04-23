from sqlalchemy.orm import Session
from app.models.ussd import UssdSession, UssdLog
from app.models.shipments import Shipment


def get_or_create_session(db: Session, phone: str) -> UssdSession:
    session = db.query(UssdSession).filter(UssdSession.phone == phone).first()
    if session:
        return session
    session = UssdSession(phone=phone, state={})
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def handle_ussd(db: Session, session_id: str, service_code: str, phone: str, text: str) -> str:
    session = get_or_create_session(db, phone)
    db.add(UssdLog(session_id=session.id, payload=text or ""))
    db.commit()

    if not text:
        return "CON 1. Envoyer colis\n2. Suivre colis"

    parts = text.split("*")
    if parts[0] == "2":
        if len(parts) == 1:
            return "CON Entrer le numero du colis"
        shipment = db.query(Shipment).filter(Shipment.shipment_no == parts[1]).first()
        if not shipment:
            return "END Colis introuvable"
        return f"END Statut: {shipment.status}"

    return "END Option non disponible"
