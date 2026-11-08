"""Add service change policies and a future customer management token digest.

Revision ID: c6b2e4d9108a
Revises: a7d8c9012f34
"""

import sqlalchemy as sa
from alembic import op

revision = "c6b2e4d9108a"
down_revision = "a7d8c9012f34"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("services", sa.Column("reschedule_cutoff_hours", sa.Integer(), nullable=True))
    op.add_column(
        "services",
        sa.Column(
            "allow_cancellations", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column(
        "services",
        sa.Column("cancel_cutoff_hours", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint(
        "ck_services_reschedule_cutoff_nonnegative",
        "services",
        "reschedule_cutoff_hours IS NULL OR reschedule_cutoff_hours >= 0",
    )
    op.create_check_constraint(
        "ck_services_cancel_cutoff_nonnegative", "services", "cancel_cutoff_hours >= 0"
    )

    op.add_column("bookings", sa.Column("management_token_hash", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_bookings_management_token_hash", "bookings", ["management_token_hash"]
    )


def downgrade():
    op.drop_constraint("uq_bookings_management_token_hash", "bookings", type_="unique")
    op.drop_column("bookings", "management_token_hash")

    op.drop_constraint("ck_services_cancel_cutoff_nonnegative", "services", type_="check")
    op.drop_constraint("ck_services_reschedule_cutoff_nonnegative", "services", type_="check")
    op.drop_column("services", "cancel_cutoff_hours")
    op.drop_column("services", "allow_cancellations")
    op.drop_column("services", "reschedule_cutoff_hours")
