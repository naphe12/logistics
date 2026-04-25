import hashlib
import hmac
from decimal import Decimal, ROUND_HALF_UP
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config import (
    COMMISSION_RELAY_RATE,
    COMMISSION_TRANSPORT_RATE,
    PAYMENT_RECONCILE_STALE_MINUTES,
    PAYMENT_WEBHOOK_SECRET,
)
from app.models.incidents import Commission
from app.models.payments import PaymentTransaction
from app.models.shipments import Shipment
from app.models.statuses import PaymentStatus
from app.models.shipments import Manifest, ManifestShipment
from app.models.transport import Trip
from app.models.users import User
from app.schemas.payments import PaymentCreate
from app.services.audit_service import log_action
from app.enums import UserTypeEnum
from app.services.notification_service import queue_and_send_sms
from app.services.payment_provider_service import (
    build_provider_initiation_metadata,
    normalize_provider,
    provider_status_to_internal,
    validate_supported_provider,
)


class PaymentError(Exception):
    pass


class PaymentNotFoundError(PaymentError):
    pass


class PaymentStateError(PaymentError):
    pass


class PaymentValidationError(PaymentError):
    pass


class PaymentWebhookError(PaymentError):
    pass


class PaymentSignatureError(PaymentWebhookError):
    pass


def _to_money(value: Decimal | float) -> Decimal:
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def list_payment_statuses(db: Session) -> list[PaymentStatus]:
    return db.query(PaymentStatus).order_by(PaymentStatus.code.asc()).all()


def _apply_payment_visibility(query, current_user: User | None):
    if not current_user:
        return query
    if current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        return query.join(
            Shipment,
            Shipment.id == PaymentTransaction.shipment_id,
        ).filter(
            or_(
                Shipment.sender_id == current_user.id,
                Shipment.sender_phone == current_user.phone_e164,
                Shipment.receiver_phone == current_user.phone_e164,
                PaymentTransaction.payer_phone == current_user.phone_e164,
            )
        )
    return query


def list_payments(
    db: Session,
    *,
    shipment_id: UUID | None = None,
    status: str | None = None,
    payer_phone: str | None = None,
    extra_key: str | None = None,
    extra_value: str | None = None,
    current_user: User | None = None,
) -> list[PaymentTransaction]:
    query = _apply_payment_visibility(db.query(PaymentTransaction), current_user)
    if shipment_id is not None:
        query = query.filter(PaymentTransaction.shipment_id == shipment_id)
    if status:
        query = query.filter(PaymentTransaction.status == status)
    if payer_phone:
        query = query.filter(PaymentTransaction.payer_phone == payer_phone)
    if extra_key and extra_value is not None:
        query = query.filter(PaymentTransaction.extra[extra_key].astext == extra_value)
    return query.order_by(PaymentTransaction.created_at.desc()).all()


def list_payments_page(
    db: Session,
    *,
    shipment_id: UUID | None = None,
    status: str | None = None,
    payer_phone: str | None = None,
    extra_key: str | None = None,
    extra_value: str | None = None,
    current_user: User | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    offset = max(0, offset)
    limit = max(1, min(limit, 200))
    query = _apply_payment_visibility(db.query(PaymentTransaction), current_user)
    if shipment_id is not None:
        query = query.filter(PaymentTransaction.shipment_id == shipment_id)
    if status:
        query = query.filter(PaymentTransaction.status == status)
    if payer_phone:
        query = query.filter(PaymentTransaction.payer_phone == payer_phone)
    if extra_key and extra_value is not None:
        query = query.filter(PaymentTransaction.extra[extra_key].astext == extra_value)
    total = query.count()
    items = query.order_by(PaymentTransaction.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


def get_payment(db: Session, payment_id: UUID) -> PaymentTransaction | None:
    return db.query(PaymentTransaction).filter(PaymentTransaction.id == payment_id).first()


def get_payment_for_user(db: Session, payment_id: UUID, current_user: User | None = None) -> PaymentTransaction | None:
    query = _apply_payment_visibility(db.query(PaymentTransaction), current_user)
    return query.filter(PaymentTransaction.id == payment_id).first()


def get_payment_by_external_ref(db: Session, external_ref: str) -> PaymentTransaction | None:
    return db.query(PaymentTransaction).filter(PaymentTransaction.external_ref == external_ref).first()


def list_commissions(
    db: Session,
    *,
    shipment_id: UUID | None = None,
    payment_id: UUID | None = None,
    current_user: User | None = None,
) -> list[Commission]:
    query = db.query(Commission)
    if current_user and current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        query = query.join(Shipment, Shipment.id == Commission.shipment_id).filter(
            or_(
                Shipment.sender_id == current_user.id,
                Shipment.sender_phone == current_user.phone_e164,
                Shipment.receiver_phone == current_user.phone_e164,
            )
        )
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


def _verify_webhook_signature(raw_body: bytes, signature: str) -> None:
    if not PAYMENT_WEBHOOK_SECRET:
        raise PaymentSignatureError("PAYMENT_WEBHOOK_SECRET is not configured")
    expected = hmac.new(
        PAYMENT_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature.strip()):
        raise PaymentSignatureError("Invalid webhook signature")


def _send_payment_status_ack_sms(db: Session, payment: PaymentTransaction) -> None:
    phone = (payment.payer_phone or "").strip()
    if not phone:
        return
    shipment_no = None
    if payment.shipment_id:
        shipment = db.query(Shipment).filter(Shipment.id == payment.shipment_id).first()
        shipment_no = shipment.shipment_no if shipment else None

    status = (payment.status or "pending").upper()
    ref = payment.external_ref or str(payment.id)
    if status == "PAID":
        message = f"Paiement confirme. Colis: {shipment_no or '-'} Ref: {ref}."
    elif status == "FAILED":
        message = f"Paiement echoue. Colis: {shipment_no or '-'} Ref: {ref}."
    elif status == "CANCELLED":
        message = f"Paiement annule. Colis: {shipment_no or '-'} Ref: {ref}."
    elif status == "REFUNDED":
        message = f"Paiement rembourse. Colis: {shipment_no or '-'} Ref: {ref}."
    else:
        return
    queue_and_send_sms(db, phone, message, background_tasks=None, respect_preferences=True)


def _apply_webhook_idempotence(payment: PaymentTransaction, event_id: str) -> bool:
    extra = payment.extra if isinstance(payment.extra, dict) else {}
    events = extra.get("webhook_events")
    if not isinstance(events, list):
        events = []
    if event_id in events:
        return False
    events.append(event_id)
    extra["webhook_events"] = events[-100:]
    payment.extra = extra
    return True


def _apply_webhook_update(
    db: Session,
    *,
    target: PaymentTransaction,
    event_id: str,
    status: str,
    reason: str | None = None,
    external_ref: str | None = None,
    provider: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not _apply_webhook_idempotence(target, event_id):
        db.commit()
        return {
            "accepted": True,
            "applied": False,
            "payment_id": target.id,
            "status": target.status,
            "detail": "Webhook event already processed",
        }

    effective_provider = provider or target.provider
    if provider:
        target.provider = normalize_provider(provider)
    try:
        mapped_status = provider_status_to_internal(effective_provider, status)
    except ValueError as exc:
        raise PaymentValidationError(str(exc)) from exc
    if external_ref:
        target.external_ref = external_ref

    if mapped_status == "paid":
        target.status = "paid"
        target.failure_reason = None
        _ensure_commissions_for_paid_payment(db, target)
    elif mapped_status in {"failed", "cancelled", "refunded"}:
        target.status = mapped_status
        target.failure_reason = reason or target.failure_reason
    else:
        target.status = mapped_status

    if payload:
        extra = target.extra if isinstance(target.extra, dict) else {}
        extra["last_webhook_payload"] = payload
        target.extra = extra

    log_action(db, entity="payment_transactions", action="webhook_update")
    db.commit()
    db.refresh(target)

    # Customer-facing acknowledgement for terminal provider updates.
    _send_payment_status_ack_sms(db, target)

    return {
        "accepted": True,
        "applied": True,
        "payment_id": target.id,
        "status": target.status,
        "detail": "Webhook processed",
    }


def create_payment(db: Session, payload: PaymentCreate) -> PaymentTransaction:
    shipment = db.query(Shipment).filter(Shipment.id == payload.shipment_id).first()
    if not shipment:
        raise PaymentValidationError("Shipment not found")
    _require_status_exists(db, "pending")
    try:
        provider = validate_supported_provider(payload.provider)
    except ValueError as exc:
        raise PaymentValidationError(str(exc)) from exc

    payment = PaymentTransaction(
        shipment_id=payload.shipment_id,
        amount=payload.amount,
        payer_phone=payload.payer_phone,
        payment_stage=payload.payment_stage,
        provider=provider,
        status="pending",
        extra=payload.extra,
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
    extra = payment.extra if isinstance(payment.extra, dict) else {}
    extra["provider_initiation"] = build_provider_initiation_metadata(
        provider=payment.provider,
        external_ref=payment.external_ref,
        amount=payment.amount,
        payer_phone=payment.payer_phone,
    )
    payment.extra = extra
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


def _read_refund_events(payment: PaymentTransaction) -> list[dict[str, Any]]:
    extra = payment.extra if isinstance(payment.extra, dict) else {}
    events = extra.get("refund_events")
    if not isinstance(events, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in events:
        if isinstance(item, dict) and "amount" in item and "reason" in item and "refunded_at" in item:
            normalized.append(item)
    return normalized


def _sum_refunded(events: list[dict[str, Any]]) -> Decimal:
    total = Decimal("0")
    for item in events:
        amount_raw = item.get("amount", "0")
        total += _to_money(Decimal(str(amount_raw)))
    return _to_money(total)


def get_payment_refund_preview(db: Session, payment_id: UUID) -> dict[str, Any]:
    payment = get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError("Payment not found")
    total_amount = _to_money(Decimal(str(payment.amount or 0)))
    events = _read_refund_events(payment)
    refunded_total = _sum_refunded(events)
    refundable_balance = _to_money(max(Decimal("0"), total_amount - refunded_total))
    return {
        "payment_id": payment.id,
        "status": payment.status,
        "total_amount": total_amount,
        "refunded_total": refunded_total,
        "refundable_balance": refundable_balance,
        "is_fully_refunded": refundable_balance == Decimal("0"),
    }


def list_payment_refund_history(db: Session, payment_id: UUID) -> dict[str, Any]:
    payment = get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError("Payment not found")
    preview = get_payment_refund_preview(db, payment_id)
    events_raw = _read_refund_events(payment)
    events: list[dict[str, Any]] = []
    for item in events_raw:
        refunded_at_raw = item.get("refunded_at")
        refunded_at = datetime.fromisoformat(refunded_at_raw) if isinstance(refunded_at_raw, str) else datetime.now(UTC)
        events.append(
            {
                "idempotency_key": item.get("idempotency_key"),
                "amount": _to_money(Decimal(str(item.get("amount", "0")))),
                "reason": str(item.get("reason")),
                "refunded_at": refunded_at,
            }
        )
    return {
        "payment_id": payment.id,
        "total_amount": preview["total_amount"],
        "refunded_total": preview["refunded_total"],
        "refundable_balance": preview["refundable_balance"],
        "events": events,
    }


def refund_payment(
    db: Session,
    payment_id: UUID,
    reason: str,
    *,
    amount: Decimal | None = None,
    idempotency_key: str | None = None,
) -> PaymentTransaction:
    _require_status_exists(db, "refunded")
    payment = get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError("Payment not found")
    if payment.status not in {"paid", "refunded"}:
        raise PaymentStateError(f"Cannot refund payment from status '{payment.status}'")

    extra = payment.extra if isinstance(payment.extra, dict) else {}
    events = _read_refund_events(payment)
    if idempotency_key:
        for item in events:
            if item.get("idempotency_key") == idempotency_key:
                return payment

    preview = get_payment_refund_preview(db, payment_id)
    refundable_balance = preview["refundable_balance"]
    if refundable_balance <= Decimal("0"):
        raise PaymentStateError("Payment already fully refunded")

    requested_amount = _to_money(amount if amount is not None else refundable_balance)
    if requested_amount <= Decimal("0"):
        raise PaymentValidationError("Refund amount must be greater than 0")
    if requested_amount > refundable_balance:
        raise PaymentValidationError(
            f"Refund amount exceeds refundable balance ({refundable_balance})"
        )

    event = {
        "idempotency_key": idempotency_key,
        "amount": str(requested_amount),
        "reason": reason,
        "refunded_at": datetime.now(UTC).isoformat(),
    }
    events.append(event)
    extra["refund_events"] = events[-200:]

    new_refunded_total = _sum_refunded(events)
    total_amount = _to_money(Decimal(str(payment.amount or 0)))
    is_full_refund = new_refunded_total >= total_amount

    if is_full_refund:
        payment.status = "refunded"
        commissions = db.query(Commission).filter(Commission.payment_id == payment.id).all()
        for row in commissions:
            row.status = "reversed"
        action = "refund_full"
    else:
        payment.status = "paid"
        extra["refund_state"] = "partial"
        commissions = db.query(Commission).filter(Commission.payment_id == payment.id).all()
        for row in commissions:
            if row.status == "accrued":
                row.status = "partially_reversed"
        action = "refund_partial"

    payment.failure_reason = reason
    payment.extra = extra
    log_action(db, entity="payment_transactions", action=action)
    db.commit()
    db.refresh(payment)
    return payment


def update_payment_extra(
    db: Session,
    payment_id: UUID,
    *,
    extra: dict,
    merge: bool = True,
) -> PaymentTransaction:
    payment = get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError("Payment not found")

    if merge and isinstance(payment.extra, dict):
        payment.extra = {**payment.extra, **extra}
    else:
        payment.extra = extra

    log_action(db, entity="payment_transactions", action="extra_update")
    db.commit()
    db.refresh(payment)
    return payment


def apply_payment_webhook(
    db: Session,
    *,
    raw_body: bytes,
    signature: str,
    event_id: str,
    status: str,
    reason: str | None = None,
    external_ref: str | None = None,
    payment_id: UUID | None = None,
    provider: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _verify_webhook_signature(raw_body, signature)
    target: PaymentTransaction | None = None
    if payment_id is not None:
        target = get_payment(db, payment_id)
    if target is None and external_ref:
        target = get_payment_by_external_ref(db, external_ref)
    if target is None:
        return {
            "accepted": True,
            "applied": False,
            "payment_id": None,
            "status": None,
            "detail": "Payment not found for webhook reference",
        }
    return _apply_webhook_update(
        db,
        target=target,
        event_id=event_id,
        status=status,
        reason=reason,
        external_ref=external_ref,
        provider=provider,
        payload=payload,
    )


def simulate_provider_payment_webhook(
    db: Session,
    *,
    event_id: str,
    status: str,
    reason: str | None = None,
    external_ref: str | None = None,
    payment_id: UUID | None = None,
    provider: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target: PaymentTransaction | None = None
    if payment_id is not None:
        target = get_payment(db, payment_id)
    if target is None and external_ref:
        target = get_payment_by_external_ref(db, external_ref)
    if target is None:
        return {
            "accepted": True,
            "applied": False,
            "payment_id": None,
            "status": None,
            "detail": "Payment not found for webhook reference",
        }
    return _apply_webhook_update(
        db,
        target=target,
        event_id=event_id,
        status=status,
        reason=reason,
        external_ref=external_ref,
        provider=provider,
        payload=payload,
    )


def reconcile_stuck_payments(
    db: Session,
    *,
    stale_minutes: int | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    minutes = stale_minutes if stale_minutes is not None else PAYMENT_RECONCILE_STALE_MINUTES
    minutes = max(1, min(minutes, 24 * 60))
    limit = max(1, min(limit, 2000))
    cutoff = datetime.now(UTC) - timedelta(minutes=minutes)
    rows = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.status == "processing",
            PaymentTransaction.updated_at <= cutoff,
        )
        .order_by(PaymentTransaction.updated_at.asc())
        .limit(limit)
        .all()
    )
    failed_ids: list[UUID] = []
    for row in rows:
        row.status = "failed"
        row.failure_reason = "Reconciliation timeout: provider callback not received"
        failed_ids.append(row.id)

    if rows:
        log_action(
            db,
            entity="payment_transactions",
            action="reconcile_timeout_fail",
            status_code=len(rows),
        )
    db.commit()
    return {
        "scanned": len(rows),
        "updated": len(rows),
        "failed_ids": failed_ids,
    }


def build_payment_receipt(db: Session, payment_id: UUID) -> dict[str, Any]:
    payment = get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError("Payment not found")
    commissions = db.query(Commission).filter(Commission.payment_id == payment.id).order_by(Commission.created_at.asc()).all()
    paid_at = payment.updated_at if payment.status == "paid" else None
    refund_history = list_payment_refund_history(db, payment.id)
    return {
        "receipt_no": f"RCT-{str(payment.id).split('-')[0].upper()}",
        "payment_id": payment.id,
        "shipment_id": payment.shipment_id,
        "external_ref": payment.external_ref,
        "provider": payment.provider,
        "payer_phone": payment.payer_phone,
        "amount": payment.amount,
        "status": payment.status,
        "payment_stage": payment.payment_stage,
        "paid_at": paid_at,
        "created_at": payment.created_at,
        "updated_at": payment.updated_at,
        "refunded_total": refund_history["refunded_total"],
        "refundable_balance": refund_history["refundable_balance"],
        "commissions": commissions,
        "refund_events": [
            {
                "idempotency_key": item.get("idempotency_key"),
                "amount": str(item.get("amount")),
                "reason": item.get("reason"),
                "refunded_at": item.get("refunded_at").isoformat() if item.get("refunded_at") else None,
            }
            for item in refund_history["events"]
        ],
    }


def _invoicing_base_query(
    db: Session,
    *,
    sender_phone: str | None = None,
    sender_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    query = db.query(PaymentTransaction, Shipment).join(
        Shipment,
        Shipment.id == PaymentTransaction.shipment_id,
    )
    if sender_phone:
        query = query.filter(Shipment.sender_phone == sender_phone)
    if sender_id is not None:
        query = query.filter(Shipment.sender_id == sender_id)
    if date_from is not None:
        query = query.filter(PaymentTransaction.updated_at >= date_from)
    if date_to is not None:
        query = query.filter(PaymentTransaction.updated_at <= date_to)
    return query


def list_invoice_lines(
    db: Session,
    *,
    sender_phone: str | None = None,
    sender_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_refunded: bool = True,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 5000))
    query = _invoicing_base_query(
        db,
        sender_phone=sender_phone,
        sender_id=sender_id,
        date_from=date_from,
        date_to=date_to,
    )
    if include_refunded:
        query = query.filter(PaymentTransaction.status.in_(["paid", "refunded"]))
    else:
        query = query.filter(PaymentTransaction.status == "paid")

    rows = (
        query.order_by(PaymentTransaction.updated_at.desc(), PaymentTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
    lines: list[dict[str, Any]] = []
    for payment, shipment in rows:
        total_amount = _to_money(Decimal(str(payment.amount or 0)))
        events = _read_refund_events(payment)
        refunded_total = _sum_refunded(events)
        net_amount = _to_money(max(Decimal("0"), total_amount - refunded_total))
        lines.append(
            {
                "payment_id": payment.id,
                "shipment_id": payment.shipment_id,
                "shipment_no": shipment.shipment_no if shipment else None,
                "payer_phone": payment.payer_phone,
                "sender_phone": shipment.sender_phone if shipment else None,
                "external_ref": payment.external_ref,
                "provider": payment.provider,
                "status": payment.status,
                "amount": total_amount,
                "refunded_total": refunded_total,
                "net_amount": net_amount,
                "created_at": payment.created_at,
                "updated_at": payment.updated_at,
            }
        )
    return lines


def get_invoice_summary(
    db: Session,
    *,
    sender_phone: str | None = None,
    sender_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_refunded: bool = True,
    limit: int = 1000,
) -> dict[str, Any]:
    lines = list_invoice_lines(
        db,
        sender_phone=sender_phone,
        sender_id=sender_id,
        date_from=date_from,
        date_to=date_to,
        include_refunded=include_refunded,
        limit=limit,
    )
    gross_amount = Decimal("0")
    refunded_amount = Decimal("0")
    net_amount = Decimal("0")
    for line in lines:
        gross_amount += Decimal(str(line["amount"]))
        refunded_amount += Decimal(str(line["refunded_total"]))
        net_amount += Decimal(str(line["net_amount"]))

    summary = {
        "total_payments": len(lines),
        "gross_amount": _to_money(gross_amount),
        "refunded_amount": _to_money(refunded_amount),
        "net_amount": _to_money(net_amount),
        "currency": "BIF",
        "date_from": date_from,
        "date_to": date_to,
        "sender_phone": sender_phone,
        "sender_id": sender_id,
    }
    return {
        "summary": summary,
        "lines": lines,
    }
