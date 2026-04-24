"""backoffice observability

Revision ID: 20260424_0008
Revises: 20260424_0007
Create Date: 2026-04-24 16:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260424_0008"
down_revision: str | None = "20260424_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    notif_cols = {col["name"]: col for col in inspector.get_columns("notifications", schema="logix")}
    if "delivery_status" not in notif_cols:
        op.add_column(
            "notifications",
            sa.Column("delivery_status", sa.String(length=20), nullable=True, server_default="queued"),
            schema="logix",
        )
        op.alter_column(
            "notifications",
            "delivery_status",
            server_default=None,
            existing_type=sa.String(length=20),
            schema="logix",
        )
    if "error_message" not in notif_cols:
        op.add_column(
            "notifications",
            sa.Column("error_message", sa.Text(), nullable=True),
            schema="logix",
        )

    ussd_cols = {col["name"]: col for col in inspector.get_columns("ussd_logs", schema="logix")}
    if "created_at" not in ussd_cols:
        op.add_column(
            "ussd_logs",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column(
            "ussd_logs",
            "created_at",
            server_default=None,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            schema="logix",
        )

    audit_cols = {col["name"]: col for col in inspector.get_columns("audit_logs", schema="logix")}
    if "created_at" not in audit_cols:
        op.add_column(
            "audit_logs",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column(
            "audit_logs",
            "created_at",
            server_default=None,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            schema="logix",
        )


def downgrade() -> None:
    op.drop_column("audit_logs", "created_at", schema="logix")
    op.drop_column("ussd_logs", "created_at", schema="logix")
    op.drop_column("notifications", "error_message", schema="logix")
    op.drop_column("notifications", "delivery_status", schema="logix")
