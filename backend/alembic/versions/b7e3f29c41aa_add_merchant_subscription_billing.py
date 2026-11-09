"""Add merchant subscription billing without changing booking payment tables.

Revision ID: b7e3f29c41aa
Revises: c6b2e4d9108a
"""

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b7e3f29c41aa"
down_revision = "c6b2e4d9108a"
branch_labels = None
depends_on = None


def upgrade():
    trial_days = int(os.environ.get("BILLING_TRIAL_DAYS", "30"))
    if not 0 <= trial_days <= 3650:
        raise ValueError("BILLING_TRIAL_DAYS must be between 0 and 3650")

    op.add_column("merchants", sa.Column("trial_ends_at", sa.DateTime(timezone=True)))
    op.add_column(
        "merchants",
        sa.Column("subscription_status", sa.String(20), nullable=False, server_default="trialing"),
    )
    op.add_column("merchants", sa.Column("razorpay_subscription_id", sa.String(80)))
    op.add_column("merchants", sa.Column("current_period_end", sa.DateTime(timezone=True)))
    op.add_column(
        "merchants",
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("merchants", sa.Column("checkout_confirmed_at", sa.DateTime(timezone=True)))
    op.add_column("merchants", sa.Column("subscription_authenticated_at", sa.DateTime(timezone=True)))
    op.execute(
        sa.text(f"UPDATE merchants SET trial_ends_at = CURRENT_TIMESTAMP + INTERVAL '{trial_days} days'")
    )
    op.alter_column("merchants", "trial_ends_at", nullable=False)
    op.create_unique_constraint(
        "uq_merchants_razorpay_subscription_id", "merchants", ["razorpay_subscription_id"]
    )
    op.create_check_constraint(
        "ck_merchants_merchant_subscription_status",
        "merchants",
        "subscription_status IN ('trialing', 'active', 'past_due', 'expired', 'cancelled')",
    )

    op.create_table(
        "billing_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("razorpay_payment_id", sa.String(80), nullable=False),
        sa.Column("razorpay_subscription_id", sa.String(80), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("razorpay_payment_id", name="uq_billing_payments_razorpay_payment_id"),
        sa.CheckConstraint("amount_paise >= 0", name="ck_billing_payments_amount_nonnegative"),
    )
    op.create_index("ix_billing_payments_merchant_created", "billing_payments", ["merchant_id", "created_at"])

    op.create_table(
        "billing_webhook_events",
        sa.Column("event_id", sa.String(120), primary_key=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("subscription_id", sa.String(80)),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("processing_status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(60)),
        sa.Column("event_created_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_billing_webhook_events_subscription_created",
        "billing_webhook_events", ["subscription_id", "event_created_at"]
    )


def downgrade():
    op.drop_index("ix_billing_webhook_events_subscription_created", table_name="billing_webhook_events")
    op.drop_table("billing_webhook_events")
    op.drop_index("ix_billing_payments_merchant_created", table_name="billing_payments")
    op.drop_table("billing_payments")
    op.drop_constraint("ck_merchants_merchant_subscription_status", "merchants", type_="check")
    op.drop_constraint("uq_merchants_razorpay_subscription_id", "merchants", type_="unique")
    op.drop_column("merchants", "checkout_confirmed_at")
    op.drop_column("merchants", "subscription_authenticated_at")
    op.drop_column("merchants", "cancel_at_period_end")
    op.drop_column("merchants", "current_period_end")
    op.drop_column("merchants", "razorpay_subscription_id")
    op.drop_column("merchants", "subscription_status")
    op.drop_column("merchants", "trial_ends_at")
