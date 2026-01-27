"""add reference to payment

Revision ID: f4b9a8c2d7e1
Revises: a1b2c3d4e5f6
Create Date: 2026-01-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f4b9a8c2d7e1"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payment", sa.Column("reference", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("payment", "reference")
