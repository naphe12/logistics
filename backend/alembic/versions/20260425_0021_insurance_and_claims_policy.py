"""insurance and claims policy fields

Revision ID: 20260425_0021
Revises: 20260425_0020
Create Date: 2026-04-25 10:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260425_0021"
down_revision: str | None = "20260425_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "logix"


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    cols = {col["name"] for col in inspector.get_columns(table, schema=SCHEMA)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "shipments", "declared_value"):
        op.add_column("shipments", sa.Column("declared_value", sa.Numeric(12, 2), nullable=True), schema=SCHEMA)
    if not _has_column(inspector, "shipments", "insurance_fee"):
        op.add_column("shipments", sa.Column("insurance_fee", sa.Numeric(12, 2), nullable=True), schema=SCHEMA)
    if not _has_column(inspector, "shipments", "coverage_amount"):
        op.add_column("shipments", sa.Column("coverage_amount", sa.Numeric(12, 2), nullable=True), schema=SCHEMA)

    if not _has_column(inspector, "claims", "amount_requested"):
        op.add_column("claims", sa.Column("amount_requested", sa.Numeric(12, 2), nullable=True), schema=SCHEMA)
    if not _has_column(inspector, "claims", "amount_approved"):
        op.add_column("claims", sa.Column("amount_approved", sa.Numeric(12, 2), nullable=True), schema=SCHEMA)
    if not _has_column(inspector, "claims", "claim_type"):
        op.add_column("claims", sa.Column("claim_type", sa.String(length=40), nullable=True), schema=SCHEMA)
    if not _has_column(inspector, "claims", "proof_urls"):
        op.add_column("claims", sa.Column("proof_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema=SCHEMA)

    # Backfill requested amount for existing claims.
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.claims
            SET amount_requested = amount
            WHERE amount_requested IS NULL AND amount IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("claims", "proof_urls", schema=SCHEMA)
    op.drop_column("claims", "claim_type", schema=SCHEMA)
    op.drop_column("claims", "amount_approved", schema=SCHEMA)
    op.drop_column("claims", "amount_requested", schema=SCHEMA)
    op.drop_column("shipments", "coverage_amount", schema=SCHEMA)
    op.drop_column("shipments", "insurance_fee", schema=SCHEMA)
    op.drop_column("shipments", "declared_value", schema=SCHEMA)
