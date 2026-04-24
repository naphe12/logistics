"""seed shipment statuses

Revision ID: 20260424_0004
Revises: 20260423_0003
Create Date: 2026-04-24 13:15:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260424_0004"
down_revision: str | None = "20260423_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO logix.shipment_statuses (code, label)
        VALUES
            ('created', 'Created'),
            ('ready_for_pickup', 'Ready for pickup'),
            ('picked_up', 'Picked up'),
            ('in_transit', 'In transit'),
            ('arrived_at_relay', 'Arrived at relay'),
            ('delivered', 'Delivered')
        ON CONFLICT (code)
        DO UPDATE SET label = EXCLUDED.label
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM logix.shipment_statuses
        WHERE code IN (
            'created',
            'ready_for_pickup',
            'picked_up',
            'in_transit',
            'arrived_at_relay',
            'delivered'
        )
        """
    )
