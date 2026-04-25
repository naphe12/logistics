import pytest

from app.services.shipment_flow_rules import ALLOWED_TRANSITIONS, validate_transition


STATUSES = [
    "created",
    "picked_up",
    "in_transit",
    "arrived_at_relay",
    "ready_for_pickup",
    "delivered",
]


def _valid_event_for_target(target: str) -> str | None:
    mapping = {
        "picked_up": "shipment_picked_up",
        "in_transit": "shipment_departed_trip",
        "arrived_at_relay": "shipment_arrived_trip",
    }
    return mapping.get(target)


@pytest.mark.parametrize("source", STATUSES)
@pytest.mark.parametrize("target", STATUSES)
def test_transition_matrix_complete(source: str, target: str) -> None:
    if source == target:
        validate_transition(source, target, event_type="noop")
        return

    allowed_targets = ALLOWED_TRANSITIONS.get(source, set())
    if target in allowed_targets:
        validate_transition(source, target, event_type=_valid_event_for_target(target))
        return

    with pytest.raises(ValueError):
        validate_transition(source, target, event_type="shipment_departed_trip")


@pytest.mark.parametrize(
    "source,target,bad_event",
    [
        ("created", "picked_up", "shipment_arrived_trip"),
        ("picked_up", "in_transit", "shipment_picked_up"),
        ("in_transit", "arrived_at_relay", "shipment_departed_trip"),
    ],
)
def test_scan_required_transition_rejects_wrong_event(source: str, target: str, bad_event: str) -> None:
    with pytest.raises(ValueError):
        validate_transition(source, target, event_type=bad_event)


@pytest.mark.parametrize(
    "source,target",
    [
        ("created", "picked_up"),
        ("picked_up", "in_transit"),
        ("in_transit", "arrived_at_relay"),
    ],
)
def test_scan_required_transition_rejects_missing_event(source: str, target: str) -> None:
    with pytest.raises(ValueError):
        validate_transition(source, target, event_type=None)
