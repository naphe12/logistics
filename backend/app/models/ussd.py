import uuid
from datetime import datetime, UTC
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.enums import CodePurposeEnum


class UssdSession(Base):
    __tablename__ = "ussd_sessions"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str | None] = mapped_column(String(20))
    state: Mapped[dict | None] = mapped_column(JSONB)


class UssdLog(Base):
    __tablename__ = "ussd_logs"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.ussd_sessions.id"))
    payload: Mapped[str | None] = mapped_column(Text)


class ShipmentCode(Base):
    __tablename__ = "shipment_codes"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    code_last4: Mapped[str | None] = mapped_column(String(4))
    purpose: Mapped[CodePurposeEnum] = mapped_column(
        Enum(CodePurposeEnum, name="code_purpose_enum", schema="logix")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    shipment = relationship("Shipment", back_populates="codes")


class ShipmentCodeAttempt(Base):
    __tablename__ = "shipment_code_attempts"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    success: Mapped[bool | None]


class OTPCode(Base):
    __tablename__ = "otp_codes"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.users.id"))
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    attempts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
