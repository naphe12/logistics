"""shipments updated_at and sync support

Revision ID: 20260424_0011
Revises: 20260424_0010
Create Date: 2026-04-24 23:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260424_0011"
down_revision: str | None = "20260424_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    cols = {col["name"] for col in inspector.get_columns(table, schema="logix")}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "shipments", "updated_at"):
        op.add_column(
            "shipments",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.execute("UPDATE logix.shipments SET updated_at = created_at WHERE updated_at IS NULL")
        op.alter_column("shipments", "updated_at", server_default=None, schema="logix")


def downgrade() -> None:
    op.drop_column("shipments", "updated_at", schema="logix")

