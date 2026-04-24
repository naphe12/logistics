import uuid
from decimal import Decimal
from datetime import UTC, datetime
from sqlalchemy import DateTime, String, Numeric, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Commission(Base):
    __tablename__ = "commissions"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.payment_transactions.id"))
    commission_type: Mapped[str | None] = mapped_column(String(30))
    beneficiary_kind: Mapped[str | None] = mapped_column(String(30))
    beneficiary_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str | None] = mapped_column(String(30), default="accrued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    incident_type: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(40), ForeignKey("logix.incident_statuses.code"))
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class IncidentUpdate(Base):
    __tablename__ = "incident_updates"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.incidents.id"))
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    incident_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.incidents.id"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(Text)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    refunded_payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.payment_transactions.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
