from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer

from app.models import InvoiceJobStatus, InvoiceType, PaymentCondition


class MockApprovalInput(BaseModel):
    """Internal development mock contract, not a DingTalk official payload."""

    process_instance_id: str
    approval_no: str | None = None
    invoice_type: InvoiceType
    payment_condition: PaymentCondition
    seller_name: str
    buyer_name: str
    buyer_tax_no: str | None = None
    amount: Decimal
    invoice_content: str
    buyer_title_type: str | None = None
    requested_total_amount: Decimal | None = None
    line_items: list["InvoiceLineItemInput"] = []
    remark: str | None = None
    department: str | None = None
    approved_at: datetime
    ding_started_at: datetime | None = None
    ding_finished_at: datetime | None = None
    source_payload: dict | None = None


class InvoiceLineItemInput(BaseModel):
    line_no: int
    item_name: str
    quantity: Decimal
    amount: Decimal


class InvoiceLineItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_no: int
    item_name: str
    quantity: Decimal
    amount: Decimal


class InvoiceJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    process_instance_id: str
    approval_no: str | None
    invoice_type: InvoiceType
    payment_condition: PaymentCondition
    seller_name: str
    buyer_name: str
    buyer_tax_no: str | None
    amount: Decimal
    requested_total_amount: Decimal | None
    buyer_title_type: str | None
    invoice_content: str
    line_items: list[InvoiceLineItemRead]
    remark: str | None
    department: str | None
    approved_at: datetime
    ding_started_at: datetime | None
    ding_finished_at: datetime | None
    status: InvoiceJobStatus
    operator_id: str | None
    claimed_at: datetime | None
    started_at: datetime | None
    issued_at: datetime | None
    completed_at: datetime | None
    invoice_no: str | None
    last_error: str | None
    error_stage: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("amount", "requested_total_amount")
    def serialize_amount(self, amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        return f"{amount:.2f}"


class InvoiceJobSummary(BaseModel):
    pending: int
    processing: int
    completed: int
    exceptions: int
