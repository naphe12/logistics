"""relays and agent assignment

Revision ID: 20260424_0005
Revises: 20260424_0004
Create Date: 2026-04-24 14:05:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260424_0005"
down_revision: str | None = "20260424_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    relay_cols = {col["name"]: col for col in inspector.get_columns("relay_points", schema="logix")}
    if "opening_hours" not in relay_cols:
        op.add_column(
            "relay_points",
            sa.Column("opening_hours", sa.String(length=120), nullable=True),
            schema="logix",
        )
    if "storage_capacity" not in relay_cols:
        op.add_column(
            "relay_points",
            sa.Column("storage_capacity", sa.Integer(), nullable=True),
            schema="logix",
        )
    if "is_active" not in relay_cols:
        op.add_column(
            "relay_points",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            schema="logix",
        )
        op.alter_column(
            "relay_points",
            "is_active",
            server_default=None,
            existing_type=sa.Boolean(),
            schema="logix",
        )

    user_cols = {col["name"]: col for col in inspector.get_columns("users", schema="logix")}
    if "relay_id" not in user_cols:
        op.add_column(
            "users",
            sa.Column("relay_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema="logix",
        )

    user_fks = inspector.get_foreign_keys("users", schema="logix")
    user_fk_names = {fk.get("name") for fk in user_fks}
    if "fk_users_relay_id_relay_points" not in user_fk_names:
        op.create_foreign_key(
            "fk_users_relay_id_relay_points",
            "users",
            "relay_points",
            ["relay_id"],
            ["id"],
            source_schema="logix",
            referent_schema="logix",
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_users_relay_id_relay_points",
        "users",
        schema="logix",
        type_="foreignkey",
    )
    op.drop_column("users", "relay_id", schema="logix")

    op.drop_column("relay_points", "is_active", schema="logix")
    op.drop_column("relay_points", "storage_capacity", schema="logix")
    op.drop_column("relay_points", "opening_hours", schema="logix")
