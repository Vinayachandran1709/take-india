"""Add the independent typein early-access waitlist.

Revision ID: f93a4c1236de
Revises: e82f3b0125cd
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f93a4c1236de"
down_revision = "e82f3b0125cd"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "waitlist_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("whatsapp", sa.String(16), nullable=False),
        sa.Column("business_type", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "consented_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_waitlist_entries"),
        sa.UniqueConstraint("whatsapp", name="uq_waitlist_entries_whatsapp"),
    )


def downgrade():
    op.drop_table("waitlist_entries")
