from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import JSON, CheckConstraint, DateTime, Enum as SqlEnum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InvoiceJobStatus(str, Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    ISSUING = "ISSUING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    ISSUED = "ISSUED"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    ISSUE_FAILED = "ISSUE_FAILED"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"


class InvoiceType(str, Enum):
    NORMAL = "NORMAL"
    SPECIAL = "SPECIAL"


class PaymentCondition(str, Enum):
    BEFORE_PAYMENT = "BEFORE_PAYMENT"
    AFTER_PAYMENT = "AFTER_PAYMENT"
    OTHER = "OTHER"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InvoiceJob(Base):
    __tablename__ = "invoice_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), default="DINGTALK", nullable=False)
    process_instance_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    approval_no: Mapped[str | None] = mapped_column(String(128))
    invoice_type: Mapped[InvoiceType] = mapped_column(SqlEnum(InvoiceType, native_enum=False), nullable=False)
    payment_condition: Mapped[PaymentCondition] = mapped_column(SqlEnum(PaymentCondition, native_enum=False), nullable=False)
    seller_name: Mapped[str] = mapped_column(String(255), nullable=False)
    buyer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    buyer_tax_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    requested_total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    buyer_title_type: Mapped[str | None] = mapped_column(String(64))
    invoice_content: Mapped[str] = mapped_column(String(500), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ding_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ding_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[InvoiceJobStatus] = mapped_column(SqlEnum(InvoiceJobStatus, native_enum=False), default=InvoiceJobStatus.PENDING, nullable=False, index=True)
    operator_id: Mapped[str | None] = mapped_column(String(128))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invoice_no: Mapped[str | None] = mapped_column(String(128))
    last_error: Mapped[str | None] = mapped_column(Text)
    error_stage: Mapped[str | None] = mapped_column(String(64))
    source_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    line_items: Mapped[list["InvoiceLineItem"]] = relationship(back_populates="invoice_job", order_by="InvoiceLineItem.line_no")


class DingTalkSyncState(Base):
    __tablename__ = "dingtalk_sync_state"

    process_code: Mapped[str] = mapped_column(String(128), primary_key=True)
    last_successful_dingtalk_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"
    __table_args__ = (CheckConstraint("line_no >= 1", name="ck_invoice_line_items_line_no"), UniqueConstraint("invoice_job_id", "line_no", name="uq_invoice_line_items_job_line"))

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_job_id: Mapped[int] = mapped_column(ForeignKey("invoice_jobs.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(nullable=False)
    item_name: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    invoice_job: Mapped[InvoiceJob] = relationship(back_populates="line_items")
