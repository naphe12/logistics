from datetime import UTC, datetime
from uuid import UUID

from anyio import from_thread

from app.realtime.tracking import tracking_hub


def emit_shipment_status_update(
    *,
    shipment_id: UUID,
    status: str,
    event_type: str,
    relay_id: UUID | None = None,
) -> None:
    payload = {
        "kind": "shipment_status_updated",
        "shipment_id": str(shipment_id),
        "status": status,
        "event_type": event_type,
        "relay_id": str(relay_id) if relay_id else None,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    try:
        from_thread.run(tracking_hub.broadcast, str(shipment_id), payload)
    except RuntimeError:
        return

