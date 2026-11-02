"""Add an optional name to existing and future waitlist entries.

Revision ID: a7d8c9012f34
Revises: f93a4c1236de
"""

import sqlalchemy as sa

from alembic import op

revision = "a7d8c9012f34"
down_revision = "f93a4c1236de"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("waitlist_entries", sa.Column("name", sa.String(120), nullable=True))


def downgrade():
    op.drop_column("waitlist_entries", "name")
