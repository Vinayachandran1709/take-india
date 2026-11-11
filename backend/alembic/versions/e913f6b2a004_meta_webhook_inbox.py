"""Durable, data-minimal inbox for verified Meta webhook deliveries.

Revision ID: e913f6b2a004
Revises: d4c2e6a91b70
"""

import sqlalchemy as sa

from alembic import op

revision = "e913f6b2a004"
down_revision = "d4c2e6a91b70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_webhook_events",
        sa.Column("body_sha256", sa.String(64), primary_key=True),
        sa.Column("object_type", sa.String(80), nullable=False),
        sa.Column("processing_status", sa.String(20), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "processing_status IN ('received', 'ignored', 'processed')",
            name="meta_webhook_processing_status",
        ),
    )
    op.create_index("ix_meta_webhook_events_received_at", "meta_webhook_events", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_meta_webhook_events_received_at", table_name="meta_webhook_events")
    op.drop_table("meta_webhook_events")
