"""add ext_biller_ref_id to payment

Revision ID: a1b2c3d4e5f6
Revises: c1e53695c925
Create Date: 2024-12-07 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'c1e53695c925'
branch_labels = None
depends_on = None


def upgrade():
    # Add ext_biller_ref_id column to payment table
    op.add_column('payment', sa.Column('ext_biller_ref_id', sa.String(), nullable=True))


def downgrade():
    # Remove ext_biller_ref_id column from payment table
    op.drop_column('payment', 'ext_biller_ref_id')
