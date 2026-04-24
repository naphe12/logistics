from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import COMMISSION_RELAY_RATE, COMMISSION_TRANSPORT_RATE
from app.models.incidents import Commission
from app.models.payments import PaymentTransaction
from app.models.shipments import Shipment
from app.models.statuses import PaymentStatus
from app.models.shipments import Manifest, ManifestShipment
from app.models.transport import Trip
from app.schemas.payments import PaymentCreate
from app.services.audit_service import log_action


class PaymentError(Exception):
    pass


class PaymentNotFoundError(PaymentError):
    pass


class PaymentStateError(PaymentError):
    pass


class PaymentValidationError(PaymentError):
    pass


def _to_money(value: Decimal | float) -> Decimal:
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def list_payment_statuses(db: Session) -> list[PaymentStatus]:
    return db.query(PaymentStatus).order_by(PaymentStatus.code.asc()).all()


def list_payments(
    db: Session,
    *,
    shipment_id: UUID | None = None,
    status: str | None = None,
    payer_phone: str | None = None,
) -> list[PaymentTransaction]:
    query = db.query(PaymentTransaction)
    if shipment_id is not None:
        query = query.filter(PaymentTransaction.shipment_id == shipment_id)
    if status:
        query = query.filter(PaymentTransaction.status == status)
    if payer_phone:
        query = query.filter(PaymentTransaction.payer_phone == payer_phone)
    return query.order_by(PaymentTransaction.created_at.desc()).all()


def get_payment(db: Session, payment_id: UUID) -> PaymentTransaction | None:
    return db.query(PaymentTransaction).filter(PaymentTransaction.id == payment_id).first()


def list_commissions(
    db: Session,
    *,
    shipment_id: UUID | None = None,
    payment_id: UUID | None = None,
) -> list[Commission]:
    query = db.query(Commission)
    if shipment_id is not None:
        query = query.filter(Commission.shipment_id == shipment_id)
    if payment_id is not None:
        query = query.filter(Commission.payment_id == payment_id)
    return query.order_by(Commission.created_at.desc()).all()


def _find_trip_for_shipment(db: Session, shipment_id: UUID) -> Trip | None:
    manifest = (
        db.query(Manifest)
        .join(ManifestShipment, ManifestShipment.manifest_id == Manifest.id)
        .filter(ManifestShipment.shipment_id == shipment_id)
        .order_by(Manifest.id.desc())
        .first()
    )
    if not manifest or not manifest.trip_id:
        return None
    return db.query(Trip).filter(Trip.id == manifest.trip_id).first()


def _ensure_commissions_for_paid_payment(db: Session, payment: PaymentTransaction) -> None:
    if not payment.shipment_id or payment.amount is None:
        return
    exists = db.query(Commission.id).filter(Commission.payment_id == payment.id).first()
    if exists:
        return

    shipment = db.query(Shipment).filter(Shipment.id == payment.shipment_id).first()
    if not shipment:
        return

    relay_rate = Decimal(str(COMMISSION_RELAY_RATE))
    transport_rate = Decimal(str(COMMISSION_TRANSPORT_RATE))
    relay_amount = _to_money(Decimal(payment.amount) * relay_rate)
    transport_amount = _to_money(Decimal(payment.amount) * transport_rate)

    relay_beneficiary = shipment.destination or shipment.origin
    trip = _find_trip_for_shipment(db, shipment.id)
    transport_beneficiary = trip.vehicle_id if trip else None

    db.add(
        Commission(
            shipment_id=shipment.id,
            payment_id=payment.id,
            commission_type="relay",
            beneficiary_kind="relay",
            beneficiary_id=relay_beneficiary,
            rate_pct=relay_rate,
            amount=relay_amount,
            status="accrued",
        )
    )
    db.add(
        Commission(
            shipment_id=shipment.id,
            payment_id=payment.id,
            commission_type="transport",
            beneficiary_kind="vehicle",
            beneficiary_id=transport_beneficiary,
            rate_pct=transport_rate,
            amount=transport_amount,
            status="accrued",
        )
    )
    log_action(db, entity="commissions", action="create")


def _require_status_exists(db: Session, status_code: str) -> None:
    exists = db.query(PaymentStatus.code).filter(PaymentStatus.code == status_code).first()
    if not exists:
        raise PaymentValidationError(f"Unknown payment status: {status_code}")


def create_payment(db: Session, payload: PaymentCreate) -> PaymentTransaction:
    shipment = db.query(Shipment).filter(Shipment.id == payload.shipment_id).first()
    if not shipment:
        raise PaymentValidationError("Shipment not found")
    _require_status_exists(db, "pending")

    payment = PaymentTransaction(
        shipment_id=payload.shipment_id,
        amount=payload.amount,
        payer_phone=payload.payer_phone,
        payment_stage=payload.payment_stage,
        provider=payload.provider,
        status="pending",
    )
    db.add(payment)
    log_action(db, entity="payment_transactions", action="create")
    db.commit()
    db.refresh(payment)
    return payment


def initiate_payment(db: Session, payment_id: UUID, external_ref: str | None = None) -> PaymentTransaction:
    _require_status_exists(db, "processing")
    payment = get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError("Payment not found")
    if payment.status not in {"pending", "failed"}:
        raise PaymentStateError(f"Cannot initiate payment from status '{payment.status}'")

    payment.status = "processing"
    if external_ref:
        payment.external_ref = external_ref
    elif not payment.external_ref:
        payment.external_ref = f"MM-{payment.id}"
    log_action(db, entity="payment_transactions", action="initiate")
    db.commit()
    db.refresh(payment)
    return payment


def confirm_payment(db: Session, payment_id: UUID, external_ref: str | None = None) -> PaymentTransaction:
    _require_status_exists(db, "paid")
    payment = get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError("Payment not found")
    if payment.status not in {"processing", "pending"}:
        raise PaymentStateError(f"Cannot confirm payment from status '{payment.status}'")

    payment.status = "paid"
    if external_ref:
        payment.external_ref = external_ref
    payment.failure_reason = None
    _ensure_commissions_for_paid_payment(db, payment)
    log_action(db, entity="payment_transactions", action="confirm")
    db.commit()
    db.refresh(payment)
    return payment


def fail_payment(db: Session, payment_id: UUID, reason: str) -> PaymentTransaction:
    _require_status_exists(db, "failed")
    payment = get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError("Payment not found")
    if payment.status not in {"pending", "processing"}:
        raise PaymentStateError(f"Cannot fail payment from status '{payment.status}'")

    payment.status = "failed"
    payment.failure_reason = reason
    log_action(db, entity="payment_transactions", action="fail")
    db.commit()
    db.refresh(payment)
    return payment


def cancel_payment(db: Session, payment_id: UUID) -> PaymentTransaction:
    _require_status_exists(db, "cancelled")
    payment = get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError("Payment not found")
    if payment.status in {"paid", "cancelled"}:
        raise PaymentStateError(f"Cannot cancel payment from status '{payment.status}'")

    payment.status = "cancelled"
    log_action(db, entity="payment_transactions", action="cancel")
    db.commit()
    db.refresh(payment)
    return payment


def refund_payment(db: Session, payment_id: UUID, reason: str) -> PaymentTransaction:
    _require_status_exists(db, "refunded")
    payment = get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError("Payment not found")
    if payment.status != "paid":
        raise PaymentStateError(f"Cannot refund payment from status '{payment.status}'")

    payment.status = "refunded"
    payment.failure_reason = reason
    commissions = db.query(Commission).filter(Commission.payment_id == payment.id).all()
    for row in commissions:
        row.status = "reversed"
    log_action(db, entity="payment_transactions", action="refund")
    db.commit()
    db.refresh(payment)
    return payment
