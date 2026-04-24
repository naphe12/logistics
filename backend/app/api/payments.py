import csv
from io import StringIO
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.enums import UserTypeEnum
from app.models.users import User
from app.models.statuses import PaymentStatus
from app.schemas.payments import (
    CommissionOut,
    PaymentCreate,
    PaymentRefundHistoryOut,
    PaymentRefundPreviewOut,
    PaymentInvoicePageOut,
    PaymentInvoiceSummaryOut,
    PaymentListPageOut,
    PaymentWebhookPayload,
    PaymentWebhookResult,
    PaymentReconcileResult,
    PaymentReceiptOut,
    PaymentExtraUpdate,
    PaymentFailRequest,
    PaymentRefundRequest,
    PaymentInitiateRequest,
    PaymentOut,
)
from app.services.payment_service import (
    PaymentNotFoundError,
    PaymentSignatureError,
    PaymentStateError,
    PaymentValidationError,
    apply_payment_webhook,
    build_payment_receipt,
    cancel_payment,
    confirm_payment,
    create_payment,
    fail_payment,
    get_payment,
    get_payment_for_user,
    get_payment_refund_preview,
    get_invoice_summary,
    initiate_payment,
    list_payment_refund_history,
    list_invoice_lines,
    list_commissions,
    list_payment_statuses,
    list_payments,
    list_payments_page,
    reconcile_stuck_payments,
    refund_payment,
    simulate_provider_payment_webhook,
    update_payment_extra,
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
    extra_key: str | None = Query(default=None, min_length=1, max_length=120),
    extra_value: str | None = Query(default=None, min_length=0, max_length=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    return list_payments(
        db,
        shipment_id=shipment_id,
        status=status,
        payer_phone=payer_phone,
        extra_key=extra_key,
        extra_value=extra_value,
        current_user=current_user,
    )


@router.get("/page", response_model=PaymentListPageOut)
def list_payments_page_endpoint(
    shipment_id: UUID | None = None,
    status: str | None = None,
    payer_phone: str | None = None,
    extra_key: str | None = Query(default=None, min_length=1, max_length=120),
    extra_value: str | None = Query(default=None, min_length=0, max_length=500),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    return list_payments_page(
        db,
        shipment_id=shipment_id,
        status=status,
        payer_phone=payer_phone,
        extra_key=extra_key,
        extra_value=extra_value,
        current_user=current_user,
        offset=offset,
        limit=limit,
    )


@router.get("/commissions", response_model=list[CommissionOut])
def list_commissions_endpoint(
    shipment_id: UUID | None = None,
    payment_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    return list_commissions(db, shipment_id=shipment_id, payment_id=payment_id, current_user=current_user)


@router.get("/invoicing/summary", response_model=PaymentInvoiceSummaryOut)
def invoice_summary_endpoint(
    sender_phone: str | None = Query(default=None, min_length=8, max_length=20),
    sender_id: UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    include_refunded: bool = Query(default=True),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.business, UserTypeEnum.customer)
    ),
):
    scope_phone = sender_phone
    scope_sender_id = sender_id
    if current_user.user_type in {UserTypeEnum.business, UserTypeEnum.customer}:
        scope_phone = current_user.phone_e164
        scope_sender_id = current_user.id
    page = get_invoice_summary(
        db,
        sender_phone=scope_phone,
        sender_id=scope_sender_id,
        date_from=date_from,
        date_to=date_to,
        include_refunded=include_refunded,
        limit=limit,
    )
    return page["summary"]


@router.get("/invoicing/lines", response_model=PaymentInvoicePageOut)
def invoice_lines_endpoint(
    sender_phone: str | None = Query(default=None, min_length=8, max_length=20),
    sender_id: UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    include_refunded: bool = Query(default=True),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.business, UserTypeEnum.customer)
    ),
):
    scope_phone = sender_phone
    scope_sender_id = sender_id
    if current_user.user_type in {UserTypeEnum.business, UserTypeEnum.customer}:
        scope_phone = current_user.phone_e164
        scope_sender_id = current_user.id
    return get_invoice_summary(
        db,
        sender_phone=scope_phone,
        sender_id=scope_sender_id,
        date_from=date_from,
        date_to=date_to,
        include_refunded=include_refunded,
        limit=limit,
    )


@router.get("/invoicing/lines.csv")
def invoice_lines_csv_endpoint(
    sender_phone: str | None = Query(default=None, min_length=8, max_length=20),
    sender_id: UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    include_refunded: bool = Query(default=True),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.business, UserTypeEnum.customer)
    ),
):
    scope_phone = sender_phone
    scope_sender_id = sender_id
    if current_user.user_type in {UserTypeEnum.business, UserTypeEnum.customer}:
        scope_phone = current_user.phone_e164
        scope_sender_id = current_user.id
    lines = list_invoice_lines(
        db,
        sender_phone=scope_phone,
        sender_id=scope_sender_id,
        date_from=date_from,
        date_to=date_to,
        include_refunded=include_refunded,
        limit=limit,
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "payment_id",
            "shipment_id",
            "shipment_no",
            "payer_phone",
            "sender_phone",
            "external_ref",
            "provider",
            "status",
            "amount",
            "refunded_total",
            "net_amount",
            "created_at",
            "updated_at",
        ]
    )
    for row in lines:
        writer.writerow(
            [
                str(row["payment_id"]),
                str(row["shipment_id"]) if row["shipment_id"] else "",
                row["shipment_no"] or "",
                row["payer_phone"] or "",
                row["sender_phone"] or "",
                row["external_ref"] or "",
                row["provider"] or "",
                row["status"] or "",
                str(row["amount"]),
                str(row["refunded_total"]),
                str(row["net_amount"]),
                row["created_at"].isoformat() if row["created_at"] else "",
                row["updated_at"].isoformat() if row["updated_at"] else "",
            ]
        )
    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="invoice_lines.csv"'},
    )


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment_endpoint(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    payment = get_payment_for_user(db, payment_id, current_user=current_user)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.get("/{payment_id}/receipt", response_model=PaymentReceiptOut)
def get_payment_receipt_endpoint(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        if not get_payment_for_user(db, payment_id, current_user=current_user):
            raise PaymentNotFoundError("Payment not found")
        return build_payment_receipt(db, payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{payment_id}/receipt.txt", response_class=PlainTextResponse)
def download_payment_receipt_text_endpoint(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        if not get_payment_for_user(db, payment_id, current_user=current_user):
            raise PaymentNotFoundError("Payment not found")
        receipt = build_payment_receipt(db, payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    lines = [
        f"Receipt: {receipt['receipt_no']}",
        f"Payment ID: {receipt['payment_id']}",
        f"Shipment ID: {receipt['shipment_id'] or '-'}",
        f"Amount: {receipt['amount'] or '-'}",
        f"Status: {receipt['status'] or '-'}",
        f"Provider: {receipt['provider'] or '-'}",
        f"External Ref: {receipt['external_ref'] or '-'}",
        f"Payer Phone: {receipt['payer_phone'] or '-'}",
        f"Created At: {receipt['created_at'] or '-'}",
        f"Updated At: {receipt['updated_at'] or '-'}",
    ]
    commissions = receipt.get("commissions") or []
    if commissions:
        lines.append("Commissions:")
        for item in commissions:
            lines.append(
                f"- {item.commission_type or '-'} | {item.amount or '-'} | {item.status or '-'} | beneficiary={item.beneficiary_id or '-'}"
            )
    content = "\n".join(lines)
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="{receipt["receipt_no"]}.txt"'},
    )


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
        return refund_payment(
            db,
            payment_id,
            reason=payload.reason,
            amount=payload.amount,
            idempotency_key=payload.idempotency_key,
        )
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PaymentValidationError, PaymentStateError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{payment_id}/refund/preview", response_model=PaymentRefundPreviewOut)
def refund_preview_endpoint(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        if not get_payment_for_user(db, payment_id, current_user=current_user):
            raise PaymentNotFoundError("Payment not found")
        return get_payment_refund_preview(db, payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{payment_id}/refunds", response_model=PaymentRefundHistoryOut)
def refund_history_endpoint(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub, UserTypeEnum.customer)),
):
    try:
        if not get_payment_for_user(db, payment_id, current_user=current_user):
            raise PaymentNotFoundError("Payment not found")
        return list_payment_refund_history(db, payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{payment_id}/extra", response_model=PaymentOut)
def update_payment_extra_endpoint(
    payment_id: UUID,
    payload: PaymentExtraUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.agent, UserTypeEnum.hub)),
):
    try:
        return update_payment_extra(
            db,
            payment_id,
            extra=payload.extra,
            merge=payload.merge,
        )
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/webhooks/provider", response_model=PaymentWebhookResult)
async def provider_payment_webhook_endpoint(
    payload: PaymentWebhookPayload,
    request: Request,
    db: Session = Depends(get_db),
    x_payment_signature: str = Header(default="", alias="X-Payment-Signature"),
):
    raw_body = await request.body()
    try:
        return apply_payment_webhook(
            db,
            raw_body=raw_body,
            signature=x_payment_signature,
            event_id=payload.event_id,
            status=payload.status,
            reason=payload.reason,
            external_ref=payload.external_ref,
            payment_id=payload.payment_id,
            provider=payload.provider,
            payload=payload.payload,
        )
    except PaymentSignatureError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except PaymentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/webhooks/provider/simulate", response_model=PaymentWebhookResult)
def simulate_provider_payment_webhook_endpoint(
    payload: PaymentWebhookPayload,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    try:
        return simulate_provider_payment_webhook(
            db,
            event_id=payload.event_id,
            status=payload.status,
            reason=payload.reason,
            external_ref=payload.external_ref,
            payment_id=payload.payment_id,
            provider=payload.provider,
            payload=payload.payload,
        )
    except PaymentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/reconcile/stale", response_model=PaymentReconcileResult)
def reconcile_stale_payments_endpoint(
    stale_minutes: int | None = Query(default=None, ge=1, le=1440),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    _user=Depends(require_roles(UserTypeEnum.admin, UserTypeEnum.hub)),
):
    return reconcile_stuck_payments(
        db,
        stale_minutes=stale_minutes,
        limit=limit,
    )
