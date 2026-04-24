"""seed 5 active Burundi provinces

Revision ID: 20260424_0019
Revises: 20260424_0018
Create Date: 2026-04-24 23:59:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260424_0019"
down_revision: str | None = "20260424_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "logix"

PROVINCES = [
    "Bujumbura",
    "Gitega",
    "Butanyerera",
    "Burunga",
    "Buhumuza",
]


def upgrade() -> None:
    bind = op.get_bind()
    for province in PROVINCES:
        bind.execute(
            sa.text(
                f"""
                INSERT INTO {SCHEMA}.provinces (name)
                VALUES (:name)
                ON CONFLICT (name) DO NOTHING
                """
            ),
            {"name": province},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            f"""
            DELETE FROM {SCHEMA}.provinces
            WHERE name = ANY(:names)
            """
        ),
        {"names": PROVINCES},
    )
