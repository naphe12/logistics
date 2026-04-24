from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.shipments import Manifest, ManifestShipment, Shipment, ShipmentEvent
from app.models.transport import Trip
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
