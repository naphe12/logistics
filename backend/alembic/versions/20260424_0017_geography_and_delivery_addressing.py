"""add provinces/communes and delivery addressing links

Revision ID: 20260424_0017
Revises: 20260424_0016
Create Date: 2026-04-24 23:35:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260424_0017"
down_revision: str | None = "20260424_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "logix"


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names(schema=SCHEMA)


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {col["name"] for col in inspector.get_columns(table_name, schema=SCHEMA)}


def _fk_exists(inspector: sa.Inspector, table_name: str, fk_name: str) -> bool:
    return fk_name in {fk["name"] for fk in inspector.get_foreign_keys(table_name, schema=SCHEMA)}


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name, schema=SCHEMA)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "provinces"):
        op.create_table(
            "provinces",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.UniqueConstraint("name", name="uq_provinces_name"),
            schema=SCHEMA,
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "communes"):
        op.create_table(
            "communes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("province_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.ForeignKeyConstraint(["province_id"], [f"{SCHEMA}.provinces.id"], name="fk_communes_province_id_provinces"),
            sa.UniqueConstraint("province_id", "name", name="uq_communes_province_name"),
            schema=SCHEMA,
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "addresses"):
        if not _column_exists(inspector, "addresses", "province_id"):
            op.add_column("addresses", sa.Column("province_id", postgresql.UUID(as_uuid=True), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "addresses", "commune_id"):
            op.add_column("addresses", sa.Column("commune_id", postgresql.UUID(as_uuid=True), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "addresses", "zone"):
            op.add_column("addresses", sa.Column("zone", sa.String(length=120), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "addresses", "colline"):
            op.add_column("addresses", sa.Column("colline", sa.String(length=120), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "addresses", "quartier"):
            op.add_column("addresses", sa.Column("quartier", sa.String(length=120), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "addresses", "landmark"):
            op.add_column("addresses", sa.Column("landmark", sa.Text(), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "addresses", "latitude"):
            op.add_column("addresses", sa.Column("latitude", sa.Numeric(9, 6), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "addresses", "longitude"):
            op.add_column("addresses", sa.Column("longitude", sa.Numeric(9, 6), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "addresses", "raw_input"):
            op.add_column("addresses", sa.Column("raw_input", sa.Text(), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "addresses", "created_at"):
            op.add_column(
                "addresses",
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
                schema=SCHEMA,
            )

        inspector = sa.inspect(bind)
        if not _fk_exists(inspector, "addresses", "fk_addresses_province_id_provinces"):
            op.create_foreign_key(
                "fk_addresses_province_id_provinces",
                "addresses",
                "provinces",
                ["province_id"],
                ["id"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA,
            )
        if not _fk_exists(inspector, "addresses", "fk_addresses_commune_id_communes"):
            op.create_foreign_key(
                "fk_addresses_commune_id_communes",
                "addresses",
                "communes",
                ["commune_id"],
                ["id"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA,
            )
        if not _index_exists(inspector, "addresses", "idx_addresses_commune"):
            op.create_index("idx_addresses_commune", "addresses", ["commune_id"], schema=SCHEMA)
        if not _index_exists(inspector, "addresses", "idx_addresses_zone"):
            op.create_index("idx_addresses_zone", "addresses", ["zone"], schema=SCHEMA)

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "relay_points"):
        if not _column_exists(inspector, "relay_points", "province_id"):
            op.add_column("relay_points", sa.Column("province_id", postgresql.UUID(as_uuid=True), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "relay_points", "commune_id"):
            op.add_column("relay_points", sa.Column("commune_id", postgresql.UUID(as_uuid=True), nullable=True), schema=SCHEMA)

        inspector = sa.inspect(bind)
        if not _fk_exists(inspector, "relay_points", "fk_relay_points_province_id_provinces"):
            op.create_foreign_key(
                "fk_relay_points_province_id_provinces",
                "relay_points",
                "provinces",
                ["province_id"],
                ["id"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA,
            )
        if not _fk_exists(inspector, "relay_points", "fk_relay_points_commune_id_communes"):
            op.create_foreign_key(
                "fk_relay_points_commune_id_communes",
                "relay_points",
                "communes",
                ["commune_id"],
                ["id"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA,
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "shipments"):
        if not _column_exists(inspector, "shipments", "origin_relay_id"):
            op.add_column("shipments", sa.Column("origin_relay_id", postgresql.UUID(as_uuid=True), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "shipments", "destination_relay_id"):
            op.add_column("shipments", sa.Column("destination_relay_id", postgresql.UUID(as_uuid=True), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "shipments", "delivery_address_id"):
            op.add_column("shipments", sa.Column("delivery_address_id", postgresql.UUID(as_uuid=True), nullable=True), schema=SCHEMA)
        if not _column_exists(inspector, "shipments", "delivery_note"):
            op.add_column("shipments", sa.Column("delivery_note", sa.String(length=500), nullable=True), schema=SCHEMA)

        inspector = sa.inspect(bind)
        if not _fk_exists(inspector, "shipments", "fk_shipments_origin_relay_id_relay_points"):
            op.create_foreign_key(
                "fk_shipments_origin_relay_id_relay_points",
                "shipments",
                "relay_points",
                ["origin_relay_id"],
                ["id"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA,
            )
        if not _fk_exists(inspector, "shipments", "fk_shipments_destination_relay_id_relay_points"):
            op.create_foreign_key(
                "fk_shipments_destination_relay_id_relay_points",
                "shipments",
                "relay_points",
                ["destination_relay_id"],
                ["id"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA,
            )
        if not _fk_exists(inspector, "shipments", "fk_shipments_delivery_address_id_addresses"):
            op.create_foreign_key(
                "fk_shipments_delivery_address_id_addresses",
                "shipments",
                "addresses",
                ["delivery_address_id"],
                ["id"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "shipments"):
        if _fk_exists(inspector, "shipments", "fk_shipments_delivery_address_id_addresses"):
            op.drop_constraint("fk_shipments_delivery_address_id_addresses", "shipments", schema=SCHEMA, type_="foreignkey")
        if _fk_exists(inspector, "shipments", "fk_shipments_destination_relay_id_relay_points"):
            op.drop_constraint("fk_shipments_destination_relay_id_relay_points", "shipments", schema=SCHEMA, type_="foreignkey")
        if _fk_exists(inspector, "shipments", "fk_shipments_origin_relay_id_relay_points"):
            op.drop_constraint("fk_shipments_origin_relay_id_relay_points", "shipments", schema=SCHEMA, type_="foreignkey")
        for col in ["delivery_note", "delivery_address_id", "destination_relay_id", "origin_relay_id"]:
            if _column_exists(inspector, "shipments", col):
                op.drop_column("shipments", col, schema=SCHEMA)

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "relay_points"):
        if _fk_exists(inspector, "relay_points", "fk_relay_points_commune_id_communes"):
            op.drop_constraint("fk_relay_points_commune_id_communes", "relay_points", schema=SCHEMA, type_="foreignkey")
        if _fk_exists(inspector, "relay_points", "fk_relay_points_province_id_provinces"):
            op.drop_constraint("fk_relay_points_province_id_provinces", "relay_points", schema=SCHEMA, type_="foreignkey")
        for col in ["commune_id", "province_id"]:
            if _column_exists(inspector, "relay_points", col):
                op.drop_column("relay_points", col, schema=SCHEMA)

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "addresses"):
        if _index_exists(inspector, "addresses", "idx_addresses_zone"):
            op.drop_index("idx_addresses_zone", table_name="addresses", schema=SCHEMA)
        if _index_exists(inspector, "addresses", "idx_addresses_commune"):
            op.drop_index("idx_addresses_commune", table_name="addresses", schema=SCHEMA)
        if _fk_exists(inspector, "addresses", "fk_addresses_commune_id_communes"):
            op.drop_constraint("fk_addresses_commune_id_communes", "addresses", schema=SCHEMA, type_="foreignkey")
        if _fk_exists(inspector, "addresses", "fk_addresses_province_id_provinces"):
            op.drop_constraint("fk_addresses_province_id_provinces", "addresses", schema=SCHEMA, type_="foreignkey")
        for col in ["created_at", "raw_input", "longitude", "latitude", "landmark", "quartier", "colline", "zone", "commune_id", "province_id"]:
            if _column_exists(inspector, "addresses", col):
                op.drop_column("addresses", col, schema=SCHEMA)

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "communes"):
        op.drop_table("communes", schema=SCHEMA)
    if _table_exists(inspector, "provinces"):
        op.drop_table("provinces", schema=SCHEMA)
