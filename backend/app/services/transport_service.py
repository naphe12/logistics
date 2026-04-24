from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.incidents import Incident
from app.models.relays import RelayPoint
from app.models.shipments import Manifest, ManifestShipment, RelayInventory, Shipment, ShipmentEvent
from app.models.transport import Route, Trip
from app.realtime.events import emit_shipment_status_update
from app.services.relay_service import (
    RelayCapacityError,
    RelayInventoryError,
    RelayNotFoundError,
    upsert_relay_inventory,
)
from app.services.audit_service import log_action


class TripError(Exception):
    pass


class TripNotFoundError(TripError):
    pass


class ManifestShipmentError(TripError):
    pass


class RelaySyncError(TripError):
    pass


PRIORITY_STATUS_WEIGHT: dict[str, int] = {
    "arrived_at_relay": 70,
    "ready_for_pickup": 45,
    "picked_up": 35,
    "created": 20,
    "in_transit": 10,
}
DEFAULT_VEHICLE_CAPACITY = 40
CRITICAL_INCIDENT_TYPES = {"lost", "damaged", "security", "fraud", "stolen", "critical"}
LOADABLE_STATUSES = {"created", "ready_for_pickup", "picked_up", "arrived_at_relay"}


def _assigned_shipment_ids(db: Session) -> set[UUID]:
    return {
        row.shipment_id
        for row in db.query(ManifestShipment.shipment_id).all()
        if row.shipment_id is not None
    }


def _destination_utilization_ratio(db: Session, destination_id: UUID | None) -> float | None:
    if destination_id is None:
        return None
    relay = db.query(RelayPoint).filter(RelayPoint.id == destination_id).first()
    if not relay or relay.storage_capacity is None or relay.storage_capacity <= 0:
        return None
    present_count = (
        db.query(RelayInventory)
        .filter(
            RelayInventory.relay_id == destination_id,
            RelayInventory.present.is_(True),
        )
        .count()
    )
    return present_count / relay.storage_capacity


def suggest_shipment_priority_queue(
    db: Session,
    *,
    max_results: int = 50,
    limit: int = 500,
) -> dict:
    max_results = max(1, min(max_results, 200))
    limit = max(1, min(limit, 1000))
    now = datetime.now(UTC)
    candidate_statuses = ["created", "ready_for_pickup", "picked_up", "arrived_at_relay"]

    assigned_ids = _assigned_shipment_ids(db)
    candidates = (
        db.query(Shipment)
        .filter(Shipment.status.in_(candidate_statuses))
        .order_by(Shipment.created_at.asc())
        .limit(limit)
        .all()
    )
    candidates = [item for item in candidates if item.id not in assigned_ids]

    suggestion_rows: list[dict] = []
    for shipment in candidates:
        reasons: list[str] = []
        score = 0

        status = shipment.status or "created"
        status_weight = PRIORITY_STATUS_WEIGHT.get(status, 10)
        score += status_weight
        reasons.append(f"status:{status}(+{status_weight})")

        created_at = shipment.created_at or now
        age_hours = max(0.0, (now - created_at).total_seconds() / 3600.0)
        age_points = min(60, int(age_hours // 6) * 5)
        if age_points > 0:
            score += age_points
            reasons.append(f"waiting:{int(age_hours)}h(+{age_points})")

        incidents_open = (
            db.query(func.count(Incident.id))
            .filter(
                Incident.shipment_id == shipment.id,
                Incident.status.in_(["open", "investigating"]),
            )
            .scalar()
        ) or 0
        if incidents_open > 0:
            incident_points = min(30, 10 + (incidents_open - 1) * 5)
            score += incident_points
            reasons.append(f"incidents:{incidents_open}(+{incident_points})")

        utilization = _destination_utilization_ratio(db, shipment.destination)
        if utilization is not None and utilization >= 0.9:
            saturation_points = 12 if utilization >= 1.0 else 8
            score += saturation_points
            reasons.append(f"dest_util:{int(utilization * 100)}%(+{saturation_points})")

        suggestion_rows.append(
            {
                "shipment_id": shipment.id,
                "shipment_no": shipment.shipment_no,
                "status": shipment.status,
                "created_at": shipment.created_at,
                "origin": shipment.origin,
                "destination": shipment.destination,
                "priority_score": score,
                "reasons": reasons,
            }
        )

    suggestion_rows.sort(
        key=lambda item: (
            -int(item["priority_score"]),
            item["created_at"] or now,
        )
    )
    top = suggestion_rows[:max_results]

    return {
        "generated_at": now,
        "total_candidates": len(suggestion_rows),
        "max_results": max_results,
        "suggestions": top,
    }


def auto_assign_priority_shipments_to_trip(
    db: Session,
    trip_id: UUID,
    *,
    target_manifest_size: int = 20,
    max_add: int = 10,
    candidate_limit: int = 500,
    vehicle_capacity: int | None = None,
) -> dict:
    trip = get_trip(db, trip_id)
    if not trip:
        raise TripNotFoundError("Trip not found")

    target_manifest_size = max(1, min(target_manifest_size, 500))
    max_add = max(1, min(max_add, 200))
    candidate_limit = max(1, min(candidate_limit, 1000))
    capacity_limit = (
        max(1, min(vehicle_capacity, 1000))
        if vehicle_capacity is not None
        else (DEFAULT_VEHICLE_CAPACITY if trip.vehicle_id else 1000)
    )

    manifest = _get_or_create_manifest(db, trip_id)
    manifest_rows = db.query(ManifestShipment).filter(ManifestShipment.manifest_id == manifest.id).all()
    existing_ids = {row.shipment_id for row in manifest_rows if row.shipment_id is not None}
    before_count = len(existing_ids)
    slots_left = max(0, target_manifest_size - before_count)
    capacity_left = max(0, capacity_limit - before_count)
    to_add = min(max_add, slots_left, capacity_left)
    route = db.query(Route).filter(Route.id == trip.route_id).first() if trip.route_id else None

    if to_add <= 0:
        db.commit()
        db.refresh(manifest)
        return {
            "trip_id": trip.id,
            "manifest_id": manifest.id,
            "before_count": before_count,
            "after_count": before_count,
            "target_manifest_size": target_manifest_size,
            "requested_max_add": max_add,
            "added_count": 0,
            "rejected_count": 0,
            "total_priority_candidates": 0,
            "added": [],
            "rejected": [],
        }

    priority = suggest_shipment_priority_queue(
        db,
        max_results=candidate_limit,
        limit=candidate_limit,
    )
    candidates = priority.get("suggestions", [])

    added: list[dict] = []
    rejected: list[dict] = []
    for item in candidates:
        shipment_id = item.get("shipment_id")
        if shipment_id is None or shipment_id in existing_ids:
            continue
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            continue

        rejection_reasons: list[str] = []
        shipment_status = shipment.status or "created"
        if shipment_status not in LOADABLE_STATUSES:
            rejection_reasons.append("status_not_loadable")
        if shipment_status == "created" and (shipment.origin is None or shipment.destination is None):
            rejection_reasons.append("created_missing_route")
        if route is not None:
            if route.origin is not None and shipment.origin != route.origin:
                rejection_reasons.append("route_origin_mismatch")
            if route.destination is not None and shipment.destination != route.destination:
                rejection_reasons.append("route_destination_mismatch")

        critical_incident_exists = (
            db.query(Incident.id)
            .filter(
                Incident.shipment_id == shipment.id,
                Incident.status.in_(["open", "investigating"]),
                func.lower(func.coalesce(Incident.incident_type, "")).in_(CRITICAL_INCIDENT_TYPES),
            )
            .first()
            is not None
        )
        if critical_incident_exists:
            rejection_reasons.append("critical_incident_open")

        if rejection_reasons:
            rejected.append(
                {
                    "shipment_id": shipment.id,
                    "shipment_no": shipment.shipment_no,
                    "priority_score": int(item.get("priority_score") or 0),
                    "reasons": rejection_reasons,
                }
            )
            continue

        db.add(ManifestShipment(manifest_id=manifest.id, shipment_id=shipment_id))
        existing_ids.add(shipment_id)
        added.append(
            {
                "shipment_id": shipment_id,
                "shipment_no": item.get("shipment_no"),
                "priority_score": int(item.get("priority_score") or 0),
                "reasons": list(item.get("reasons") or []),
            }
        )
        if len(added) >= to_add:
            break

    log_action(
        db,
        entity="manifest_shipments",
        action="auto_assign_accept",
        status_code=len(added),
    )
    log_action(
        db,
        entity="manifest_shipments",
        action="auto_assign_reject",
        status_code=len(rejected),
    )
    if added:
        log_action(db, entity="manifest_shipments", action="auto_assign_priority")
    db.commit()
    db.refresh(manifest)

    return {
        "trip_id": trip.id,
        "manifest_id": manifest.id,
        "before_count": before_count,
        "after_count": before_count + len(added),
        "target_manifest_size": target_manifest_size,
        "requested_max_add": max_add,
        "added_count": len(added),
        "rejected_count": len(rejected),
        "total_priority_candidates": int(priority.get("total_candidates") or 0),
        "added": added,
        "rejected": rejected[:50],
    }


def suggest_shipment_grouping(
    db: Session,
    *,
    max_group_size: int = 10,
    limit: int = 300,
) -> dict:
    max_group_size = max(1, min(max_group_size, 100))
    limit = max(1, min(limit, 1000))
    candidate_statuses = ["created", "ready_for_pickup", "picked_up", "arrived_at_relay"]

    assigned_shipment_ids = _assigned_shipment_ids(db)
    candidates = (
        db.query(Shipment)
        .filter(Shipment.status.in_(candidate_statuses))
        .order_by(Shipment.created_at.asc())
        .limit(limit)
        .all()
    )
    candidates = [item for item in candidates if item.id not in assigned_shipment_ids]

    grouped: dict[tuple[UUID | None, UUID | None], list[Shipment]] = {}
    for shipment in candidates:
        key = (shipment.origin, shipment.destination)
        grouped.setdefault(key, []).append(shipment)

    suggestions: list[dict] = []
    for (origin, destination), shipments in grouped.items():
        for index in range(0, len(shipments), max_group_size):
            chunk = shipments[index : index + max_group_size]
            suggestions.append(
                {
                    "key": f"{origin or 'none'}->{destination or 'none'}#{index // max_group_size + 1}",
                    "origin": origin,
                    "destination": destination,
                    "candidate_count": len(chunk),
                    "shipments": [
                        {
                            "shipment_id": item.id,
                            "shipment_no": item.shipment_no,
                            "status": item.status,
                            "created_at": item.created_at,
                            "origin": item.origin,
                            "destination": item.destination,
                        }
                        for item in chunk
                    ],
                }
            )

    suggestions.sort(key=lambda item: (-item["candidate_count"], item["key"]))
    return {
        "generated_at": datetime.now(UTC),
        "max_group_size": max_group_size,
        "total_candidates": len(candidates),
        "total_groups": len(suggestions),
        "suggestions": suggestions,
    }


def list_trips(db: Session) -> list[Trip]:
    return db.query(Trip).order_by(Trip.id.desc()).all()


def get_trip(db: Session, trip_id: UUID) -> Trip | None:
    return db.query(Trip).filter(Trip.id == trip_id).first()


def create_trip(db: Session, *, route_id=None, vehicle_id=None, status: str = "planned") -> Trip:
    trip = Trip(route_id=route_id, vehicle_id=vehicle_id, status=status)
    db.add(trip)
    log_action(db, entity="trips", action="create")
    db.commit()
    db.refresh(trip)
    return trip


def update_trip(db: Session, trip_id: UUID, *, route_id=None, vehicle_id=None, status: str | None = None) -> Trip:
    trip = get_trip(db, trip_id)
    if not trip:
        raise TripNotFoundError("Trip not found")
    if route_id is not None:
        trip.route_id = route_id
    if vehicle_id is not None:
        trip.vehicle_id = vehicle_id
    if status is not None:
        trip.status = status
    log_action(db, entity="trips", action="update")
    db.commit()
    db.refresh(trip)
    return trip


def _get_or_create_manifest(db: Session, trip_id: UUID) -> Manifest:
    manifest = db.query(Manifest).filter(Manifest.trip_id == trip_id).first()
    if manifest:
        return manifest
    manifest = Manifest(trip_id=trip_id)
    db.add(manifest)
    db.flush()
    return manifest


def get_trip_manifest_with_shipments(db: Session, trip_id: UUID) -> tuple[Trip, Manifest, list[Shipment]]:
    trip = get_trip(db, trip_id)
    if not trip:
        raise TripNotFoundError("Trip not found")

    manifest = _get_or_create_manifest(db, trip_id)
    manifest_rows = db.query(ManifestShipment).filter(ManifestShipment.manifest_id == manifest.id).all()
    shipment_ids = [row.shipment_id for row in manifest_rows if row.shipment_id is not None]
    shipments = []
    if shipment_ids:
        shipments = db.query(Shipment).filter(Shipment.id.in_(shipment_ids)).all()
    db.commit()
    db.refresh(manifest)
    return trip, manifest, shipments


def add_shipment_to_manifest(db: Session, trip_id: UUID, shipment_id: UUID) -> ManifestShipment:
    trip = get_trip(db, trip_id)
    if not trip:
        raise TripNotFoundError("Trip not found")

    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise ManifestShipmentError("Shipment not found")

    manifest = _get_or_create_manifest(db, trip_id)
    existing = (
        db.query(ManifestShipment)
        .filter(ManifestShipment.manifest_id == manifest.id, ManifestShipment.shipment_id == shipment_id)
        .first()
    )
    if existing:
        raise ManifestShipmentError("Shipment already in manifest")

    row = ManifestShipment(manifest_id=manifest.id, shipment_id=shipment_id)
    db.add(row)
    log_action(db, entity="manifest_shipments", action="add")
    db.commit()
    db.refresh(row)
    return row


def remove_shipment_from_manifest(db: Session, trip_id: UUID, shipment_id: UUID) -> None:
    trip = get_trip(db, trip_id)
    if not trip:
        raise TripNotFoundError("Trip not found")

    manifest = db.query(Manifest).filter(Manifest.trip_id == trip_id).first()
    if not manifest:
        raise ManifestShipmentError("Manifest not found for trip")

    row = (
        db.query(ManifestShipment)
        .filter(ManifestShipment.manifest_id == manifest.id, ManifestShipment.shipment_id == shipment_id)
        .first()
    )
    if not row:
        raise ManifestShipmentError("Shipment is not in this manifest")
    db.delete(row)
    log_action(db, entity="manifest_shipments", action="remove")
    db.commit()


def _manifest_shipments(db: Session, trip_id: UUID) -> list[Shipment]:
    manifest = db.query(Manifest).filter(Manifest.trip_id == trip_id).first()
    if not manifest:
        return []
    rows = db.query(ManifestShipment).filter(ManifestShipment.manifest_id == manifest.id).all()
    shipment_ids = [row.shipment_id for row in rows if row.shipment_id is not None]
    if not shipment_ids:
        return []
    return db.query(Shipment).filter(Shipment.id.in_(shipment_ids)).all()


def scan_trip_departure(db: Session, trip_id: UUID, *, relay_id=None, event_type: str | None = None) -> tuple[Trip, int]:
    trip = get_trip(db, trip_id)
    if not trip:
        raise TripNotFoundError("Trip not found")
    shipments = _manifest_shipments(db, trip_id)
    event_name = event_type or "shipment_departed_trip"
    for shipment in shipments:
        shipment.status = "in_transit"
        db.add(
            ShipmentEvent(
                shipment_id=shipment.id,
                relay_id=relay_id,
                event_type=event_name,
            )
        )
        if relay_id:
            try:
                upsert_relay_inventory(
                    db,
                    relay_id,
                    shipment_id=shipment.id,
                    present=False,
                    auto_commit=False,
                )
            except (RelayNotFoundError, RelayInventoryError, RelayCapacityError) as exc:
                raise RelaySyncError(str(exc)) from exc
    trip.status = "in_progress"
    log_action(db, entity="trips", action="scan_departure")
    db.commit()
    for shipment in shipments:
        emit_shipment_status_update(
            shipment_id=shipment.id,
            status="in_transit",
            event_type=event_name,
            relay_id=relay_id,
        )
    db.refresh(trip)
    return trip, len(shipments)


def scan_trip_arrival(db: Session, trip_id: UUID, *, relay_id=None, event_type: str | None = None) -> tuple[Trip, int]:
    trip = get_trip(db, trip_id)
    if not trip:
        raise TripNotFoundError("Trip not found")
    shipments = _manifest_shipments(db, trip_id)
    event_name = event_type or "shipment_arrived_trip"
    for shipment in shipments:
        shipment.status = "arrived_at_relay"
        db.add(
            ShipmentEvent(
                shipment_id=shipment.id,
                relay_id=relay_id,
                event_type=event_name,
            )
        )
        if relay_id:
            try:
                upsert_relay_inventory(
                    db,
                    relay_id,
                    shipment_id=shipment.id,
                    present=True,
                    auto_commit=False,
                )
            except (RelayNotFoundError, RelayInventoryError, RelayCapacityError) as exc:
                raise RelaySyncError(str(exc)) from exc
    trip.status = "arrived"
    log_action(db, entity="trips", action="scan_arrival")
    db.commit()
    for shipment in shipments:
        emit_shipment_status_update(
            shipment_id=shipment.id,
            status="arrived_at_relay",
            event_type=event_name,
            relay_id=relay_id,
        )
    db.refresh(trip)
    return trip, len(shipments)


def complete_trip(db: Session, trip_id: UUID) -> Trip:
    trip = get_trip(db, trip_id)
    if not trip:
        raise TripNotFoundError("Trip not found")
    trip.status = "completed"
    log_action(db, entity="trips", action="complete")
    db.commit()
    db.refresh(trip)
    return trip


def now_utc() -> datetime:
    return datetime.now(UTC)
