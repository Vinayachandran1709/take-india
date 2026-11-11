"""Remember the first failed recurring charge for a fixed grace deadline.

Revision ID: d4c2e6a91b70
Revises: b7e3f29c41aa
"""

import sqlalchemy as sa
from alembic import op

revision = "d4c2e6a91b70"
down_revision = "b7e3f29c41aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("merchants", sa.Column("billing_delinquent_at", sa.DateTime(timezone=True)))
    # Existing past-due rows had no grace tracking. Keep their current locked
    # behavior rather than silently granting a new grace window.


def downgrade() -> None:
    op.drop_column("merchants", "billing_delinquent_at")
