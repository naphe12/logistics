from uuid import UUID
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.incidents import Claim, Incident, IncidentUpdate
from app.models.shipments import Shipment
from app.models.statuses import IncidentStatus
from app.models.users import User
from app.enums import UserTypeEnum
from sqlalchemy import or_
from app.schemas.incidents import ClaimCreate, IncidentCreate
from app.services.audit_service import log_action
from app.services.insurance_service import InsuranceValidationError, validate_claim_policy
from app.services.notification_service import queue_and_send_sms
from app.config import (
    INSURANCE_CLAIM_REVIEW_SLA_HOURS,
    CLAIMS_ESCALATION_NOTIFY_ROLES,
    CLAIMS_ANTIFRAUD_HIGH_RISK_THRESHOLD,
)


class IncidentError(Exception):
    pass


class IncidentNotFoundError(IncidentError):
    pass


class IncidentValidationError(IncidentError):
    pass


def _to_decimal(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _user_types_from_config(raw_roles: list[str]) -> list[UserTypeEnum]:
    result: list[UserTypeEnum] = []
    for raw in raw_roles:
        normalized = (raw or "").strip().lower()
        if not normalized:
            continue
        try:
            result.append(UserTypeEnum(normalized))
        except ValueError:
            continue
    return result


def _compute_claim_risk(
    db: Session,
    *,
    shipment: Shipment,
    claim_type: str,
    amount_requested: Decimal,
    proof_urls: list[str] | None,
    reason: str,
) -> tuple[Decimal, list[str]]:
    score = Decimal("0")
    flags: list[str] = []

    coverage = _to_decimal(shipment.coverage_amount)
    declared = _to_decimal(shipment.declared_value)
    insurance_fee = _to_decimal(shipment.insurance_fee)

    if insurance_fee <= 0:
        score += Decimal("15")
        flags.append("uninsured_or_zero_premium")

    baseline = coverage if coverage > 0 else declared
    if baseline > 0:
        ratio = amount_requested / baseline
        if ratio >= Decimal("0.90"):
            score += Decimal("25")
            flags.append("high_requested_to_coverage_ratio")
        elif ratio >= Decimal("0.70"):
            score += Decimal("15")
            flags.append("elevated_requested_to_coverage_ratio")
    else:
        score += Decimal("20")
        flags.append("missing_value_baseline")

    clean_proofs = [item for item in (proof_urls or []) if item and item.strip()]
    if not clean_proofs:
        score += Decimal("10")
        flags.append("missing_proof")

    if len((reason or "").strip()) < 20:
        score += Decimal("10")
        flags.append("short_reason")

    if (claim_type or "").strip().lower() == "lost":
        score += Decimal("10")
        flags.append("loss_claim")

    if shipment.created_at:
        age_hours = (datetime.now(UTC) - shipment.created_at).total_seconds() / 3600
        if age_hours <= 2:
            score += Decimal("15")
            flags.append("very_early_claim")

    recent_sender_claims = 0
    if shipment.sender_phone:
        since = datetime.now(UTC) - timedelta(days=30)
        recent_sender_claims = (
            db.query(Claim)
            .join(Shipment, Shipment.id == Claim.shipment_id)
            .filter(
                Shipment.sender_phone == shipment.sender_phone,
                Claim.created_at >= since,
            )
            .count()
        )
        if recent_sender_claims >= 3:
            score += Decimal("20")
            flags.append("sender_high_claim_frequency_30d")
        elif recent_sender_claims == 2:
            score += Decimal("10")
            flags.append("sender_repeat_claims_30d")

    if score > Decimal("100"):
        score = Decimal("100")
    return score.quantize(Decimal("0.01")), flags


def list_incident_statuses(db: Session) -> list[IncidentStatus]:
    return db.query(IncidentStatus).order_by(IncidentStatus.code.asc()).all()


def _apply_incident_visibility(query, current_user: User | None):
    if not current_user:
        return query
    if current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        return query.join(Shipment, Shipment.id == Incident.shipment_id).filter(
            or_(
                Shipment.sender_id == current_user.id,
                Shipment.sender_phone == current_user.phone_e164,
                Shipment.receiver_phone == current_user.phone_e164,
            )
        )
    return query


def _require_incident_status_exists(db: Session, status_code: str) -> None:
    exists = db.query(IncidentStatus.code).filter(IncidentStatus.code == status_code).first()
    if not exists:
        raise IncidentValidationError(f"Unknown incident status: {status_code}")


def list_incidents(
    db: Session,
    *,
    shipment_id: UUID | None = None,
    status: str | None = None,
    incident_type: str | None = None,
    extra_key: str | None = None,
    extra_value: str | None = None,
    current_user: User | None = None,
) -> list[Incident]:
    query = _apply_incident_visibility(db.query(Incident), current_user)
    if shipment_id is not None:
        query = query.filter(Incident.shipment_id == shipment_id)
    if status:
        query = query.filter(Incident.status == status)
    if incident_type:
        query = query.filter(Incident.incident_type == incident_type)
    if extra_key and extra_value is not None:
        query = query.filter(Incident.extra[extra_key].astext == extra_value)
    return query.order_by(Incident.created_at.desc()).all()


def list_incidents_page(
    db: Session,
    *,
    shipment_id: UUID | None = None,
    status: str | None = None,
    incident_type: str | None = None,
    extra_key: str | None = None,
    extra_value: str | None = None,
    current_user: User | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    offset = max(0, offset)
    limit = max(1, min(limit, 200))
    query = _apply_incident_visibility(db.query(Incident), current_user)
    if shipment_id is not None:
        query = query.filter(Incident.shipment_id == shipment_id)
    if status:
        query = query.filter(Incident.status == status)
    if incident_type:
        query = query.filter(Incident.incident_type == incident_type)
    if extra_key and extra_value is not None:
        query = query.filter(Incident.extra[extra_key].astext == extra_value)
    total = query.count()
    items = query.order_by(Incident.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


def get_incident(db: Session, incident_id: UUID, current_user: User | None = None) -> Incident | None:
    query = _apply_incident_visibility(db.query(Incident), current_user)
    return query.filter(Incident.id == incident_id).first()


def create_incident(db: Session, payload: IncidentCreate, current_user: User | None = None) -> Incident:
    shipment = db.query(Shipment).filter(Shipment.id == payload.shipment_id).first()
    if not shipment:
        raise IncidentValidationError("Shipment not found")
    if current_user and current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        is_owner = (
            shipment.sender_id == current_user.id
            or shipment.sender_phone == current_user.phone_e164
            or shipment.receiver_phone == current_user.phone_e164
        )
        if not is_owner:
            raise IncidentValidationError("Not allowed for this shipment")
    _require_incident_status_exists(db, "open")

    incident = Incident(
        shipment_id=payload.shipment_id,
        incident_type=payload.incident_type,
        description=payload.description,
        status="open",
        extra=payload.extra,
    )
    db.add(incident)
    log_action(db, entity="incidents", action="create")
    db.commit()
    db.refresh(incident)
    return incident


def update_incident_status(db: Session, incident_id: UUID, status: str) -> Incident:
    _require_incident_status_exists(db, status)
    incident = get_incident(db, incident_id)
    if not incident:
        raise IncidentNotFoundError("Incident not found")
    incident.status = status
    log_action(db, entity="incidents", action="status_update")
    db.commit()
    db.refresh(incident)
    return incident


def add_incident_update(db: Session, incident_id: UUID, message: str) -> IncidentUpdate:
    incident = get_incident(db, incident_id)
    if not incident:
        raise IncidentNotFoundError("Incident not found")
    row = IncidentUpdate(incident_id=incident_id, message=message)
    db.add(row)
    log_action(db, entity="incident_updates", action="add")
    db.commit()
    db.refresh(row)
    return row


def list_incident_updates(db: Session, incident_id: UUID, current_user: User | None = None) -> list[IncidentUpdate]:
    incident = get_incident(db, incident_id, current_user=current_user)
    if not incident:
        raise IncidentNotFoundError("Incident not found")
    return (
        db.query(IncidentUpdate)
        .filter(IncidentUpdate.incident_id == incident_id)
        .order_by(IncidentUpdate.created_at.desc())
        .all()
    )


def create_claim(db: Session, payload: ClaimCreate, current_user: User | None = None) -> Claim:
    incident = get_incident(db, payload.incident_id, current_user=current_user)
    if not incident:
        raise IncidentValidationError("Incident not found")
    if incident.shipment_id != payload.shipment_id:
        raise IncidentValidationError("Claim shipment does not match incident shipment")
    shipment = db.query(Shipment).filter(Shipment.id == payload.shipment_id).first()
    if not shipment:
        raise IncidentValidationError("Shipment not found")
    claim_type = payload.claim_type or incident.incident_type or "other"
    requested_amount = payload.amount_requested if payload.amount_requested is not None else payload.amount
    if requested_amount is None:
        raise IncidentValidationError("amount_requested is required")
    try:
        eligible_ceiling = validate_claim_policy(
            shipment=shipment,
            claim_type=claim_type,
            amount_requested=requested_amount,
            proof_urls=payload.proof_urls,
        )
    except InsuranceValidationError as exc:
        raise IncidentValidationError(str(exc)) from exc
    risk_score, risk_flags = _compute_claim_risk(
        db,
        shipment=shipment,
        claim_type=claim_type,
        amount_requested=requested_amount,
        proof_urls=payload.proof_urls,
        reason=payload.reason,
    )
    high_risk = risk_score >= Decimal(str(CLAIMS_ANTIFRAUD_HIGH_RISK_THRESHOLD))

    claim = Claim(
        incident_id=payload.incident_id,
        shipment_id=payload.shipment_id,
        amount=requested_amount,
        amount_requested=requested_amount,
        amount_approved=None,
        claim_type=claim_type,
        proof_urls=payload.proof_urls,
        risk_score=risk_score,
        risk_flags=risk_flags,
        status="submitted",
        reason=payload.reason,
    )
    db.add(
        IncidentUpdate(
            incident_id=payload.incident_id,
            message=(
                f"Claim submitted ({claim_type}), requested={requested_amount}, "
                f"eligible_ceiling={eligible_ceiling}."
            ),
        )
    )
    if high_risk:
        db.add(
            IncidentUpdate(
                incident_id=payload.incident_id,
                message=(
                    f"Fraud risk alert: score={risk_score} "
                    f"flags={', '.join(risk_flags) if risk_flags else 'none'}."
                ),
            )
        )
    db.add(claim)
    log_action(db, entity="claims", action="create")
    db.commit()
    db.refresh(claim)
    return claim


def list_claims(
    db: Session,
    *,
    incident_id: UUID | None = None,
    shipment_id: UUID | None = None,
    status: str | None = None,
    current_user: User | None = None,
) -> list[Claim]:
    query = db.query(Claim)
    if current_user and current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        query = query.join(Shipment, Shipment.id == Claim.shipment_id).filter(
            or_(
                Shipment.sender_id == current_user.id,
                Shipment.sender_phone == current_user.phone_e164,
                Shipment.receiver_phone == current_user.phone_e164,
            )
        )
    if incident_id is not None:
        query = query.filter(Claim.incident_id == incident_id)
    if shipment_id is not None:
        query = query.filter(Claim.shipment_id == shipment_id)
    if status:
        query = query.filter(Claim.status == status)
    return query.order_by(Claim.created_at.desc()).all()


def list_claims_page(
    db: Session,
    *,
    incident_id: UUID | None = None,
    shipment_id: UUID | None = None,
    status: str | None = None,
    current_user: User | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    offset = max(0, offset)
    limit = max(1, min(limit, 200))
    query = db.query(Claim)
    if current_user and current_user.user_type in {UserTypeEnum.customer, UserTypeEnum.business}:
        query = query.join(Shipment, Shipment.id == Claim.shipment_id).filter(
            or_(
                Shipment.sender_id == current_user.id,
                Shipment.sender_phone == current_user.phone_e164,
                Shipment.receiver_phone == current_user.phone_e164,
            )
        )
    if incident_id is not None:
        query = query.filter(Claim.incident_id == incident_id)
    if shipment_id is not None:
        query = query.filter(Claim.shipment_id == shipment_id)
    if status:
        query = query.filter(Claim.status == status)
    total = query.count()
    items = query.order_by(Claim.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


def update_claim_status(
    db: Session,
    claim_id: UUID,
    *,
    status: str,
    amount_approved: Decimal | None = None,
    resolution_note: str | None = None,
    refunded_payment_id: UUID | None = None,
) -> Claim:
    allowed = {"submitted", "reviewing", "approved", "rejected", "paid"}
    if status not in allowed:
        raise IncidentValidationError(f"Unsupported claim status: {status}")
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise IncidentNotFoundError("Claim not found")
    allowed_transitions = {
        "submitted": {"reviewing", "rejected"},
        "reviewing": {"approved", "rejected"},
        "approved": {"paid", "rejected"},
        "rejected": set(),
        "paid": set(),
    }
    current_status = (claim.status or "submitted").strip().lower()
    if status not in allowed_transitions.get(current_status, set()) and status != current_status:
        raise IncidentValidationError(f"Invalid claim transition: {current_status} -> {status}")

    if amount_approved is not None:
        if status not in {"approved", "paid"}:
            raise IncidentValidationError("amount_approved is only allowed for approved/paid statuses")
        requested = claim.amount_requested or claim.amount
        if requested is not None and amount_approved > requested:
            raise IncidentValidationError("amount_approved cannot exceed amount_requested")
        claim.amount_approved = amount_approved
    elif status in {"approved", "paid"} and claim.amount_approved is None:
        claim.amount_approved = claim.amount_requested or claim.amount

    claim.status = status
    if resolution_note is not None:
        claim.resolution_note = resolution_note
    if refunded_payment_id is not None:
        claim.refunded_payment_id = refunded_payment_id
    if status == "paid" and claim.amount_approved is None:
        raise IncidentValidationError("Cannot mark paid without approved amount")
    log_action(db, entity="claims", action="status_update")
    db.commit()
    db.refresh(claim)
    return claim


def update_incident_extra(
    db: Session,
    incident_id: UUID,
    *,
    extra: dict,
    merge: bool = True,
) -> Incident:
    incident = get_incident(db, incident_id)
    if not incident:
        raise IncidentNotFoundError("Incident not found")

    if merge and isinstance(incident.extra, dict):
        incident.extra = {**incident.extra, **extra}
    else:
        incident.extra = extra

    log_action(db, entity="incidents", action="extra_update")
    db.commit()
    db.refresh(incident)
    return incident


def get_incident_dashboard(
    db: Session,
    *,
    stale_hours: int = 24,
) -> dict:
    stale_hours = max(1, min(stale_hours, 24 * 30))
    cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)

    total = db.query(Incident).count()
    open_count = db.query(Incident).filter(Incident.status == "open").count()
    investigating_count = db.query(Incident).filter(Incident.status == "investigating").count()
    resolved_count = db.query(Incident).filter(Incident.status == "resolved").count()
    stale_open_count = (
        db.query(Incident)
        .filter(
            Incident.status.in_(["open", "investigating"]),
            Incident.created_at <= cutoff,
        )
        .count()
    )
    type_rows = (
        db.query(func.coalesce(Incident.incident_type, "unknown"), func.count(Incident.id))
        .group_by(Incident.incident_type)
        .all()
    )
    by_type = {str(incident_type): int(count) for incident_type, count in type_rows}

    return {
        "total": total,
        "open_count": open_count,
        "investigating_count": investigating_count,
        "resolved_count": resolved_count,
        "stale_open_count": stale_open_count,
        "by_type": by_type,
    }


def get_incident_timeline(db: Session, incident_id: UUID, current_user: User | None = None) -> list[dict]:
    incident = get_incident(db, incident_id, current_user=current_user)
    if not incident:
        raise IncidentNotFoundError("Incident not found")

    items: list[dict] = [
        {
            "occurred_at": incident.created_at or datetime.now(UTC),
            "kind": "incident_created",
            "status": incident.status,
            "message": incident.description,
            "incident_type": incident.incident_type,
            "extra": incident.extra if isinstance(incident.extra, dict) else None,
        }
    ]
    updates = (
        db.query(IncidentUpdate)
        .filter(IncidentUpdate.incident_id == incident_id)
        .order_by(IncidentUpdate.created_at.asc())
        .all()
    )
    for row in updates:
        items.append(
            {
                "occurred_at": row.created_at or datetime.now(UTC),
                "kind": "incident_update",
                "status": None,
                "message": row.message,
                "incident_type": None,
                "extra": None,
            }
        )
    items.sort(key=lambda item: item["occurred_at"])
    return items


def auto_escalate_stale_incidents(
    db: Session,
    *,
    stale_hours: int = 24,
    limit: int = 200,
    dry_run: bool = False,
) -> dict:
    stale_hours = max(1, min(stale_hours, 24 * 30))
    limit = max(1, min(limit, 500))
    _require_incident_status_exists(db, "investigating")
    cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)

    candidates = (
        db.query(Incident)
        .filter(Incident.status == "open", Incident.created_at <= cutoff)
        .order_by(Incident.created_at.asc())
        .limit(limit)
        .all()
    )

    escalated = 0
    skipped = 0
    for incident in candidates:
        last_update = (
            db.query(func.max(IncidentUpdate.created_at))
            .filter(IncidentUpdate.incident_id == incident.id)
            .scalar()
        )
        reference_time = last_update or incident.updated_at or incident.created_at
        if reference_time and reference_time > cutoff:
            skipped += 1
            continue
        escalated += 1
        if dry_run:
            continue

        incident.status = "investigating"
        extra = incident.extra if isinstance(incident.extra, dict) else {}
        extra["auto_escalation"] = {
            "stale_hours": stale_hours,
            "escalated_at": datetime.now(UTC).isoformat(),
        }
        incident.extra = extra
        db.add(
            IncidentUpdate(
                incident_id=incident.id,
                message=f"Auto-escalated after {stale_hours}h without progress.",
            )
        )

    if escalated > 0 and not dry_run:
        log_action(db, entity="incidents", action="auto_escalate_stale", status_code=escalated)
    if not dry_run:
        db.commit()

    return {
        "examined": len(candidates),
        "escalated": escalated,
        "skipped": skipped,
        "stale_hours": stale_hours,
        "dry_run": dry_run,
    }


def get_claims_ops_stats(
    db: Session,
    *,
    stale_hours: int = INSURANCE_CLAIM_REVIEW_SLA_HOURS,
) -> dict:
    stale_hours = max(1, min(int(stale_hours), 24 * 30))
    cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)

    total = db.query(Claim).count()
    pending = db.query(Claim).filter(Claim.status.in_(["submitted", "reviewing"])).count()
    pending_over_sla = (
        db.query(Claim)
        .filter(
            Claim.status.in_(["submitted", "reviewing"]),
            Claim.created_at <= cutoff,
        )
        .count()
    )

    status_rows = (
        db.query(func.coalesce(Claim.status, "unknown"), func.count(Claim.id))
        .group_by(Claim.status)
        .all()
    )
    by_status = {str(status): int(count) for status, count in status_rows}

    type_rows = (
        db.query(func.coalesce(Claim.claim_type, "unknown"), func.count(Claim.id))
        .group_by(Claim.claim_type)
        .all()
    )
    by_type = {str(claim_type): int(count) for claim_type, count in type_rows}

    requested_total = (
        db.query(func.coalesce(func.sum(Claim.amount_requested), 0))
        .scalar()
        or 0
    )
    approved_total = (
        db.query(func.coalesce(func.sum(Claim.amount_approved), 0))
        .scalar()
        or 0
    )
    paid_total = (
        db.query(func.coalesce(func.sum(Claim.amount_approved), 0))
        .filter(Claim.status == "paid")
        .scalar()
        or 0
    )

    resolution_rows = (
        db.query(Claim)
        .filter(Claim.status.in_(["rejected", "paid"]), Claim.updated_at.is_not(None))
        .all()
    )
    durations = []
    for row in resolution_rows:
        created_at = row.created_at
        updated_at = row.updated_at
        if created_at and updated_at and updated_at >= created_at:
            durations.append((updated_at - created_at).total_seconds() / 3600)
    avg_resolution_hours = round(sum(durations) / len(durations), 2) if durations else None

    return {
        "total": int(total),
        "pending": int(pending),
        "pending_over_sla": int(pending_over_sla),
        "stale_hours": int(stale_hours),
        "by_status": by_status,
        "by_type": by_type,
        "requested_total": requested_total,
        "approved_total": approved_total,
        "paid_total": paid_total,
        "avg_resolution_hours": avg_resolution_hours,
    }


def auto_escalate_stale_claims(
    db: Session,
    *,
    stale_hours: int = INSURANCE_CLAIM_REVIEW_SLA_HOURS,
    limit: int = 200,
    dry_run: bool = False,
    notify_internal: bool = True,
) -> dict:
    stale_hours = max(1, min(int(stale_hours), 24 * 30))
    limit = max(1, min(int(limit), 500))
    cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)
    now = datetime.now(UTC)

    candidates = (
        db.query(Claim)
        .filter(
            Claim.status.in_(["submitted", "reviewing"]),
            Claim.created_at <= cutoff,
        )
        .order_by(Claim.created_at.asc())
        .limit(limit)
        .all()
    )

    escalated = 0
    for claim in candidates:
        escalated += 1
        if dry_run:
            continue
        if claim.status == "submitted":
            claim.status = "reviewing"
        claim.escalated_at = now
        note = claim.resolution_note or ""
        append = f"[auto_escalated_after_{stale_hours}h@{now.isoformat()}]"
        claim.resolution_note = f"{note} {append}".strip()

    notified_recipients = 0
    if escalated > 0 and not dry_run:
        log_action(db, entity="claims", action="auto_escalate_stale", status_code=escalated)
        if notify_internal:
            roles = _user_types_from_config(CLAIMS_ESCALATION_NOTIFY_ROLES)
            if roles:
                recipients = (
                    db.query(User)
                    .filter(User.user_type.in_(roles), User.phone_e164.is_not(None))
                    .all()
                )
                message = (
                    f"[CLAIMS-SLA] {escalated} reclamation(s) escaladee(s) "
                    f"(>{stale_hours}h). Action immediate requise."
                )
                for user in recipients:
                    queue_and_send_sms(db, user.phone_e164, message, respect_preferences=True)
                notified_recipients = len(recipients)
        db.commit()

    return {
        "examined": len(candidates),
        "escalated": escalated,
        "notified_recipients": notified_recipients,
        "stale_hours": stale_hours,
        "dry_run": dry_run,
    }


def get_insurance_finance_report(
    db: Session,
    *,
    months: int = 6,
) -> dict:
    months = max(1, min(int(months), 36))
    now = datetime.now(UTC)
    this_month = datetime(now.year, now.month, 1, tzinfo=UTC)

    points: list[dict] = []
    total_premiums = Decimal("0")
    total_requested = Decimal("0")
    total_approved = Decimal("0")
    total_paid = Decimal("0")

    for back in range(months - 1, -1, -1):
        year = this_month.year
        month = this_month.month - back
        while month <= 0:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        start = datetime(year, month, 1, tzinfo=UTC)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=UTC)
        else:
            end = datetime(year, month + 1, 1, tzinfo=UTC)

        premiums_collected = _to_decimal(
            db.query(func.coalesce(func.sum(Shipment.insurance_fee), 0))
            .filter(
                Shipment.created_at >= start,
                Shipment.created_at < end,
                Shipment.insurance_fee.is_not(None),
                Shipment.insurance_fee > 0,
            )
            .scalar()
        )
        claims_requested = _to_decimal(
            db.query(func.coalesce(func.sum(Claim.amount_requested), 0))
            .filter(Claim.created_at >= start, Claim.created_at < end)
            .scalar()
        )
        claims_approved = _to_decimal(
            db.query(func.coalesce(func.sum(Claim.amount_approved), 0))
            .filter(Claim.updated_at >= start, Claim.updated_at < end, Claim.status.in_(["approved", "paid"]))
            .scalar()
        )
        claims_paid = _to_decimal(
            db.query(func.coalesce(func.sum(Claim.amount_approved), 0))
            .filter(Claim.updated_at >= start, Claim.updated_at < end, Claim.status == "paid")
            .scalar()
        )
        margin = premiums_collected - claims_paid
        loss_ratio_pct = float((claims_paid / premiums_collected) * Decimal("100")) if premiums_collected > 0 else 0.0

        point = {
            "month": f"{start.year:04d}-{start.month:02d}",
            "premiums_collected": premiums_collected.quantize(Decimal("0.01")),
            "claims_requested": claims_requested.quantize(Decimal("0.01")),
            "claims_approved": claims_approved.quantize(Decimal("0.01")),
            "claims_paid": claims_paid.quantize(Decimal("0.01")),
            "margin": margin.quantize(Decimal("0.01")),
            "loss_ratio_pct": round(loss_ratio_pct, 2),
        }
        points.append(point)

        total_premiums += premiums_collected
        total_requested += claims_requested
        total_approved += claims_approved
        total_paid += claims_paid

    total_margin = total_premiums - total_paid
    total_loss_ratio_pct = float((total_paid / total_premiums) * Decimal("100")) if total_premiums > 0 else 0.0
    totals = {
        "month": "total",
        "premiums_collected": total_premiums.quantize(Decimal("0.01")),
        "claims_requested": total_requested.quantize(Decimal("0.01")),
        "claims_approved": total_approved.quantize(Decimal("0.01")),
        "claims_paid": total_paid.quantize(Decimal("0.01")),
        "margin": total_margin.quantize(Decimal("0.01")),
        "loss_ratio_pct": round(total_loss_ratio_pct, 2),
    }

    return {
        "months": months,
        "points": points,
        "totals": totals,
    }
