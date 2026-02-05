"""add beneficiary fields to payment

Revision ID: b2d91e7c4a10
Revises: f4b9a8c2d7e1
Create Date: 2026-01-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2d91e7c4a10"
down_revision = "f4b9a8c2d7e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payment", sa.Column("beneficiary_id", sa.Integer(), nullable=True))
    op.add_column("payment", sa.Column("beneficiary_name", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_payment_beneficiary_id_beneficiaries",
        "payment",
        "beneficiaries",
        ["beneficiary_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_payment_beneficiary_id_beneficiaries", "payment", type_="foreignkey")
    op.drop_column("payment", "beneficiary_name")
    op.drop_column("payment", "beneficiary_id")
