"""create invoice jobs

Revision ID: 20260916_01
Revises:
Create Date: 2026-09-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20260916_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("process_instance_id", sa.String(length=128), nullable=False),
        sa.Column("approval_no", sa.String(length=128)),
        sa.Column("invoice_type", sa.Enum("NORMAL", "SPECIAL", name="invoicetype", native_enum=False), nullable=False),
        sa.Column("payment_condition", sa.Enum("BEFORE_PAYMENT", "AFTER_PAYMENT", "OTHER", name="paymentcondition", native_enum=False), nullable=False),
        sa.Column("seller_name", sa.String(length=255), nullable=False),
        sa.Column("buyer_name", sa.String(length=255), nullable=False),
        sa.Column("buyer_tax_no", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("invoice_content", sa.String(length=500), nullable=False),
        sa.Column("remark", sa.Text()), sa.Column("department", sa.String(length=255)), sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "CLAIMED", "ISSUING", "WAITING_CONFIRMATION", "ISSUED", "UPLOADING", "COMPLETED", "ISSUE_FAILED", "UPLOAD_FAILED", "UNKNOWN_RESULT", name="invoicejobstatus", native_enum=False), nullable=False),
        sa.Column("operator_id", sa.String(length=128)), sa.Column("claimed_at", sa.DateTime(timezone=True)), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("issued_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("invoice_no", sa.String(length=128)), sa.Column("last_error", sa.Text()), sa.Column("error_stage", sa.String(length=64)), sa.Column("source_payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("process_instance_id"),
    )
    op.create_index("ix_invoice_jobs_process_instance_id", "invoice_jobs", ["process_instance_id"])
    op.create_index("ix_invoice_jobs_status", "invoice_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_invoice_jobs_status", table_name="invoice_jobs")
    op.drop_index("ix_invoice_jobs_process_instance_id", table_name="invoice_jobs")
    op.drop_table("invoice_jobs")
