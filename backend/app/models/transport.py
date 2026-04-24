import uuid
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TransportPartner(Base):
    __tablename__ = "transport_partners"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str | None] = mapped_column(String(180))


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.transport_partners.id"))
    plate: Mapped[str | None] = mapped_column(String(30))


class Route(Base):
    __tablename__ = "routes"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    origin: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.relay_points.id"))
    destination: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.relay_points.id"))


class RouteStop(Base):
    __tablename__ = "route_stops"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.routes.id"))
    relay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.relay_points.id"))
    stop_order: Mapped[int | None] = mapped_column(Integer)


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.routes.id"))
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.vehicles.id"))
    status: Mapped[str | None] = mapped_column(String(20))
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB)
