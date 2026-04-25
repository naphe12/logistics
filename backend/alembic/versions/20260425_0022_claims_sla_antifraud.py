"""claims sla and antifraud fields

Revision ID: 20260425_0022
Revises: 20260425_0021
Create Date: 2026-04-25 12:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260425_0022"
down_revision: str | None = "20260425_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "logix"


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    cols = {col["name"] for col in inspector.get_columns(table, schema=SCHEMA)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "claims", "risk_score"):
        op.add_column("claims", sa.Column("risk_score", sa.Numeric(5, 2), nullable=True), schema=SCHEMA)
    if not _has_column(inspector, "claims", "risk_flags"):
        op.add_column(
            "claims",
            sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            schema=SCHEMA,
        )
    if not _has_column(inspector, "claims", "escalated_at"):
        op.add_column("claims", sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)


def downgrade() -> None:
    op.drop_column("claims", "escalated_at", schema=SCHEMA)
    op.drop_column("claims", "risk_flags", schema=SCHEMA)
    op.drop_column("claims", "risk_score", schema=SCHEMA)
