"""ops monetization hardening

Revision ID: 20260424_0010
Revises: 20260424_0009
Create Date: 2026-04-24 20:40:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260424_0010"
down_revision: str | None = "20260424_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    cols = {col["name"] for col in inspector.get_columns(table, schema="logix")}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "notifications", "attempts_count"):
        op.add_column(
            "notifications",
            sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
            schema="logix",
        )
        op.alter_column(
            "notifications",
            "attempts_count",
            server_default=None,
            schema="logix",
        )
    if not _has_column(inspector, "notifications", "max_attempts"):
        op.add_column(
            "notifications",
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            schema="logix",
        )
        op.alter_column(
            "notifications",
            "max_attempts",
            server_default=None,
            schema="logix",
        )
    if not _has_column(inspector, "notifications", "next_retry_at"):
        op.add_column(
            "notifications",
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            schema="logix",
        )
    if not _has_column(inspector, "notifications", "last_attempt_at"):
        op.add_column(
            "notifications",
            sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
            schema="logix",
        )

    if not _has_column(inspector, "commissions", "payment_id"):
        op.add_column(
            "commissions",
            sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema="logix",
        )
    if not _has_column(inspector, "commissions", "commission_type"):
        op.add_column(
            "commissions",
            sa.Column("commission_type", sa.String(length=30), nullable=True),
            schema="logix",
        )
    if not _has_column(inspector, "commissions", "beneficiary_kind"):
        op.add_column(
            "commissions",
            sa.Column("beneficiary_kind", sa.String(length=30), nullable=True),
            schema="logix",
        )
    if not _has_column(inspector, "commissions", "beneficiary_id"):
        op.add_column(
            "commissions",
            sa.Column("beneficiary_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema="logix",
        )
    if not _has_column(inspector, "commissions", "rate_pct"):
        op.add_column(
            "commissions",
            sa.Column("rate_pct", sa.Numeric(8, 4), nullable=True),
            schema="logix",
        )
    if not _has_column(inspector, "commissions", "status"):
        op.add_column(
            "commissions",
            sa.Column("status", sa.String(length=30), nullable=True),
            schema="logix",
        )
    if not _has_column(inspector, "commissions", "created_at"):
        op.add_column(
            "commissions",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column("commissions", "created_at", server_default=None, schema="logix")

    fks = inspector.get_foreign_keys("commissions", schema="logix")
    fk_names = {fk.get("name") for fk in fks}
    if "fk_commissions_payment_id_payment_transactions" not in fk_names:
        op.create_foreign_key(
            "fk_commissions_payment_id_payment_transactions",
            "commissions",
            "payment_transactions",
            ["payment_id"],
            ["id"],
            source_schema="logix",
            referent_schema="logix",
        )

    if not _has_column(inspector, "claims", "resolution_note"):
        op.add_column(
            "claims",
            sa.Column("resolution_note", sa.Text(), nullable=True),
            schema="logix",
        )
    if not _has_column(inspector, "claims", "refunded_payment_id"):
        op.add_column(
            "claims",
            sa.Column("refunded_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema="logix",
        )
    if not _has_column(inspector, "claims", "updated_at"):
        op.add_column(
            "claims",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column("claims", "updated_at", server_default=None, schema="logix")

    claim_fks = inspector.get_foreign_keys("claims", schema="logix")
    claim_fk_names = {fk.get("name") for fk in claim_fks}
    if "fk_claims_refunded_payment_id_payment_transactions" not in claim_fk_names:
        op.create_foreign_key(
            "fk_claims_refunded_payment_id_payment_transactions",
            "claims",
            "payment_transactions",
            ["refunded_payment_id"],
            ["id"],
            source_schema="logix",
            referent_schema="logix",
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_claims_refunded_payment_id_payment_transactions",
        "claims",
        schema="logix",
        type_="foreignkey",
    )
    op.drop_column("claims", "updated_at", schema="logix")
    op.drop_column("claims", "refunded_payment_id", schema="logix")
    op.drop_column("claims", "resolution_note", schema="logix")

    op.drop_constraint(
        "fk_commissions_payment_id_payment_transactions",
        "commissions",
        schema="logix",
        type_="foreignkey",
    )
    op.drop_column("commissions", "created_at", schema="logix")
    op.drop_column("commissions", "status", schema="logix")
    op.drop_column("commissions", "rate_pct", schema="logix")
    op.drop_column("commissions", "beneficiary_id", schema="logix")
    op.drop_column("commissions", "beneficiary_kind", schema="logix")
    op.drop_column("commissions", "commission_type", schema="logix")
    op.drop_column("commissions", "payment_id", schema="logix")

    op.drop_column("notifications", "last_attempt_at", schema="logix")
    op.drop_column("notifications", "next_retry_at", schema="logix")
    op.drop_column("notifications", "max_attempts", schema="logix")
    op.drop_column("notifications", "attempts_count", schema="logix")

