"""db automation triggers for shipments and relay inventory

Revision ID: 20260425_0023
Revises: 20260425_0022
Create Date: 2026-04-25 14:00:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260425_0023"
down_revision: str | None = "20260425_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_uuid_v4_fallback()
        RETURNS uuid
        LANGUAGE plpgsql
        AS $$
        DECLARE
            hash text;
            variant text;
        BEGIN
            hash := md5(random()::text || clock_timestamp()::text || txid_current()::text);
            variant := substr('89ab', (floor(random() * 4)::int + 1), 1);
            RETURN (
                substr(hash, 1, 8) || '-' ||
                substr(hash, 9, 4) || '-' ||
                '4' || substr(hash, 14, 3) || '-' ||
                variant || substr(hash, 18, 3) || '-' ||
                substr(hash, 21, 12)
            )::uuid;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_generate_shipment_no()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.shipment_no IS NULL OR btrim(NEW.shipment_no) = '' THEN
                NEW.shipment_no :=
                    'PBL-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' ||
                    upper(substr(replace(logix.fn_uuid_v4_fallback()::text, '-', ''), 1, 6));
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_generate_shipment_no ON logix.shipments")
    op.execute(
        """
        CREATE TRIGGER trg_generate_shipment_no
        BEFORE INSERT ON logix.shipments
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_generate_shipment_no();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_shipment_status_event()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status THEN
                INSERT INTO logix.shipment_events (
                    id,
                    shipment_id,
                    relay_id,
                    event_type,
                    metadata,
                    created_at
                )
                VALUES (
                    logix.fn_uuid_v4_fallback(),
                    NEW.id,
                    NULL,
                    NEW.status,
                    NULL,
                    NOW()
                );
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_shipment_status_event ON logix.shipments")
    op.execute(
        """
        CREATE TRIGGER trg_shipment_status_event
        AFTER UPDATE ON logix.shipments
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_shipment_status_event();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_relay_inventory()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.relay_id IS NULL THEN
                RETURN NEW;
            END IF;

            IF NEW.event_type = 'arrived_at_relay' THEN
                UPDATE logix.relay_inventory
                SET present = TRUE
                WHERE shipment_id = NEW.shipment_id
                  AND relay_id = NEW.relay_id;

                IF NOT FOUND THEN
                    INSERT INTO logix.relay_inventory (id, relay_id, shipment_id, present)
                    VALUES (logix.fn_uuid_v4_fallback(), NEW.relay_id, NEW.shipment_id, TRUE);
                END IF;
            ELSIF NEW.event_type IN ('departed_relay', 'loaded_on_trip') THEN
                UPDATE logix.relay_inventory
                SET present = FALSE
                WHERE shipment_id = NEW.shipment_id
                  AND relay_id = NEW.relay_id;
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_relay_inventory ON logix.shipment_events")
    op.execute(
        """
        CREATE TRIGGER trg_relay_inventory
        AFTER INSERT ON logix.shipment_events
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_relay_inventory();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_sync_shipment_status_from_event()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.event_type = 'arrived_at_relay' THEN
                UPDATE logix.shipments
                SET status = 'ready_for_pickup',
                    updated_at = NOW()
                WHERE id = NEW.shipment_id
                  AND status IS DISTINCT FROM 'ready_for_pickup';
            ELSIF NEW.event_type IN ('loaded_on_trip', 'departed_relay') THEN
                UPDATE logix.shipments
                SET status = 'in_transit',
                    updated_at = NOW()
                WHERE id = NEW.shipment_id
                  AND status IS DISTINCT FROM 'in_transit';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_sync_shipment_status_from_event ON logix.shipment_events")
    op.execute(
        """
        CREATE TRIGGER trg_sync_shipment_status_from_event
        AFTER INSERT ON logix.shipment_events
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_sync_shipment_status_from_event();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sync_shipment_status_from_event ON logix.shipment_events")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_sync_shipment_status_from_event()")

    op.execute("DROP TRIGGER IF EXISTS trg_relay_inventory ON logix.shipment_events")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_relay_inventory()")

    op.execute("DROP TRIGGER IF EXISTS trg_shipment_status_event ON logix.shipments")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_shipment_status_event()")

    op.execute("DROP TRIGGER IF EXISTS trg_generate_shipment_no ON logix.shipments")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_generate_shipment_no()")

    op.execute("DROP FUNCTION IF EXISTS logix.fn_uuid_v4_fallback()")
