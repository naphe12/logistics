"""shipment schedules and recurring sends

Revision ID: 20260425_0026
Revises: 20260425_0025
Create Date: 2026-04-25 18:30:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260425_0026"
down_revision: str | None = "20260425_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS logix.shipment_schedules (
            id uuid PRIMARY KEY,
            sender_id uuid NULL REFERENCES logix.users(id),
            sender_phone varchar(20) NULL,
            receiver_name varchar(180) NULL,
            receiver_phone varchar(20) NULL,
            origin_relay_id uuid NULL REFERENCES logix.relay_points(id),
            destination_relay_id uuid NULL REFERENCES logix.relay_points(id),
            delivery_address_id uuid NULL REFERENCES logix.addresses(id),
            delivery_note varchar(500) NULL,
            declared_value numeric(12,2) NULL,
            insurance_opt_in boolean NOT NULL DEFAULT false,
            frequency varchar(20) NOT NULL DEFAULT 'once',
            interval_count integer NOT NULL DEFAULT 1,
            day_of_week integer NULL,
            day_of_month integer NULL,
            start_at timestamptz NOT NULL,
            next_run_at timestamptz NULL,
            last_run_at timestamptz NULL,
            end_at timestamptz NULL,
            remaining_runs integer NULL,
            is_active boolean NOT NULL DEFAULT true,
            last_error varchar(1000) NULL,
            metadata jsonb NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_shipment_schedules_next_run
        ON logix.shipment_schedules (is_active, next_run_at, created_at);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_shipment_schedules_sender_phone
        ON logix.shipment_schedules (sender_phone, created_at);
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_shipment_schedules_frequency'
            ) THEN
                ALTER TABLE logix.shipment_schedules
                ADD CONSTRAINT ck_shipment_schedules_frequency
                CHECK (frequency IN ('once', 'daily', 'weekly', 'monthly'));
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_shipment_schedules_interval_count'
            ) THEN
                ALTER TABLE logix.shipment_schedules
                ADD CONSTRAINT ck_shipment_schedules_interval_count
                CHECK (interval_count >= 1);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_shipment_schedules_day_of_week'
            ) THEN
                ALTER TABLE logix.shipment_schedules
                ADD CONSTRAINT ck_shipment_schedules_day_of_week
                CHECK (day_of_week IS NULL OR (day_of_week >= 0 AND day_of_week <= 6));
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_shipment_schedules_day_of_month'
            ) THEN
                ALTER TABLE logix.shipment_schedules
                ADD CONSTRAINT ck_shipment_schedules_day_of_month
                CHECK (day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31));
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS logix.ix_shipment_schedules_sender_phone")
    op.execute("DROP INDEX IF EXISTS logix.ix_shipment_schedules_next_run")
    op.execute("ALTER TABLE logix.shipment_schedules DROP CONSTRAINT IF EXISTS ck_shipment_schedules_day_of_month")
    op.execute("ALTER TABLE logix.shipment_schedules DROP CONSTRAINT IF EXISTS ck_shipment_schedules_day_of_week")
    op.execute("ALTER TABLE logix.shipment_schedules DROP CONSTRAINT IF EXISTS ck_shipment_schedules_interval_count")
    op.execute("ALTER TABLE logix.shipment_schedules DROP CONSTRAINT IF EXISTS ck_shipment_schedules_frequency")
    op.execute("DROP TABLE IF EXISTS logix.shipment_schedules")
