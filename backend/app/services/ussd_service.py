from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import (
    USSD_ALLOWED_SERVICE_CODES,
    USSD_CREATE_MAX_PER_WINDOW,
    USSD_CREATE_WINDOW_SECONDS,
    USSD_INPUT_MAX_LENGTH,
    USSD_MAX_STEPS,
)
from app.enums import CodePurposeEnum
from app.models.shipments import Shipment
from app.models.payments import PaymentTransaction
from app.models.relays import RelayPoint
from app.models.addresses import Address, Commune, Province
from app.models.ussd import ShipmentCode, UssdLog, UssdSession
from app.schemas.shipments import ShipmentCreate
from app.schemas.payments import PaymentCreate
from app.services.audit_service import log_action
from app.services.payment_service import create_payment, initiate_payment
from app.services.shipment_service import create_shipment

SHIPMENT_NO_RE = re.compile(r"^[A-Z0-9-]{6,40}$")
RELAY_CODE_RE = re.compile(r"^[A-Z0-9-]{2,30}$")


def _menu() -> str:
    return (
        "CON LOGIX\n"
        "1. Envoyer colis\n"
        "2. Suivre colis\n"
        "3. Code retrait\n"
        "4. Payer colis\n"
        "0. Retour  00. Menu"
    )


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in phone.strip() if ch not in {" ", "-", "(", ")"})


def _is_valid_phone(phone: str) -> bool:
    normalized = _normalize_phone(phone)
    if not normalized.startswith("+"):
        return False
    digits = normalized[1:]
    return digits.isdigit() and 8 <= len(normalized) <= 20


def _is_allowed_service_code(service_code: str) -> bool:
    if not USSD_ALLOWED_SERVICE_CODES:
        return True
    code = service_code.strip()
    return code in USSD_ALLOWED_SERVICE_CODES


def _sanitize_text(text: str) -> str:
    clean = (text or "").strip()
    if len(clean) > USSD_INPUT_MAX_LENGTH:
        clean = clean[:USSD_INPUT_MAX_LENGTH]
    return clean


def _normalize_parts(text: str) -> list[str]:
    cleaned = _sanitize_text(text)
    if cleaned == "":
        return []
    parts = [segment.strip() for segment in cleaned.split("*")]
    parts = [part for part in parts if part != ""]
    if len(parts) > USSD_MAX_STEPS:
        return parts[:USSD_MAX_STEPS]
    return parts


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


def _find_active_relay_by_code(db: Session, relay_code: str) -> RelayPoint | None:
    code = relay_code.strip().upper()
    if not RELAY_CODE_RE.match(code):
        return None
    return (
        db.query(RelayPoint)
        .filter(
            RelayPoint.relay_code == code,
            RelayPoint.is_active.is_(True),
        )
        .first()
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _tokenize(value: str) -> list[str]:
    return [tok for tok in re.split(r"[^a-zA-Z0-9]+", _normalize_text(value)) if tok]


def _guess_destination_relays(db: Session, destination_text: str, limit: int = 3) -> list[RelayPoint]:
    query_text = _normalize_text(destination_text)
    tokens = _tokenize(destination_text)
    if not query_text:
        return []

    rows = (
        db.query(RelayPoint, Address, Commune, Province)
        .outerjoin(Address, Address.id == RelayPoint.address_id)
        .outerjoin(Commune, Commune.id == RelayPoint.commune_id)
        .outerjoin(Province, Province.id == RelayPoint.province_id)
        .filter(RelayPoint.is_active.is_(True))
        .all()
    )

    scored: list[tuple[int, RelayPoint]] = []
    for relay, address, commune, province in rows:
        fields = [
            relay.relay_code or "",
            relay.name or "",
            relay.type or "",
            getattr(address, "province", "") or "",
            getattr(address, "commune", "") or "",
            getattr(address, "zone", "") or "",
            getattr(address, "colline", "") or "",
            getattr(address, "quartier", "") or "",
            getattr(address, "address_line", "") or "",
            getattr(address, "landmark", "") or "",
            getattr(commune, "name", "") or "",
            getattr(province, "name", "") or "",
        ]
        haystack = " ".join(_normalize_text(field) for field in fields if field).strip()
        if not haystack:
            continue

        score = 0
        if query_text in haystack:
            score += 8
        relay_code_l = _normalize_text(relay.relay_code or "")
        relay_name_l = _normalize_text(relay.name or "")
        if relay_code_l and query_text == relay_code_l:
            score += 20
        if relay_name_l and query_text == relay_name_l:
            score += 12
        for token in tokens:
            if token in relay_name_l:
                score += 4
            if token in relay_code_l:
                score += 5
            if token in haystack:
                score += 2
        if score > 0:
            scored.append((score, relay))

    scored.sort(key=lambda row: row[0], reverse=True)
    seen: set[str] = set()
    top: list[RelayPoint] = []
    for _score, relay in scored:
        key = str(relay.id)
        if key in seen:
            continue
        seen.add(key)
        top.append(relay)
        if len(top) >= max(1, min(limit, 5)):
            break
    return top


def get_or_create_session(db: Session, phone: str, ussd_session_id: str, service_code: str) -> UssdSession:
    normalized_phone = _normalize_phone(phone)
    session = db.query(UssdSession).filter(UssdSession.phone == normalized_phone).first()
    now = datetime.now(UTC).isoformat()
    if session:
        state = session.state if isinstance(session.state, dict) else {}
        state["last_session_id"] = ussd_session_id
        state["last_service_code"] = service_code
        state["last_seen_at"] = now
        session.state = state
        db.commit()
        return session
    session = UssdSession(
        phone=normalized_phone,
        state={
            "last_session_id": ussd_session_id,
            "last_service_code": service_code,
            "last_seen_at": now,
        },
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _route_send_shipment(db: Session, phone: str, parts: list[str]) -> str:
    if len(parts) == 1:
        return "CON Nom du destinataire:\n0. Retour\n00. Menu"

    receiver_name = parts[1].strip()
    if len(receiver_name) < 2 or len(receiver_name) > 80:
        return "CON Nom invalide (2-80 caracteres).\nNom du destinataire:\n0. Retour\n00. Menu"

    if len(parts) == 2:
        return "CON Telephone destinataire (format +257...):\n0. Retour\n00. Menu"

    receiver_phone = _normalize_phone(parts[2].strip())
    if not _is_valid_phone(receiver_phone):
        return "CON Telephone invalide.\nTelephone destinataire (+257...):\n0. Retour\n00. Menu"

    if len(parts) == 3:
        return (
            "CON Destination (ex: Gitega quartier Songa ou code relais):\n"
            "0. Retour\n00. Menu"
        )

    destination_input = parts[3].strip()
    destination_relay = _find_active_relay_by_code(db, destination_input.upper())
    payment_index = 4

    if not destination_relay:
        suggestions = _guess_destination_relays(db, destination_input, limit=3)
        if not suggestions:
            return (
                "CON Destination non reconnue.\n"
                "Entrez commune/quartier (ex: Gitega Songa):\n0. Retour\n00. Menu"
            )
        if len(parts) == 4:
            lines = [f"{idx + 1}. {row.name} ({row.relay_code})" for idx, row in enumerate(suggestions)]
            return (
                "CON Relais proposes:\n"
                + "\n".join(lines)
                + "\nChoisir 1-3\n0. Retour\n00. Menu"
            )
        choice_raw = parts[4].strip()
        if choice_raw not in {"1", "2", "3"}:
            lines = [f"{idx + 1}. {row.name} ({row.relay_code})" for idx, row in enumerate(suggestions)]
            return (
                "CON Choix invalide.\n"
                + "\n".join(lines)
                + "\nChoisir 1-3\n0. Retour\n00. Menu"
            )
        choice = int(choice_raw)
        if choice < 1 or choice > len(suggestions):
            return "CON Choix hors options.\nReponse 1-3.\n0. Retour\n00. Menu"
        destination_relay = suggestions[choice - 1]
        payment_index = 5

    if len(parts) == payment_index:
        return (
            "CON Paiement de ce colis?\n"
            "1. Payer maintenant\n"
            "2. Payer a la livraison\n"
            "3. Sans paiement\n"
            "0. Retour\n00. Menu"
        )

    payment_choice = parts[payment_index].strip()
    if payment_choice not in {"1", "2", "3"}:
        return (
            "CON Choix invalide.\n"
            "1. Payer maintenant\n"
            "2. Payer a la livraison\n"
            "3. Sans paiement\n"
            "0. Retour\n00. Menu"
        )

    if payment_choice in {"1", "2"}:
        amount_index = payment_index + 1
        confirm_index = payment_index + 2
        if len(parts) == amount_index:
            return "CON Montant a payer (BIF):\n0. Retour\n00. Menu"
        amount = _parse_amount(parts[amount_index])
        if amount is None:
            return "CON Montant invalide.\nMontant a payer (BIF):\n0. Retour\n00. Menu"
        if len(parts) == confirm_index:
            mode_label = "maintenant" if payment_choice == "1" else "a la livraison"
            return (
                "CON Confirmer creation?\n"
                f"Exp: {phone}\n"
                f"Dest: {receiver_name}\n"
                f"Tel: {receiver_phone}\n"
                f"Relais: {destination_relay.name} ({destination_relay.relay_code})\n"
                f"Paiement: {mode_label} ({amount} BIF)\n"
                "1. Confirmer\n0. Retour\n00. Menu"
            )
        if parts[confirm_index].strip() != "1":
            return "CON Confirmation invalide.\n1. Confirmer\n0. Retour\n00. Menu"
    else:
        confirm_index = payment_index + 1
        if len(parts) == confirm_index:
            return (
                "CON Confirmer creation?\n"
                f"Exp: {phone}\n"
                f"Dest: {receiver_name}\n"
                f"Tel: {receiver_phone}\n"
                f"Relais: {destination_relay.name} ({destination_relay.relay_code})\n"
                "Paiement: plus tard\n"
                "1. Confirmer\n0. Retour\n00. Menu"
            )
        if parts[confirm_index].strip() != "1":
            return "CON Confirmation invalide.\n1. Confirmer\n0. Retour\n00. Menu"

    if _create_rate_limited(db, phone):
        return "END Limite de creation atteinte. Reessayez plus tard."

    payload = ShipmentCreate(
        sender_phone=phone,
        receiver_name=receiver_name,
        receiver_phone=receiver_phone,
        origin=None,
        destination=destination_relay.id,
        destination_relay_id=destination_relay.id,
    )
    shipment = create_shipment(db, payload, background_tasks=None)
    if payment_choice in {"1", "2"}:
        amount = _parse_amount(parts[payment_index + 1])
        if amount is None:
            return f"END Colis cree: {shipment.shipment_no}. Paiement non cree (montant invalide)."
        stage = "at_send" if payment_choice == "1" else "at_delivery"
        created_payment = create_payment(
            db,
            PaymentCreate(
                shipment_id=shipment.id,
                amount=amount,
                payer_phone=phone,
                payment_stage=stage,
                provider="ussd",
                extra={"source": "ussd_create_flow"},
            ),
        )
        if payment_choice == "1":
            initiated = initiate_payment(
                db,
                created_payment.id,
                external_ref=f"USSD-{shipment.shipment_no}-{str(created_payment.id).split('-')[0].upper()}",
            )
            return (
                f"END Colis cree: {shipment.shipment_no}\n"
                f"Payer: {phone}\n"
                f"Dest: {receiver_phone}\n"
                f"Relais: {destination_relay.name}\n"
                f"Paiement initie ({amount} BIF)\n"
                f"Ref: {initiated.external_ref}"
            )
        return (
            f"END Colis cree: {shipment.shipment_no}\n"
            f"Payer: {phone}\n"
            f"Dest: {receiver_phone}\n"
            f"Relais: {destination_relay.name}\n"
            f"Paiement prevu a la livraison ({amount} BIF)"
        )
    return (
        f"END Colis cree: {shipment.shipment_no}\n"
        f"Expediteur: {phone}\n"
        f"Destinataire: {receiver_phone}\n"
        f"Relais destination: {destination_relay.name}\n"
        "Paiement: a definir"
    )


def _route_track_shipment(db: Session, phone: str, parts: list[str]) -> str:
    if len(parts) == 1:
        return "CON Numero du colis (ex: PBL-20260424-ABC12345):\n0. Retour\n00. Menu"

    shipment_no = parts[1].strip().upper()
    if not shipment_no or not SHIPMENT_NO_RE.match(shipment_no):
        return "CON Numero invalide.\nNumero du colis:\n0. Retour\n00. Menu"

    shipment = _get_visible_shipment(db, phone, shipment_no)
    if not shipment:
        return "END Colis introuvable pour ce numero."

    return f"END Colis {shipment.shipment_no}\nStatut: {shipment.status or 'unknown'}"


def _route_pickup_code(db: Session, phone: str, parts: list[str]) -> str:
    if len(parts) == 1:
        return "CON Numero du colis:\n0. Retour\n00. Menu"

    shipment_no = parts[1].strip().upper()
    if not shipment_no or not SHIPMENT_NO_RE.match(shipment_no):
        return "CON Numero invalide.\nNumero du colis:\n0. Retour\n00. Menu"

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
    if option == "4":
        return _route_pay_shipment(db, phone, parts)
    return "CON Option non disponible.\n0. Retour\n00. Menu"


def _parse_amount(raw: str) -> Decimal | None:
    normalized = raw.strip().replace(" ", "").replace(",", ".")
    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None
    if amount <= 0:
        return None
    if amount > Decimal("100000000"):
        return None
    return amount.quantize(Decimal("0.01"))


def _find_open_payment(db: Session, shipment_id, payer_phone: str) -> PaymentTransaction | None:
    return (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.shipment_id == shipment_id,
            PaymentTransaction.payer_phone == payer_phone,
            PaymentTransaction.status.in_(["pending", "processing"]),
        )
        .order_by(PaymentTransaction.created_at.desc())
        .first()
    )


def _route_pay_shipment(db: Session, phone: str, parts: list[str]) -> str:
    if len(parts) == 1:
        return "CON Numero du colis a payer:\n0. Retour\n00. Menu"

    shipment_no = parts[1].strip().upper()
    if not shipment_no or not SHIPMENT_NO_RE.match(shipment_no):
        return "CON Numero invalide.\nNumero du colis:\n0. Retour\n00. Menu"

    shipment = _get_visible_shipment(db, phone, shipment_no)
    if not shipment:
        return "END Colis introuvable pour ce numero."

    if len(parts) == 2:
        return "CON Montant a payer (BIF):\n0. Retour\n00. Menu"

    amount = _parse_amount(parts[2])
    if amount is None:
        return "CON Montant invalide.\nMontant a payer (BIF):\n0. Retour\n00. Menu"

    if len(parts) == 3:
        return (
            f"CON Type paiement?\nColis: {shipment.shipment_no}\nMontant: {amount} BIF\n"
            "1. Au depot\n2. A la livraison\n0. Retour\n00. Menu"
        )

    stage_choice = parts[3].strip()
    stage = "at_send" if stage_choice == "1" else "at_delivery" if stage_choice == "2" else None
    if stage is None:
        return "CON Choix invalide.\n1. Au depot\n2. A la livraison\n0. Retour\n00. Menu"

    existing = _find_open_payment(db, shipment.id, phone)
    if existing:
        return (
            f"END Paiement deja en cours.\n"
            f"Ref: {existing.external_ref or str(existing.id)}\n"
            f"Statut: {existing.status or 'pending'}"
        )

    created = create_payment(
        db,
        PaymentCreate(
            shipment_id=shipment.id,
            amount=amount,
            payer_phone=phone,
            payment_stage=stage,
            provider="ussd",
            extra={"source": "ussd"},
        ),
    )
    initiated = initiate_payment(
        db,
        created.id,
        external_ref=f"USSD-{shipment.shipment_no}-{str(created.id).split('-')[0].upper()}",
    )
    return (
        f"END Paiement initie.\n"
        f"Colis: {shipment.shipment_no}\n"
        f"Montant: {amount} BIF\n"
        f"Ref: {initiated.external_ref}"
    )


def handle_ussd(db: Session, session_id: str, service_code: str, phone: str, text: str) -> str:
    normalized_phone = _normalize_phone(phone)
    safe_text = _sanitize_text(text or "")
    if not _is_valid_phone(normalized_phone):
        return "END Numero emetteur invalide."
    if not _is_allowed_service_code(service_code):
        return "END Code service invalide."

    try:
        session = get_or_create_session(db, normalized_phone, session_id, service_code)
        payload_log = f"sid={session_id};sc={service_code};txt={safe_text}"
        db.add(UssdLog(session_id=session.id, payload=payload_log[:2000]))
        db.commit()

        cleaned = safe_text.strip().lower()
        if cleaned in {"", "00", "menu", "m"}:
            return _menu()

        parts = _normalize_parts(safe_text)
        if not parts:
            return _menu()

        # Global back/menu behavior:
        # - `00` always returns to root menu
        # - `0` goes one level up
        while parts and parts[-1] in {"0", "00"}:
            if parts[-1] == "00":
                return _menu()
            parts = parts[:-1]
            if not parts:
                return _menu()

        response = _dispatch_parts(db, normalized_phone, parts)

        state = session.state if isinstance(session.state, dict) else {}
        state["last_text"] = safe_text
        state["last_option"] = parts[0] if parts else None
        state["last_response_kind"] = "END" if response.startswith("END") else "CON"
        state["last_action_at"] = datetime.now(UTC).isoformat()
        session.state = state
        db.commit()
        return response
    except Exception:
        db.rollback()
        log_action(db, entity="ussd", action="processing_error")
        db.commit()
        return "END Service indisponible. Reessayez plus tard."
