"""add notifications metadata for campaign tracking

Revision ID: 20260424_0016
Revises: 20260424_0015
Create Date: 2026-04-24 22:40:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260424_0016"
down_revision: str | None = "20260424_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "logix"


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {col["name"] for col in inspector.get_columns(table_name, schema=SCHEMA)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _column_exists(inspector, "notifications", "metadata"):
        op.add_column(
            "notifications",
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            schema=SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _column_exists(inspector, "notifications", "metadata"):
        op.drop_column("notifications", "metadata", schema=SCHEMA)
