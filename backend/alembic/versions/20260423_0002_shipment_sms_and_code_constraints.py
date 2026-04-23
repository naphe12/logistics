"""shipment sms and code constraints

Revision ID: 20260423_0002
Revises: 20260423_0001
Create Date: 2026-04-23 22:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260423_0002"
down_revision: str | None = "20260423_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    shipment_cols = {col["name"]: col for col in inspector.get_columns("shipments", schema="logix")}
    if "sender_phone" not in shipment_cols:
        op.add_column(
            "shipments",
            sa.Column("sender_phone", sa.String(length=20), nullable=True),
            schema="logix",
        )

    shipment_event_cols = {
        col["name"]: col for col in inspector.get_columns("shipment_events", schema="logix")
    }
    if "relay_id" not in shipment_event_cols:
        op.add_column(
            "shipment_events",
            sa.Column("relay_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema="logix",
        )

    event_fks = inspector.get_foreign_keys("shipment_events", schema="logix")
    event_fk_names = {fk.get("name") for fk in event_fks}
    if "fk_shipment_events_relay_id_relay_points" not in event_fk_names:
        op.create_foreign_key(
            "fk_shipment_events_relay_id_relay_points",
            "shipment_events",
            "relay_points",
            ["relay_id"],
            ["id"],
            source_schema="logix",
            referent_schema="logix",
        )

    code_cols = {col["name"]: col for col in inspector.get_columns("shipment_codes", schema="logix")}
    if code_cols.get("shipment_id", {}).get("nullable", True):
        op.alter_column(
            "shipment_codes",
            "shipment_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=False,
            schema="logix",
        )
    if code_cols.get("code_hash", {}).get("nullable", True):
        op.alter_column(
            "shipment_codes",
            "code_hash",
            existing_type=sa.TEXT(),
            nullable=False,
            schema="logix",
        )
    if code_cols.get("expires_at", {}).get("nullable", True):
        op.alter_column(
            "shipment_codes",
            "expires_at",
            existing_type=postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            schema="logix",
        )

    notif_cols = {col["name"]: col for col in inspector.get_columns("notifications", schema="logix")}
    if "created_at" not in notif_cols:
        op.add_column(
            "notifications",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column(
            "notifications",
            "created_at",
            server_default=None,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            schema="logix",
        )


def downgrade() -> None:
    op.drop_column("notifications", "created_at", schema="logix")

    op.alter_column(
        "shipment_codes",
        "expires_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=True,
        schema="logix",
    )
    op.alter_column(
        "shipment_codes",
        "code_hash",
        existing_type=sa.TEXT(),
        nullable=True,
        schema="logix",
    )
    op.alter_column(
        "shipment_codes",
        "shipment_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
        schema="logix",
    )

    op.drop_constraint(
        "fk_shipment_events_relay_id_relay_points",
        "shipment_events",
        schema="logix",
        type_="foreignkey",
    )
    op.drop_column("shipment_events", "relay_id", schema="logix")
    op.drop_column("shipments", "sender_phone", schema="logix")
