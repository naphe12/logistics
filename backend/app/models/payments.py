import uuid
from decimal import Decimal
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("logix.shipments.id"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    payer_phone: Mapped[str | None] = mapped_column(String(20))
    payment_stage: Mapped[str | None] = mapped_column(String(20))
    provider: Mapped[str | None] = mapped_column(String(30))
    external_ref: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str | None] = mapped_column(String(40), ForeignKey("logix.payment_statuses.code"))
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
