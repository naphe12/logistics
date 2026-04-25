"""more db automation guards and audit triggers

Revision ID: 20260425_0024
Revises: 20260425_0023
Create Date: 2026-04-25 15:00:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260425_0024"
down_revision: str | None = "20260425_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_touch_updated_at()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_touch_shipments_updated_at ON logix.shipments")
    op.execute(
        """
        CREATE TRIGGER trg_touch_shipments_updated_at
        BEFORE UPDATE ON logix.shipments
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_touch_updated_at();
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_touch_incidents_updated_at ON logix.incidents")
    op.execute(
        """
        CREATE TRIGGER trg_touch_incidents_updated_at
        BEFORE UPDATE ON logix.incidents
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_touch_updated_at();
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_touch_claims_updated_at ON logix.claims")
    op.execute(
        """
        CREATE TRIGGER trg_touch_claims_updated_at
        BEFORE UPDATE ON logix.claims
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_touch_updated_at();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_audit_shipment_status_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status THEN
                INSERT INTO logix.audit_logs (
                    id, entity, action, method, endpoint, request_id, created_at
                )
                VALUES (
                    logix.fn_uuid_v4_fallback(),
                    'shipments',
                    'status_changed',
                    'TRIGGER',
                    'trg_audit_shipment_status_change',
                    left(coalesce(OLD.status, 'null') || '->' || coalesce(NEW.status, 'null'), 64),
                    NOW()
                );
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_audit_shipment_status_change ON logix.shipments")
    op.execute(
        """
        CREATE TRIGGER trg_audit_shipment_status_change
        AFTER UPDATE ON logix.shipments
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_audit_shipment_status_change();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_audit_incident_status_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status THEN
                INSERT INTO logix.audit_logs (
                    id, entity, action, method, endpoint, request_id, created_at
                )
                VALUES (
                    logix.fn_uuid_v4_fallback(),
                    'incidents',
                    'status_changed',
                    'TRIGGER',
                    'trg_audit_incident_status_change',
                    left(coalesce(OLD.status, 'null') || '->' || coalesce(NEW.status, 'null'), 64),
                    NOW()
                );
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_audit_incident_status_change ON logix.incidents")
    op.execute(
        """
        CREATE TRIGGER trg_audit_incident_status_change
        AFTER UPDATE ON logix.incidents
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_audit_incident_status_change();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_audit_claim_status_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status THEN
                INSERT INTO logix.audit_logs (
                    id, entity, action, method, endpoint, request_id, created_at
                )
                VALUES (
                    logix.fn_uuid_v4_fallback(),
                    'claims',
                    'status_changed',
                    'TRIGGER',
                    'trg_audit_claim_status_change',
                    left(coalesce(OLD.status, 'null') || '->' || coalesce(NEW.status, 'null'), 64),
                    NOW()
                );
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_audit_claim_status_change ON logix.claims")
    op.execute(
        """
        CREATE TRIGGER trg_audit_claim_status_change
        AFTER UPDATE ON logix.claims
        FOR EACH ROW
        EXECUTE FUNCTION logix.fn_audit_claim_status_change();
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_claim_amount_approved_lte_requested'
            ) THEN
                ALTER TABLE logix.claims
                ADD CONSTRAINT ck_claim_amount_approved_lte_requested
                CHECK (
                    amount_approved IS NULL
                    OR amount_requested IS NULL
                    OR amount_approved <= amount_requested
                );
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_claim_amount_requested_positive'
            ) THEN
                ALTER TABLE logix.claims
                ADD CONSTRAINT ck_claim_amount_requested_positive
                CHECK (amount_requested IS NULL OR amount_requested > 0);
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_shipment_insurance_non_negative'
            ) THEN
                ALTER TABLE logix.shipments
                ADD CONSTRAINT ck_shipment_insurance_non_negative
                CHECK (
                    coalesce(declared_value, 0) >= 0
                    AND coalesce(insurance_fee, 0) >= 0
                    AND coalesce(coverage_amount, 0) >= 0
                );
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION logix.fn_expire_shipment_codes()
        RETURNS integer
        LANGUAGE plpgsql
        AS $$
        DECLARE
            updated_count integer;
        BEGIN
            UPDATE logix.shipment_codes
            SET code_last4 = NULL
            WHERE expires_at < NOW()
              AND code_last4 IS NOT NULL;

            GET DIAGNOSTICS updated_count = ROW_COUNT;
            RETURN updated_count;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS logix.fn_expire_shipment_codes()")

    op.execute("ALTER TABLE logix.shipments DROP CONSTRAINT IF EXISTS ck_shipment_insurance_non_negative")
    op.execute("ALTER TABLE logix.claims DROP CONSTRAINT IF EXISTS ck_claim_amount_requested_positive")
    op.execute("ALTER TABLE logix.claims DROP CONSTRAINT IF EXISTS ck_claim_amount_approved_lte_requested")

    op.execute("DROP TRIGGER IF EXISTS trg_audit_claim_status_change ON logix.claims")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_audit_claim_status_change()")

    op.execute("DROP TRIGGER IF EXISTS trg_audit_incident_status_change ON logix.incidents")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_audit_incident_status_change()")

    op.execute("DROP TRIGGER IF EXISTS trg_audit_shipment_status_change ON logix.shipments")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_audit_shipment_status_change()")

    op.execute("DROP TRIGGER IF EXISTS trg_touch_claims_updated_at ON logix.claims")
    op.execute("DROP TRIGGER IF EXISTS trg_touch_incidents_updated_at ON logix.incidents")
    op.execute("DROP TRIGGER IF EXISTS trg_touch_shipments_updated_at ON logix.shipments")
    op.execute("DROP FUNCTION IF EXISTS logix.fn_touch_updated_at()")
