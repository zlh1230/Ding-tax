import json
from decimal import Decimal, InvalidOperation

from app.integrations.dingtalk.schemas import DingTalkApprovalInstance
from app.models import InvoiceType, PaymentCondition
from app.schemas.invoice_job import InvoiceLineItemInput, MockApprovalInput
from app.services.canonical_invoice import calculate_requested_total_amount

DINGTALK_FIELD_MAP = {
    "invoice_type": "开票类型", "payment_condition": "票款情况", "seller_name": "收款公司",
    "buyer_name": "抬头名称", "buyer_title_type": "抬头类型", "buyer_tax_no": "公司税号",
    "line_items": "开票内容明细", "remark": "备注",
}
REQUIRED_FIELDS = ("invoice_type", "payment_condition", "seller_name", "buyer_title_type")


class ApprovalParseError(Exception):
    def __init__(self, code: str, process_instance_id: str, fields: list[str] | None = None):
        self.code, self.process_instance_id, self.fields = code, process_instance_id, fields or []
        super().__init__(code)


def redact_payload(value):
    if isinstance(value, dict):
        return {key: redact_payload("[REDACTED]" if any(term in key.lower() for term in ("token", "secret", "password")) else item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    return value


class DingTalkApprovalParser:
    def parse(self, instance: DingTalkApprovalInstance) -> MockApprovalInput:
        values = instance.form_values
        missing = [key for key in REQUIRED_FIELDS if not self._text(values.get(DINGTALK_FIELD_MAP[key]))]
        if missing:
            raise ApprovalParseError("MISSING_REQUIRED_FIELD", instance.process_instance_id, missing)
        buyer_name = self._text(values.get(DINGTALK_FIELD_MAP["buyer_name"]))
        if not buyer_name:
            raise ApprovalParseError("MISSING_BUYER_NAME", instance.process_instance_id, ["buyer_name"])
        try:
            line_items = self._line_items(values[DINGTALK_FIELD_MAP["line_items"]])
        except (KeyError, TypeError, ValueError, InvalidOperation, json.JSONDecodeError):
            raise ApprovalParseError("INVALID_LINE_ITEMS", instance.process_instance_id, ["line_items"])
        invoice_type = {"专票": InvoiceType.SPECIAL, "普票": InvoiceType.NORMAL}.get(self._text(values[DINGTALK_FIELD_MAP["invoice_type"]]))
        payment_condition = {"先开票再收款": PaymentCondition.BEFORE_PAYMENT, "先收款再开票": PaymentCondition.AFTER_PAYMENT, "款到开票": PaymentCondition.AFTER_PAYMENT}.get(self._text(values[DINGTALK_FIELD_MAP["payment_condition"]]))
        if not invoice_type or not payment_condition:
            raise ApprovalParseError("INVALID_FIELD_VALUE", instance.process_instance_id, ["invoice_type", "payment_condition"])
        if instance.approved_at is None:
            raise ApprovalParseError("INVALID_APPROVAL_TIME", instance.process_instance_id, ["approved_at"])
        total = calculate_requested_total_amount(line_items)
        return MockApprovalInput(process_instance_id=instance.process_instance_id, approval_no=instance.approval_no, invoice_type=invoice_type, payment_condition=payment_condition, seller_name=self._text(values[DINGTALK_FIELD_MAP["seller_name"]]), buyer_name=buyer_name, buyer_title_type=self._text(values[DINGTALK_FIELD_MAP["buyer_title_type"]]), buyer_tax_no=self._text(values.get(DINGTALK_FIELD_MAP["buyer_tax_no"])) or None, amount=total, requested_total_amount=total, line_items=line_items, invoice_content=line_items[0].item_name, remark=self._text(values.get(DINGTALK_FIELD_MAP["remark"])) or None, approved_at=instance.approved_at, ding_started_at=instance.started_at, ding_finished_at=instance.finished_at or instance.approved_at, source_payload=redact_payload(instance.source_payload))

    @staticmethod
    def _text(value: object) -> str:
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _line_items(raw: str) -> list[InvoiceLineItemInput]:
        rows = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(rows, list) or not rows:
            raise ValueError("line items are required")
        items = []
        for line_no, row in enumerate(rows, start=1):
            cells = {cell["label"]: cell.get("value") for cell in row["rowValue"]}
            item_name = str(cells["开票内容"]).strip()
            quantity = Decimal(str(cells["数量"]).replace(",", "").strip())
            amount = Decimal(str(cells["金额（元）"]).replace(",", "").strip())
            if not item_name:
                raise ValueError("line item name is required")
            items.append(InvoiceLineItemInput(line_no=line_no, item_name=item_name, quantity=quantity, amount=amount))
        return items
