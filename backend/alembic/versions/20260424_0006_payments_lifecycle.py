"""payments lifecycle

Revision ID: 20260424_0006
Revises: 20260424_0005
Create Date: 2026-04-24 15:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260424_0006"
down_revision: str | None = "20260424_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col["name"]: col for col in inspector.get_columns("payment_transactions", schema="logix")}

    if "payer_phone" not in cols:
        op.add_column(
            "payment_transactions",
            sa.Column("payer_phone", sa.String(length=20), nullable=True),
            schema="logix",
        )
    if "payment_stage" not in cols:
        op.add_column(
            "payment_transactions",
            sa.Column("payment_stage", sa.String(length=20), nullable=True),
            schema="logix",
        )
    if "provider" not in cols:
        op.add_column(
            "payment_transactions",
            sa.Column("provider", sa.String(length=30), nullable=True),
            schema="logix",
        )
    if "external_ref" not in cols:
        op.add_column(
            "payment_transactions",
            sa.Column("external_ref", sa.String(length=80), nullable=True),
            schema="logix",
        )
    if "failure_reason" not in cols:
        op.add_column(
            "payment_transactions",
            sa.Column("failure_reason", sa.String(length=255), nullable=True),
            schema="logix",
        )
    if "created_at" not in cols:
        op.add_column(
            "payment_transactions",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column(
            "payment_transactions",
            "created_at",
            server_default=None,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            schema="logix",
        )
    if "updated_at" not in cols:
        op.add_column(
            "payment_transactions",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column(
            "payment_transactions",
            "updated_at",
            server_default=None,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            schema="logix",
        )

    op.execute(
        """
        INSERT INTO logix.payment_statuses (code, label)
        VALUES
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('paid', 'Paid'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
            ('refunded', 'Refunded')
        ON CONFLICT (code)
        DO UPDATE SET label = EXCLUDED.label
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM logix.payment_statuses
        WHERE code IN ('pending', 'processing', 'paid', 'failed', 'cancelled', 'refunded')
        """
    )

    op.drop_column("payment_transactions", "updated_at", schema="logix")
    op.drop_column("payment_transactions", "created_at", schema="logix")
    op.drop_column("payment_transactions", "failure_reason", schema="logix")
    op.drop_column("payment_transactions", "external_ref", schema="logix")
    op.drop_column("payment_transactions", "provider", schema="logix")
    op.drop_column("payment_transactions", "payment_stage", schema="logix")
    op.drop_column("payment_transactions", "payer_phone", schema="logix")
