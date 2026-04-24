import uuid
from datetime import datetime, UTC
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    sender_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.users.id"))
    sender_phone: Mapped[str | None] = mapped_column(String(20))
    receiver_name: Mapped[str | None] = mapped_column(String(180))
    receiver_phone: Mapped[str | None] = mapped_column(String(20))
    origin: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.relay_points.id"))
    destination: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.relay_points.id"))
    status: Mapped[str | None] = mapped_column(String(40), ForeignKey("logix.shipment_statuses.code"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    events = relationship("ShipmentEvent", back_populates="shipment", cascade="all, delete-orphan")
    packages = relationship("ShipmentPackage", back_populates="shipment", cascade="all, delete-orphan")
    items = relationship("ShipmentItem", back_populates="shipment", cascade="all, delete-orphan")
    codes = relationship("ShipmentCode", back_populates="shipment", cascade="all, delete-orphan")


class ShipmentPackage(Base):
    __tablename__ = "shipment_packages"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    weight: Mapped[float | None] = mapped_column(Numeric(10, 2))

    shipment = relationship("Shipment", back_populates="packages")


class ShipmentItem(Base):
    __tablename__ = "shipment_items"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    name: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int | None] = mapped_column(Integer)

    shipment = relationship("Shipment", back_populates="items")


class ShipmentEvent(Base):
    __tablename__ = "shipment_events"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"), nullable=False)
    relay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.relay_points.id"))
    event_type: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    shipment = relationship("Shipment", back_populates="events")


class Manifest(Base):
    __tablename__ = "manifests"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.trips.id"))


class ManifestShipment(Base):
    __tablename__ = "manifest_shipments"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manifest_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.manifests.id"))
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))


class RelayOperation(Base):
    __tablename__ = "relay_operations"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    relay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.relay_points.id"))
    operation: Mapped[str | None] = mapped_column(String(40))


class RelayInventory(Base):
    __tablename__ = "relay_inventory"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    relay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.relay_points.id"))
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    present: Mapped[bool] = mapped_column(Boolean, default=True)
