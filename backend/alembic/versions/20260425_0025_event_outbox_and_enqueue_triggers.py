"""event outbox and enqueue triggers

Revision ID: 20260425_0025
Revises: 20260425_0024
Create Date: 2026-04-25 16:00:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260425_0025"
down_revision: str | None = "20260425_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS logix.event_outbox (
            id uuid PRIMARY KEY,
            aggregate_type varchar(60) NOT NULL,
            aggregate_id uuid NULL,
            event_type varchar(120) NOT NULL,
            payload jsonb NULL,
            status varchar(20) NOT NULL DEFAULT 'queued',
            attempts_count integer NOT NULL DEFAULT 0,
            max_attempts integer NOT NULL DEFAULT 10,
            available_at timestamptz NOT NULL DEFAULT now(),
            last_error text NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            processed_at timestamptz NULL
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_event_outbox_status_available
        ON logix.event_outbox (status, available_at, created_at);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_event_outbox_aggregate
        ON logix.event_outbox (aggregate_type, aggregate_id, created_at);
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_event_outbox_status'
            ) THEN
                ALTER TABLE logix.event_outbox
                ADD CONSTRAINT ck_event_outbox_status
                CHECK (status IN ('queued', 'processing', 'done', 'failed', 'dead'));
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_outbox_enqueue_shipment_event()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            INSERT INTO logix.event_outbox (
                id, aggregate_type, aggregate_id, event_type, payload, status, attempts_count, max_attempts, available_at, created_at
            )
            VALUES (
                logix.fn_uuid_v4_fallback(),
                'shipment',
                NEW.shipment_id,
                'shipment.event.created',
                jsonb_build_object(
                    'shipment_event_id', NEW.id,
                    'shipment_id', NEW.shipment_id,
                    'relay_id', NEW.relay_id,
                    'event_type', NEW.event_type,
                    'created_at', NEW.created_at
                ),
                'queued',
                0,
                10,
                now(),
                now()
            );
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_outbox_enqueue_shipment_event ON logix.shipment_events")
    op.execute(
        """
        CREATE TRIGGER trg_outbox_enqueue_shipment_event
        AFTER INSERT ON logix.shipment_events
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_outbox_enqueue_shipment_event();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_outbox_enqueue_shipment_status_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status THEN
                INSERT INTO logix.event_outbox (
                    id, aggregate_type, aggregate_id, event_type, payload, status, attempts_count, max_attempts, available_at, created_at
                )
                VALUES (
                    logix.fn_uuid_v4_fallback(),
                    'shipment',
                    NEW.id,
                    'shipment.status.changed',
                    jsonb_build_object(
                        'shipment_id', NEW.id,
                        'shipment_no', NEW.shipment_no,
                        'sender_phone', NEW.sender_phone,
                        'receiver_phone', NEW.receiver_phone,
                        'old_status', OLD.status,
                        'new_status', NEW.status
                    ),
                    'queued',
                    0,
                    10,
                    now(),
                    now()
                );
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_outbox_enqueue_shipment_status_change ON logix.shipments")
    op.execute(
        """
        CREATE TRIGGER trg_outbox_enqueue_shipment_status_change
        AFTER UPDATE ON logix.shipments
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_outbox_enqueue_shipment_status_change();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_outbox_enqueue_incident_status_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status THEN
                INSERT INTO logix.event_outbox (
                    id, aggregate_type, aggregate_id, event_type, payload, status, attempts_count, max_attempts, available_at, created_at
                )
                VALUES (
                    logix.fn_uuid_v4_fallback(),
                    'incident',
                    NEW.id,
                    'incident.status.changed',
                    jsonb_build_object(
                        'incident_id', NEW.id,
                        'shipment_id', NEW.shipment_id,
                        'incident_type', NEW.incident_type,
                        'old_status', OLD.status,
                        'new_status', NEW.status
                    ),
                    'queued',
                    0,
                    10,
                    now(),
                    now()
                );
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_outbox_enqueue_incident_status_change ON logix.incidents")
    op.execute(
        """
        CREATE TRIGGER trg_outbox_enqueue_incident_status_change
        AFTER UPDATE ON logix.incidents
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_outbox_enqueue_incident_status_change();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_outbox_enqueue_claim_status_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status THEN
                INSERT INTO logix.event_outbox (
                    id, aggregate_type, aggregate_id, event_type, payload, status, attempts_count, max_attempts, available_at, created_at
                )
                VALUES (
                    logix.fn_uuid_v4_fallback(),
                    'claim',
                    NEW.id,
                    'claim.status.changed',
                    jsonb_build_object(
                        'claim_id', NEW.id,
                        'shipment_id', NEW.shipment_id,
                        'incident_id', NEW.incident_id,
                        'old_status', OLD.status,
                        'new_status', NEW.status,
                        'amount_requested', NEW.amount_requested,
                        'amount_approved', NEW.amount_approved,
                        'risk_score', NEW.risk_score
                    ),
                    'queued',
                    0,
                    10,
                    now(),
                    now()
                );
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_outbox_enqueue_claim_status_change ON logix.claims")
    op.execute(
        """
        CREATE TRIGGER trg_outbox_enqueue_claim_status_change
        AFTER UPDATE ON logix.claims
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_outbox_enqueue_claim_status_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_outbox_enqueue_claim_status_change ON logix.claims")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_outbox_enqueue_claim_status_change()")

    op.execute("DROP TRIGGER IF EXISTS trg_outbox_enqueue_incident_status_change ON logix.incidents")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_outbox_enqueue_incident_status_change()")

    op.execute("DROP TRIGGER IF EXISTS trg_outbox_enqueue_shipment_status_change ON logix.shipments")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_outbox_enqueue_shipment_status_change()")

    op.execute("DROP TRIGGER IF EXISTS trg_outbox_enqueue_shipment_event ON logix.shipment_events")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_outbox_enqueue_shipment_event()")

    op.execute("DROP INDEX IF EXISTS logix.ix_event_outbox_aggregate")
    op.execute("DROP INDEX IF EXISTS logix.ix_event_outbox_status_available")
    op.execute("ALTER TABLE logix.event_outbox DROP CONSTRAINT IF EXISTS ck_event_outbox_status")
    op.execute("DROP TABLE IF EXISTS logix.event_outbox")
