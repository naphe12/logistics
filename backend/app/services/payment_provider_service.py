from datetime import UTC, datetime
from uuid import uuid4


SUPPORTED_PAYMENT_PROVIDERS = {"lumicash", "ecocash", "ussd", "manual", "mock"}
PROVIDER_ALIASES = {
    "lumi_cash": "lumicash",
    "lumi-cash": "lumicash",
    "lumi cash": "lumicash",
    "eco_cash": "ecocash",
    "eco-cash": "ecocash",
    "eco cash": "ecocash",
}


def normalize_provider(provider: str | None) -> str:
    normalized = (provider or "").strip().lower()
    if not normalized:
        return ""
    return PROVIDER_ALIASES.get(normalized, normalized)


def validate_supported_provider(provider: str | None) -> str:
    normalized = normalize_provider(provider)
    if normalized not in SUPPORTED_PAYMENT_PROVIDERS:
        raise ValueError(f"Unsupported payment provider: {provider}")
    return normalized


def provider_status_to_internal(provider: str | None, status: str) -> str:
    normalized_provider = normalize_provider(provider)
    normalized_status = (status or "").strip().lower()
    generic = {
        "paid": "paid",
        "success": "paid",
        "succeeded": "paid",
        "completed": "paid",
        "ok": "paid",
        "processing": "processing",
        "pending": "pending",
        "failed": "failed",
        "error": "failed",
        "declined": "failed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "expired": "failed",
        "timeout": "failed",
        "refunded": "refunded",
    }

    lumicash = {
        "initiated": "processing",
        "submitted": "processing",
        "successful": "paid",
        "failed": "failed",
        "cancelled": "cancelled",
        "reversed": "refunded",
    }
    ecocash = {
        "queued": "processing",
        "pending_user": "processing",
        "approved": "paid",
        "rejected": "failed",
        "cancelled": "cancelled",
        "reversed": "refunded",
    }

    by_provider = {
        "lumicash": lumicash,
        "ecocash": ecocash,
    }
    provider_mapping = by_provider.get(normalized_provider, {})
    if normalized_status in provider_mapping:
        return provider_mapping[normalized_status]
    if normalized_status in generic:
        return generic[normalized_status]
    raise ValueError(f"Unsupported webhook payment status: {status}")


def build_provider_initiation_metadata(
    *,
    provider: str | None,
    external_ref: str,
    amount,
    payer_phone: str | None,
) -> dict[str, object]:
    normalized_provider = normalize_provider(provider)
    now = datetime.now(UTC).isoformat()
    return {
        "provider": normalized_provider or provider,
        "request_id": str(uuid4()),
        "external_ref": external_ref,
        "requested_at": now,
        "amount": str(amount) if amount is not None else None,
        "payer_phone": payer_phone,
        "state": "submitted",
    }
