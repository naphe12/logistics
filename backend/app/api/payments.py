from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.enums import UserTypeEnum
from app.models.statuses import PaymentStatus
from app.schemas.payments import (
    CommissionOut,
    PaymentCreate,
    PaymentFailRequest,
    PaymentRefundRequest,
    PaymentInitiateRequest,
    PaymentOut,
)
from app.services.payment_service import (
    PaymentNotFoundError,
    PaymentStateError,
    PaymentValidationError,
    cancel_payment,
    confirm_payment,
    create_payment,
    fail_payment,
    get_payment,
    initiate_payment,
    list_commissions,
    list_payment_statuses,
    list_payments,
    refund_payment,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/statuses", response_model=list[str])
def list_payment_statuses_endpoint(
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    rows: list[PaymentStatus] = list_payment_statuses(db)
    return [row.code for row in rows]


@router.get("", response_model=list[PaymentOut])
def list_payments_endpoint(
    shipment_id: UUID | None = None,
    status: str | None = None,
    payer_phone: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    return list_payments(db, shipment_id=shipment_id, status=status, payer_phone=payer_phone)


@router.get("/commissions", response_model=list[CommissionOut])
def list_commissions_endpoint(
    shipment_id: UUID | None = None,
    payment_id: UUID | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    return list_commissions(db, shipment_id=shipment_id, payment_id=payment_id)


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment_endpoint(
    payment_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    payment = get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.post("", response_model=PaymentOut)
def create_payment_endpoint(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        return create_payment(db, payload)
    except PaymentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{payment_id}/initiate", response_model=PaymentOut)
def initiate_payment_endpoint(
    payment_id: UUID,
    payload: PaymentInitiateRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    try:
        return initiate_payment(db, payment_id, external_ref=payload.external_ref)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PaymentValidationError, PaymentStateError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{payment_id}/confirm", response_model=PaymentOut)
def confirm_payment_endpoint(
    payment_id: UUID,
    payload: PaymentInitiateRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    try:
        return confirm_payment(db, payment_id, external_ref=payload.external_ref)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PaymentValidationError, PaymentStateError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{payment_id}/fail", response_model=PaymentOut)
def fail_payment_endpoint(
    payment_id: UUID,
    payload: PaymentFailRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    try:
        return fail_payment(db, payment_id, reason=payload.reason)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PaymentValidationError, PaymentStateError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{payment_id}/cancel", response_model=PaymentOut)
def cancel_payment_endpoint(
    payment_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    try:
        return cancel_payment(db, payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PaymentValidationError, PaymentStateError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{payment_id}/refund", response_model=PaymentOut)
def refund_payment_endpoint(
    payment_id: UUID,
    payload: PaymentRefundRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    try:
        return refund_payment(db, payment_id, reason=payload.reason)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PaymentValidationError, PaymentStateError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
