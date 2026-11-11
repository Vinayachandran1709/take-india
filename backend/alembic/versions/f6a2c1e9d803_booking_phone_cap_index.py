"""Index the rolling per-phone booking limit query.

Revision ID: f6a2c1e9d803
Revises: e913f6b2a004
"""

from alembic import op

revision = "f6a2c1e9d803"
down_revision = "e913f6b2a004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_bookings_merchant_customer_created",
        "bookings",
        ["merchant_id", "customer_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_bookings_merchant_customer_created", table_name="bookings")
