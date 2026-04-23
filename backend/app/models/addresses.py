import uuid
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Address(Base):
    __tablename__ = "addresses"
    __table_args__ = {"schema": "logix"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    province: Mapped[str | None] = mapped_column(String(120))
    commune: Mapped[str | None] = mapped_column(String(120))
    address_line: Mapped[str | None] = mapped_column(Text)
