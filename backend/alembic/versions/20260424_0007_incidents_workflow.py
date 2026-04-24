"""incidents workflow

Revision ID: 20260424_0007
Revises: 20260424_0006
Create Date: 2026-04-24 15:50:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260424_0007"
down_revision: str | None = "20260424_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    incident_cols = {col["name"]: col for col in inspector.get_columns("incidents", schema="logix")}
    if "incident_type" not in incident_cols:
        op.add_column(
            "incidents",
            sa.Column("incident_type", sa.String(length=40), nullable=True),
            schema="logix",
        )
    if "description" not in incident_cols:
        op.add_column(
            "incidents",
            sa.Column("description", sa.Text(), nullable=True),
            schema="logix",
        )
    if "created_at" not in incident_cols:
        op.add_column(
            "incidents",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column(
            "incidents",
            "created_at",
            server_default=None,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            schema="logix",
        )
    if "updated_at" not in incident_cols:
        op.add_column(
            "incidents",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column(
            "incidents",
            "updated_at",
            server_default=None,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            schema="logix",
        )

    updates_cols = {col["name"]: col for col in inspector.get_columns("incident_updates", schema="logix")}
    if "created_at" not in updates_cols:
        op.add_column(
            "incident_updates",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column(
            "incident_updates",
            "created_at",
            server_default=None,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            schema="logix",
        )

    claim_cols = {col["name"]: col for col in inspector.get_columns("claims", schema="logix")}
    if "incident_id" not in claim_cols:
        op.add_column(
            "claims",
            sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema="logix",
        )
    if "status" not in claim_cols:
        op.add_column(
            "claims",
            sa.Column("status", sa.String(length=40), nullable=True),
            schema="logix",
        )
    if "reason" not in claim_cols:
        op.add_column(
            "claims",
            sa.Column("reason", sa.Text(), nullable=True),
            schema="logix",
        )
    if "created_at" not in claim_cols:
        op.add_column(
            "claims",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            schema="logix",
        )
        op.alter_column(
            "claims",
            "created_at",
            server_default=None,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            schema="logix",
        )

    claim_fks = inspector.get_foreign_keys("claims", schema="logix")
    fk_names = {fk.get("name") for fk in claim_fks}
    if "fk_claims_incident_id_incidents" not in fk_names:
        op.create_foreign_key(
            "fk_claims_incident_id_incidents",
            "claims",
            "incidents",
            ["incident_id"],
            ["id"],
            source_schema="logix",
            referent_schema="logix",
        )

    op.execute(
        """
        INSERT INTO logix.incident_statuses (code, label)
        VALUES
            ('open', 'Open'),
            ('investigating', 'Investigating'),
            ('resolved', 'Resolved'),
            ('closed', 'Closed'),
            ('rejected', 'Rejected')
        ON CONFLICT (code)
        DO UPDATE SET label = EXCLUDED.label
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM logix.incident_statuses
        WHERE code IN ('open', 'investigating', 'resolved', 'closed', 'rejected')
        """
    )

    op.drop_constraint(
        "fk_claims_incident_id_incidents",
        "claims",
        schema="logix",
        type_="foreignkey",
    )

    op.drop_column("claims", "created_at", schema="logix")
    op.drop_column("claims", "reason", schema="logix")
    op.drop_column("claims", "status", schema="logix")
    op.drop_column("claims", "incident_id", schema="logix")

    op.drop_column("incident_updates", "created_at", schema="logix")

    op.drop_column("incidents", "updated_at", schema="logix")
    op.drop_column("incidents", "created_at", schema="logix")
    op.drop_column("incidents", "description", schema="logix")
    op.drop_column("incidents", "incident_type", schema="logix")
