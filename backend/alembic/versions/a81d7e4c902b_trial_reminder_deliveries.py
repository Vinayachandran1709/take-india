"""Record each trial notice once per merchant and reminder kind.

Revision ID: a81d7e4c902b
Revises: f6a2c1e9d803
"""

import sqlalchemy as sa

from alembic import op

revision = "a81d7e4c902b"
down_revision = "f6a2c1e9d803"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trial_reminder_deliveries",
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("provider_message_id", sa.String(120)),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("merchant_id", "kind"),
        sa.CheckConstraint(
            "kind IN ('three_days', 'one_day', 'ended')", name="trial_reminder_kind"
        ),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name="trial_reminder_status"),
        sa.CheckConstraint("attempt_count >= 0", name="trial_reminder_attempts_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("trial_reminder_deliveries")
