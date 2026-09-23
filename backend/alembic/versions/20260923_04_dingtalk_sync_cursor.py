"""store DingTalk approval times and successful sync cursor

Revision ID: 20260923_04
Revises: 20260917_03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260923_04"
down_revision = "20260917_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoice_jobs", sa.Column("ding_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoice_jobs", sa.Column("ding_finished_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_invoice_jobs_ding_started_at", "invoice_jobs", ["ding_started_at"])
    op.create_index("ix_invoice_jobs_ding_finished_at", "invoice_jobs", ["ding_finished_at"])
    op.create_table(
        "dingtalk_sync_state",
        sa.Column("process_code", sa.String(length=128), primary_key=True),
        sa.Column("last_successful_dingtalk_sync_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("dingtalk_sync_state")
    op.drop_index("ix_invoice_jobs_ding_finished_at", table_name="invoice_jobs")
    op.drop_index("ix_invoice_jobs_ding_started_at", table_name="invoice_jobs")
    op.drop_column("invoice_jobs", "ding_finished_at")
    op.drop_column("invoice_jobs", "ding_started_at")
