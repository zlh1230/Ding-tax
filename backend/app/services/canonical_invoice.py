from decimal import Decimal


class CanonicalInvoiceValidationError(ValueError):
    pass


def calculate_requested_total_amount(line_items) -> Decimal:
    if not line_items:
        raise CanonicalInvoiceValidationError("At least one line item is required")
    total = Decimal("0")
    for item in line_items:
        amount = item.amount if hasattr(item, "amount") else item["amount"]
        if not isinstance(amount, Decimal):
            raise CanonicalInvoiceValidationError("Line item amount must be Decimal")
        total += amount
    return total


def validate_amount_compatibility(amount: Decimal, requested_total_amount: Decimal) -> None:
    if amount != requested_total_amount:
        raise CanonicalInvoiceValidationError("Legacy amount must equal requested total amount")
