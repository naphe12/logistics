"""auth otp hardening

Revision ID: 20260423_0003
Revises: 20260423_0002
Create Date: 2026-04-23 22:55:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260423_0003"
down_revision: str | None = "20260423_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    otp_cols = {col["name"]: col for col in inspector.get_columns("otp_codes", schema="logix")}

    if "attempts_count" not in otp_cols:
        op.add_column(
            "otp_codes",
            sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
            schema="logix",
        )
        op.alter_column(
            "otp_codes",
            "attempts_count",
            server_default=None,
            existing_type=sa.Integer(),
            schema="logix",
        )

    if "locked_until" not in otp_cols:
        op.add_column(
            "otp_codes",
            sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
            schema="logix",
        )

    if "consumed_at" not in otp_cols:
        op.add_column(
            "otp_codes",
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            schema="logix",
        )

    if "created_at" not in otp_cols:
        op.add_column(
            "otp_codes",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column(
            "otp_codes",
            "created_at",
            server_default=None,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            schema="logix",
        )

    op.execute(
        """
        DELETE FROM logix.otp_codes
        WHERE code_hash IS NULL OR expires_at IS NULL
        """
    )

    otp_cols = {col["name"]: col for col in inspector.get_columns("otp_codes", schema="logix")}
    if otp_cols.get("code_hash", {}).get("nullable", True):
        op.alter_column(
            "otp_codes",
            "code_hash",
            existing_type=sa.TEXT(),
            nullable=False,
            schema="logix",
        )
    if otp_cols.get("expires_at", {}).get("nullable", True):
        op.alter_column(
            "otp_codes",
            "expires_at",
            existing_type=postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            schema="logix",
        )


def downgrade() -> None:
    op.alter_column(
        "otp_codes",
        "expires_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=True,
        schema="logix",
    )
    op.alter_column(
        "otp_codes",
        "code_hash",
        existing_type=sa.TEXT(),
        nullable=True,
        schema="logix",
    )

    op.drop_column("otp_codes", "created_at", schema="logix")
    op.drop_column("otp_codes", "consumed_at", schema="logix")
    op.drop_column("otp_codes", "locked_until", schema="logix")
    op.drop_column("otp_codes", "attempts_count", schema="logix")
