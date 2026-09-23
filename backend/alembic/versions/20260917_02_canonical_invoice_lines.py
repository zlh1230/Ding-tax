"""add canonical invoice lines

Revision ID: 20260917_02
Revises: 20260916_01
"""

from alembic import op
import sqlalchemy as sa

revision = "20260917_02"
down_revision = "20260916_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoice_jobs", sa.Column("requested_total_amount", sa.Numeric(18, 2), nullable=True))
    op.add_column("invoice_jobs", sa.Column("buyer_title_type", sa.String(length=64), nullable=True))
    op.execute("UPDATE invoice_jobs SET requested_total_amount = amount WHERE requested_total_amount IS NULL")
    op.create_table("invoice_line_items", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("invoice_job_id", sa.Integer(), sa.ForeignKey("invoice_jobs.id"), nullable=False), sa.Column("line_no", sa.Integer(), nullable=False), sa.Column("item_name", sa.String(length=500), nullable=False), sa.Column("quantity", sa.Numeric(18, 4), nullable=False), sa.Column("amount", sa.Numeric(18, 2), nullable=False), sa.CheckConstraint("line_no >= 1", name="ck_invoice_line_items_line_no"), sa.UniqueConstraint("invoice_job_id", "line_no", name="uq_invoice_line_items_job_line"))
    op.create_index("ix_invoice_line_items_invoice_job_id", "invoice_line_items", ["invoice_job_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_line_items_invoice_job_id", table_name="invoice_line_items")
    op.drop_table("invoice_line_items")
    with op.batch_alter_table("invoice_jobs") as batch:
        batch.drop_column("buyer_title_type")
        batch.drop_column("requested_total_amount")
