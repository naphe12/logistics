import uuid
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Commission(Base):
    __tablename__ = "commissions"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    status: Mapped[str | None] = mapped_column(String(40), ForeignKey("logix.incident_statuses.code"))


class IncidentUpdate(Base):
    __tablename__ = "incident_updates"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.incidents.id"))
    message: Mapped[str | None] = mapped_column(Text)


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
