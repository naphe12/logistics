"""security audit and rate limit fields

Revision ID: 20260424_0009
Revises: 20260424_0008
Create Date: 2026-04-24 17:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260424_0009"
down_revision: str | None = "20260424_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col["name"]: col for col in inspector.get_columns("audit_logs", schema="logix")}

    if "actor_user_id" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema="logix",
        )
    if "actor_phone" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("actor_phone", sa.String(length=20), nullable=True),
            schema="logix",
        )
    if "ip_address" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            schema="logix",
        )
    if "endpoint" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("endpoint", sa.String(length=255), nullable=True),
            schema="logix",
        )
    if "method" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("method", sa.String(length=10), nullable=True),
            schema="logix",
        )
    if "status_code" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("status_code", sa.Integer(), nullable=True),
            schema="logix",
        )


def downgrade() -> None:
    op.drop_column("audit_logs", "status_code", schema="logix")
    op.drop_column("audit_logs", "method", schema="logix")
    op.drop_column("audit_logs", "endpoint", schema="logix")
    op.drop_column("audit_logs", "ip_address", schema="logix")
    op.drop_column("audit_logs", "actor_phone", schema="logix")
    op.drop_column("audit_logs", "actor_user_id", schema="logix")
