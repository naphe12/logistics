ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "created": {"picked_up"},
    "picked_up": {"in_transit"},
    "in_transit": {"arrived_at_relay"},
    "arrived_at_relay": {"ready_for_pickup", "in_transit"},
    "ready_for_pickup": {"delivered"},
}

# Target statuses that must be produced by a scan-like event.
REQUIRES_SCAN_EVENT: set[str] = {"picked_up", "in_transit", "arrived_at_relay"}

# Prefix-based matching keeps events explicit while allowing operational variants.
VALID_SCAN_EVENTS_BY_STATUS: dict[str, tuple[str, ...]] = {
    "picked_up": ("shipment_picked_up", "pickup_", "scan_pickup"),
    "in_transit": ("shipment_departed_", "scan_departure", "in_transit_"),
    "arrived_at_relay": ("shipment_arrived_", "scan_arrival", "arrived_at_relay_"),
}


def _normalize_status(value: str | None) -> str:
    return (value or "").strip().lower()


def _normalize_event(value: str | None) -> str:
    return (value or "").strip().lower()


def _event_matches(event_type: str, patterns: tuple[str, ...]) -> bool:
    return any(event_type.startswith(pattern) for pattern in patterns)


def validate_transition(
    from_status: str | None,
    to_status: str | None,
    *,
    event_type: str | None = None,
) -> None:
    source = _normalize_status(from_status)
    target = _normalize_status(to_status)
    event = _normalize_event(event_type)

    if not target:
        raise ValueError("Target status is required")
    if not source:
        raise ValueError("Current status is required")
    if source == target:
        return

    allowed_targets = ALLOWED_TRANSITIONS.get(source, set())
    if target not in allowed_targets:
        raise ValueError(f"Invalid shipment status transition: {source} -> {target}")

    if target in REQUIRES_SCAN_EVENT:
        patterns = VALID_SCAN_EVENTS_BY_STATUS.get(target, tuple())
        if not event:
            raise ValueError(f"Event type is required for transition to '{target}'")
        if patterns and not _event_matches(event, patterns):
            raise ValueError(
                f"Event type '{event_type}' is not valid for transition to '{target}'"
            )
