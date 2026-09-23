"""make buyer tax number optional

Revision ID: 20260917_03
Revises: 20260917_02
"""

from alembic import op
import sqlalchemy as sa

revision = "20260917_03"
down_revision = "20260917_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("invoice_jobs") as batch:
        batch.alter_column("buyer_tax_no", existing_type=sa.String(length=64), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("invoice_jobs") as batch:
        batch.alter_column("buyer_tax_no", existing_type=sa.String(length=64), nullable=False)
