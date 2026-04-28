"""relays map onboarding and delivery photo

Revision ID: 20260428_0027
Revises: 20260425_0026
Create Date: 2026-04-28 10:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260428_0027"
down_revision: str | None = "20260425_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    tables = set(inspector.get_table_names(schema="logix"))
    if "relay_manager_applications" not in tables:
        op.create_table(
            "relay_manager_applications",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("relay_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("manager_name", sa.String(length=180), nullable=False),
            sa.Column("manager_phone", sa.String(length=20), nullable=False),
            sa.Column("manager_email", sa.String(length=180), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("training_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["logix.users.id"]),
            sa.ForeignKeyConstraint(["relay_id"], ["logix.relay_points.id"]),
            sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["logix.users.id"]),
            sa.PrimaryKeyConstraint("id"),
            schema="logix",
        )
        op.create_index(
            "ix_relay_manager_applications_status",
            "relay_manager_applications",
            ["status"],
            unique=False,
            schema="logix",
        )
        op.alter_column(
            "relay_manager_applications",
            "status",
            server_default=None,
            schema="logix",
        )
        op.alter_column(
            "relay_manager_applications",
            "training_completed",
            server_default=None,
            schema="logix",
        )


def downgrade() -> None:
    op.drop_index("ix_relay_manager_applications_status", table_name="relay_manager_applications", schema="logix")
    op.drop_table("relay_manager_applications", schema="logix")
