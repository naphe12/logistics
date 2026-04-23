from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ShipmentStatus(Base):
    __tablename__ = "shipment_statuses"
    __table_args__ = {"schema": "logix"}

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str | None] = mapped_column(String(100))


class PaymentStatus(Base):
    __tablename__ = "payment_statuses"
    __table_args__ = {"schema": "logix"}

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str | None] = mapped_column(String(100))


class IncidentStatus(Base):
    __tablename__ = "incident_statuses"
    __table_args__ = {"schema": "logix"}

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str | None] = mapped_column(String(100))
