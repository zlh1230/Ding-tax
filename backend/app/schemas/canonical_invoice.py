from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models import InvoiceType, PaymentCondition


class CanonicalInvoiceLineItem(BaseModel):
    line_no: int
    item_name: str
    quantity: Decimal
    amount: Decimal


class CanonicalInvoiceApplication(BaseModel):
    process_instance_id: str
    approval_no: str | None
    approved_at: datetime
    seller_name: str
    payment_condition: PaymentCondition
    buyer_title_type: str
    buyer_name: str | None
    buyer_tax_no: str | None
    invoice_type: InvoiceType
    requested_total_amount: Decimal
    line_items: list[CanonicalInvoiceLineItem]
    remark: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    buyer_address: str | None = None
    buyer_phone: str | None = None
