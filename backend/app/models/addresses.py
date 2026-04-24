import uuid
from datetime import UTC, datetime
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Province(Base):
    __tablename__ = "provinces"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class Commune(Base):
    __tablename__ = "communes"
    __table_args__ = (
        UniqueConstraint("province_id", "name", name="uq_communes_province_name"),
        {"schema": "logix"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    province_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.provinces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class Address(Base):
    __tablename__ = "addresses"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    province_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.provinces.id"))
    commune_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.communes.id"))
    province: Mapped[str | None] = mapped_column(String(120))
    commune: Mapped[str | None] = mapped_column(String(120))
    zone: Mapped[str | None] = mapped_column(String(120))
    colline: Mapped[str | None] = mapped_column(String(120))
    quartier: Mapped[str | None] = mapped_column(String(120))
    landmark: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    raw_input: Mapped[str | None] = mapped_column(Text)
    address_line: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
