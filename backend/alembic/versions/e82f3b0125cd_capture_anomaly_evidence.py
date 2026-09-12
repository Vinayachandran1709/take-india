"""Retain duplicate capture evidence and explicit event-ID uniqueness.

Revision ID: e82f3b0125cd
Revises: d71e2a9014bc
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e82f3b0125cd"
down_revision = "d71e2a9014bc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_webhook_config_event", "payment_webhook_events", ["config_id", "provider_event_id"])
    op.create_table("payment_capture_anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_payment_id", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["payment_transactions.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("transaction_id", "provider_payment_id", name="uq_capture_anomaly_payment"),
    )


def downgrade():
    op.drop_table("payment_capture_anomalies")
    op.drop_constraint("uq_webhook_config_event", "payment_webhook_events", type_="unique")
