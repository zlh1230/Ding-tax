from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models import InvoiceJob, InvoiceLineItem, InvoiceJobStatus, InvoiceType, PaymentCondition
from app.services.canonical_invoice import CanonicalInvoiceValidationError, calculate_requested_total_amount, validate_amount_compatibility


def job() -> InvoiceJob:
    return InvoiceJob(process_instance_id="canonical-job", invoice_type=InvoiceType.SPECIAL, payment_condition=PaymentCondition.BEFORE_PAYMENT, seller_name="fake seller", buyer_name="fake buyer", buyer_tax_no="fake-tax", amount=Decimal("3.30"), requested_total_amount=Decimal("3.30"), invoice_content="legacy display", approved_at=datetime.now(timezone.utc), status=InvoiceJobStatus.PENDING)


def test_exact_decimal_total_for_multiple_lines():
    lines = [InvoiceLineItem(line_no=1, item_name="fake-a", quantity=Decimal("1.5"), amount=Decimal("1.10")), InvoiceLineItem(line_no=2, item_name="fake-b", quantity=Decimal("2"), amount=Decimal("2.20"))]
    assert calculate_requested_total_amount(lines) == Decimal("3.30")
    validate_amount_compatibility(Decimal("3.30"), Decimal("3.30"))


def test_empty_lines_and_non_decimal_amount_are_rejected():
    with pytest.raises(CanonicalInvoiceValidationError):
        calculate_requested_total_amount([])
    with pytest.raises(CanonicalInvoiceValidationError):
        calculate_requested_total_amount([{"amount": "1.00"}])
    with pytest.raises(CanonicalInvoiceValidationError):
        validate_amount_compatibility(Decimal("1.00"), Decimal("2.00"))


def test_line_numbers_are_unique_per_job_and_ordered():
    with SessionLocal() as session:
        stored = job()
        stored.line_items = [InvoiceLineItem(line_no=2, item_name="fake-b", quantity=Decimal("1"), amount=Decimal("2.00")), InvoiceLineItem(line_no=1, item_name="fake-a", quantity=Decimal("1"), amount=Decimal("1.30"))]
        session.add(stored)
        session.commit()
        session.refresh(stored)
        assert [line.line_no for line in stored.line_items] == [1, 2]
        session.add(InvoiceLineItem(invoice_job_id=stored.id, line_no=1, item_name="duplicate", quantity=Decimal("1"), amount=Decimal("1.00")))
        with pytest.raises(IntegrityError):
            session.commit()
