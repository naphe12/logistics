from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from app.config import (
    INSURANCE_CLAIM_WINDOW_HOURS,
    INSURANCE_DAMAGE_COVERAGE_RATE,
    INSURANCE_ENABLED,
    INSURANCE_LOSS_COVERAGE_RATE,
    INSURANCE_MAX_COVERAGE_BIF,
    INSURANCE_PREMIUM_RATE,
    INSURANCE_PROHIBITED_ITEMS,
    INSURANCE_REQUIRE_PROOF,
)
from app.models.shipments import Shipment


class InsuranceValidationError(Exception):
    pass


ZERO = Decimal("0")
CENT = Decimal("0.01")


def _d(value: float | int | str | Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _contains_prohibited_item(text_value: str | None) -> bool:
    if not text_value:
        return False
    normalized = text_value.strip().lower()
    return any(token.strip().lower() in normalized for token in INSURANCE_PROHIBITED_ITEMS if token.strip())


@dataclass(frozen=True)
class InsuranceQuote:
    declared_value: Decimal
    insurance_opt_in: bool
    insurance_fee: Decimal
    coverage_amount: Decimal
    premium_rate: Decimal
    max_coverage: Decimal


def compute_insurance_quote(*, declared_value: Decimal | None, insurance_opt_in: bool) -> InsuranceQuote:
    value = max(_d(declared_value), ZERO)
    premium_rate = max(_d(INSURANCE_PREMIUM_RATE), ZERO)
    max_coverage = max(_d(INSURANCE_MAX_COVERAGE_BIF), ZERO)
    coverage_amount = min(value, max_coverage)
    insurance_fee = _quantize_money(value * premium_rate) if insurance_opt_in and INSURANCE_ENABLED else ZERO
    if not insurance_opt_in:
        insurance_fee = ZERO
    return InsuranceQuote(
        declared_value=_quantize_money(value),
        insurance_opt_in=insurance_opt_in and INSURANCE_ENABLED,
        insurance_fee=insurance_fee,
        coverage_amount=_quantize_money(coverage_amount),
        premium_rate=premium_rate,
        max_coverage=max_coverage,
    )


def compute_claim_ceiling(*, shipment: Shipment, claim_type: str) -> Decimal:
    claim_kind = (claim_type or "").strip().lower()
    coverage_amount = _d(getattr(shipment, "coverage_amount", None))
    declared_value = _d(getattr(shipment, "declared_value", None))
    base = max(coverage_amount, declared_value)
    base = min(base, _d(INSURANCE_MAX_COVERAGE_BIF))

    if claim_kind == "lost":
        factor = _d(INSURANCE_LOSS_COVERAGE_RATE)
    elif claim_kind == "damaged":
        factor = _d(INSURANCE_DAMAGE_COVERAGE_RATE)
    else:
        factor = _d("0.25")
    return _quantize_money(max(ZERO, base * factor))


def validate_claim_policy(
    *,
    shipment: Shipment,
    claim_type: str,
    amount_requested: Decimal,
    proof_urls: list[str] | None,
) -> Decimal:
    if not INSURANCE_ENABLED:
        raise InsuranceValidationError("Insurance policy is disabled")

    if amount_requested <= ZERO:
        raise InsuranceValidationError("Claim amount must be greater than 0")

    now = datetime.now(UTC)
    is_delivered = (shipment.status or "").strip().lower() == "delivered"
    deadline_reference = (shipment.updated_at or shipment.created_at or now) if is_delivered else now
    delay_hours = (now - deadline_reference).total_seconds() / 3600
    if delay_hours > INSURANCE_CLAIM_WINDOW_HOURS:
        raise InsuranceValidationError(
            f"Claim delay exceeded ({INSURANCE_CLAIM_WINDOW_HOURS}h max)"
        )

    extra = shipment.extra if isinstance(shipment.extra, dict) else {}
    prohibited_flags = [
        bool(extra.get("is_prohibited")),
        _contains_prohibited_item(str(extra.get("category") or "")),
        _contains_prohibited_item(str(extra.get("contents") or "")),
    ]
    if any(prohibited_flags):
        raise InsuranceValidationError("Shipment contains prohibited items for insurance")

    cleaned_proofs = [p.strip() for p in (proof_urls or []) if p and p.strip()]
    if INSURANCE_REQUIRE_PROOF and not cleaned_proofs:
        raise InsuranceValidationError("Proof is required to submit a claim")

    ceiling = compute_claim_ceiling(shipment=shipment, claim_type=claim_type)
    if ceiling <= ZERO:
        raise InsuranceValidationError("Shipment is not eligible for reimbursement")
    if amount_requested > ceiling:
        raise InsuranceValidationError(f"Requested amount exceeds eligible ceiling ({ceiling})")
    return ceiling
