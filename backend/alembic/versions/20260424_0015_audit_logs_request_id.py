"""add request_id to audit logs

Revision ID: 20260424_0015
Revises: 20260424_0014
Create Date: 2026-04-24 22:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260424_0015"
down_revision: str | None = "20260424_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "logix"


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {col["name"] for col in inspector.get_columns(table_name, schema=SCHEMA)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _column_exists(inspector, "audit_logs", "request_id"):
        op.add_column(
            "audit_logs",
            sa.Column("request_id", sa.String(length=64), nullable=True),
            schema=SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _column_exists(inspector, "audit_logs", "request_id"):
        op.drop_column("audit_logs", "request_id", schema=SCHEMA)
