import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class RelayPoint(Base):
    __tablename__ = "relay_points"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    relay_code: Mapped[str | None] = mapped_column(String(30), unique=True)
    name: Mapped[str | None] = mapped_column(String(180))
    type: Mapped[str | None] = mapped_column(String(30))
    province_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.provinces.id"))
    commune_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.communes.id"))
    address_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.addresses.id"))
    opening_hours: Mapped[str | None] = mapped_column(String(120))
    storage_capacity: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
