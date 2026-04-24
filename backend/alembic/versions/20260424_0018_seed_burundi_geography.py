"""seed initial Burundi provinces and communes

Revision ID: 20260424_0018
Revises: 20260424_0017
Create Date: 2026-04-24 23:55:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260424_0018"
down_revision: str | None = "20260424_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "logix"


PROVINCES = [
    "Bubanza",
    "Bujumbura Mairie",
    "Bujumbura Rural",
    "Bururi",
    "Cankuzo",
    "Cibitoke",
    "Gitega",
    "Karuzi",
    "Kayanza",
    "Kirundo",
    "Makamba",
    "Muramvya",
    "Muyinga",
    "Mwaro",
    "Ngozi",
    "Rumonge",
    "Rutana",
    "Ruyigi",
]

COMMUNES = [
    ("Bujumbura Mairie", "Mukaza"),
    ("Bujumbura Mairie", "Ntahangwa"),
    ("Bujumbura Mairie", "Muha"),
    ("Gitega", "Gitega"),
    ("Gitega", "Bugendana"),
    ("Gitega", "Makebuko"),
    ("Ngozi", "Ngozi"),
    ("Ngozi", "Kiremba"),
    ("Rumonge", "Rumonge"),
    ("Rumonge", "Bugarama"),
    ("Cibitoke", "Cibitoke"),
    ("Cibitoke", "Mugina"),
    ("Kayanza", "Kayanza"),
    ("Kayanza", "Matongo"),
    ("Muyinga", "Muyinga"),
    ("Muyinga", "Giteranyi"),
    ("Kirundo", "Kirundo"),
    ("Kirundo", "Busoni"),
    ("Bururi", "Bururi"),
    ("Bururi", "Matana"),
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

    bind.execute(
        sa.text(
            f"""
            DELETE FROM {SCHEMA}.provinces
            WHERE name = ANY(:names)
            """
        ),
        {"names": PROVINCES},
    )
