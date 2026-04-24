"""seed starter communes for 5 active provinces

Revision ID: 20260425_0020
Revises: 20260424_0019
Create Date: 2026-04-25 00:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260425_0020"
down_revision: str | None = "20260424_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "logix"

COMMUNES: list[tuple[str, str]] = [
    ("Bujumbura", "Mukaza"),
    ("Bujumbura", "Ntahangwa"),
    ("Bujumbura", "Muha"),
    ("Bujumbura", "Mutimbuzi"),
    ("Bujumbura", "Kabezi"),
    ("Gitega", "Gitega"),
    ("Gitega", "Bugendana"),
    ("Gitega", "Makebuko"),
    ("Gitega", "Mutaho"),
    ("Gitega", "Giheta"),
    ("Butanyerera", "Ngozi"),
    ("Butanyerera", "Kayanza"),
    ("Butanyerera", "Kirundo"),
    ("Butanyerera", "Muyinga"),
    ("Butanyerera", "Giteranyi"),
    ("Burunga", "Rumonge"),
    ("Burunga", "Bururi"),
    ("Burunga", "Makamba"),
    ("Burunga", "Nyanza-Lac"),
    ("Burunga", "Matana"),
    ("Buhumuza", "Ruyigi"),
    ("Buhumuza", "Cankuzo"),
    ("Buhumuza", "Rutana"),
    ("Buhumuza", "Karuzi"),
    ("Buhumuza", "Gisuru"),
]


def upgrade() -> None:
    bind = op.get_bind()
    for province_name, commune_name in COMMUNES:
        bind.execute(
            sa.text(
                f"""
                INSERT INTO {SCHEMA}.communes (province_id, name)
                SELECT p.id, :commune_name
                FROM {SCHEMA}.provinces p
                WHERE p.name = :province_name
                ON CONFLICT (province_id, name) DO NOTHING
                """
            ),
            {"province_name": province_name, "commune_name": commune_name},
        )


def downgrade() -> None:
    bind = op.get_bind()
    for province_name, commune_name in COMMUNES:
        bind.execute(
            sa.text(
                f"""
                DELETE FROM {SCHEMA}.communes c
                USING {SCHEMA}.provinces p
                WHERE c.province_id = p.id
                  AND p.name = :province_name
                  AND c.name = :commune_name
                """
            ),
            {"province_name": province_name, "commune_name": commune_name},
        )
