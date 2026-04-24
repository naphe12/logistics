"""add metadata columns to core tables

Revision ID: 20260424_0013
Revises: 20260424_0012
Create Date: 2026-04-24 18:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260424_0013"
down_revision: str | None = "20260424_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "logix"
TARGET_TABLES = (
    "shipments",
    "shipment_events",
    "payment_transactions",
    "trips",
    "incidents",
)


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {col["name"] for col in inspector.get_columns(table_name, schema=SCHEMA)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in TARGET_TABLES:
        if not _column_exists(inspector, table_name, "metadata"):
            op.add_column(
                table_name,
                sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
                schema=SCHEMA,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in reversed(TARGET_TABLES):
        if _column_exists(inspector, table_name, "metadata"):
            op.drop_column(table_name, "metadata", schema=SCHEMA)
