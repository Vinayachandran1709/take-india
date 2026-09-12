"""Phase 2 payment records and public booking access.

Revision ID: d71e2a9014bc
Revises: cbdbf24900c6
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d71e2a9014bc"
down_revision = "cbdbf24900c6"
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def uid(name, **kwargs):
    return sa.Column(name, postgresql.UUID(as_uuid=True), **kwargs)


def upgrade():
    op.add_column("bookings", sa.Column("public_token_hash", sa.String(64), nullable=True))
    op.add_column("bookings", sa.Column("amount_paid", sa.Numeric(12, 2), server_default="0", nullable=False))
    op.add_column("bookings", sa.Column("payment_review_required", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_unique_constraint("uq_booking_id_merchant", "bookings", ["id", "merchant_id"])
    op.create_table("merchant_payment_configs",
        uid("id", primary_key=True), uid("merchant_id", nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("key_id", sa.String(100), nullable=False),
        sa.Column("key_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("webhook_secret_encrypted", sa.Text(), nullable=False),
        uid("webhook_id", nullable=False, unique=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("id", "merchant_id", name="uq_payment_config_id_merchant"),
        sa.CheckConstraint("provider = 'RAZORPAY'", name="provider_razorpay"),
        sa.CheckConstraint("mode IN ('TEST', 'LIVE')", name="valid_mode"),
    )
    op.create_index("uq_current_payment_config", "merchant_payment_configs", ["merchant_id"], unique=True, postgresql_where=sa.text("is_current"))
    op.create_table("payment_transactions",
        uid("id", primary_key=True), uid("merchant_id", nullable=False),
        uid("booking_id", nullable=False), uid("config_id", nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("receipt", sa.String(40), nullable=False, unique=True),
        sa.Column("provider_order_id", sa.String(100), unique=True),
        sa.Column("provider_payment_id", sa.String(100), unique=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("failure_code", sa.String(80)), sa.Column("failure_reason", sa.String(80)),
        sa.Column("reconciliation_state", sa.String(40)),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.ForeignKeyConstraint(["booking_id", "merchant_id"], ["bookings.id", "bookings.merchant_id"], ondelete="RESTRICT", name="fk_payment_booking_tenant"),
        sa.ForeignKeyConstraint(["config_id", "merchant_id"], ["merchant_payment_configs.id", "merchant_payment_configs.merchant_id"], ondelete="RESTRICT", name="fk_payment_config_tenant"),
        sa.CheckConstraint("amount > 0", name="positive_amount"),
        sa.CheckConstraint("currency = 'INR'", name="inr_currency"),
        sa.CheckConstraint("status IN ('CREATING','CREATED','UNKNOWN','AUTHORIZED','CAPTURED','FAILED')", name="valid_payment_status"),
    )
    op.create_index("ix_payment_booking", "payment_transactions", ["booking_id"])
    op.create_table("payment_webhook_events",
        uid("id", primary_key=True), uid("config_id", nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_event_id", sa.String(200)),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("dedupe_key", sa.String(64), nullable=False, unique=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("provider_order_id", sa.String(100)),
        sa.Column("provider_payment_id", sa.String(100)),
        sa.Column("processing_status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.ForeignKeyConstraint(["config_id"], ["merchant_payment_configs.id"], ondelete="RESTRICT"),
    )


def downgrade():
    op.drop_table("payment_webhook_events")
    op.drop_table("payment_transactions")
    op.drop_table("merchant_payment_configs")
    op.drop_constraint("uq_booking_id_merchant", "bookings", type_="unique")
    op.drop_column("bookings", "payment_review_required")
    op.drop_column("bookings", "amount_paid")
    op.drop_column("bookings", "public_token_hash")
