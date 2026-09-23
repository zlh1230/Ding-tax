from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InvoiceJob, InvoiceJobStatus, InvoiceLineItem
from app.schemas.invoice_job import MockApprovalInput


class DingTalkApprovalIngestionService:
    """Maps the internal development mock contract to an invoice job."""

    def ingest(self, session: Session, approval: MockApprovalInput) -> tuple[InvoiceJob, bool]:
        job, outcome = self.upsert(session, approval)
        return job, outcome == "created"

    def upsert(self, session: Session, approval: MockApprovalInput) -> tuple[InvoiceJob, str]:
        existing = session.query(InvoiceJob).filter_by(process_instance_id=approval.process_instance_id).one_or_none()
        if existing:
            if existing.status != InvoiceJobStatus.PENDING or not self._changed(existing, approval):
                return existing, "already_exists"
            self._apply(existing, approval)
            for line_item in list(existing.line_items):
                session.delete(line_item)
            session.flush()
            existing.line_items = self._line_items(approval)
            session.commit()
            session.refresh(existing)
            return existing, "updated_pending"
        job = InvoiceJob(
            source="DINGTALK",
            process_instance_id=approval.process_instance_id,
            approval_no=approval.approval_no,
            invoice_type=approval.invoice_type,
            payment_condition=approval.payment_condition,
            seller_name=approval.seller_name,
            buyer_name=approval.buyer_name,
            buyer_tax_no=approval.buyer_tax_no,
            amount=approval.amount,
            requested_total_amount=approval.requested_total_amount or approval.amount,
            buyer_title_type=approval.buyer_title_type,
            invoice_content=approval.invoice_content,
            remark=approval.remark,
            department=approval.department,
            approved_at=approval.approved_at,
            ding_started_at=approval.ding_started_at,
            ding_finished_at=approval.ding_finished_at,
            status=InvoiceJobStatus.PENDING,
            source_payload=approval.source_payload or approval.model_dump(mode="json"),
        )
        job.line_items = self._line_items(approval)
        session.add(job)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return session.query(InvoiceJob).filter_by(process_instance_id=approval.process_instance_id).one(), "already_exists"
        session.refresh(job)
        return job, "created"

    @staticmethod
    def _line_items(approval: MockApprovalInput) -> list[InvoiceLineItem]:
        return [InvoiceLineItem(line_no=line.line_no, item_name=line.item_name, quantity=line.quantity, amount=line.amount) for line in approval.line_items]

    @staticmethod
    def _changed(job: InvoiceJob, approval: MockApprovalInput) -> bool:
        values = ("approval_no", "invoice_type", "payment_condition", "seller_name", "buyer_name", "buyer_tax_no", "amount", "requested_total_amount", "buyer_title_type", "invoice_content", "remark", "department", "approved_at", "ding_started_at", "ding_finished_at")
        if any(DingTalkApprovalIngestionService._comparison_value(getattr(job, name)) != DingTalkApprovalIngestionService._comparison_value(getattr(approval, name)) for name in values):
            return True
        return [(line.line_no, line.item_name, line.quantity, line.amount) for line in job.line_items] != [(line.line_no, line.item_name, line.quantity, line.amount) for line in approval.line_items]

    @staticmethod
    def _comparison_value(value):
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
        return value

    @staticmethod
    def _apply(job: InvoiceJob, approval: MockApprovalInput) -> None:
        for name in ("approval_no", "invoice_type", "payment_condition", "seller_name", "buyer_name", "buyer_tax_no", "amount", "requested_total_amount", "buyer_title_type", "invoice_content", "remark", "department", "approved_at", "ding_started_at", "ding_finished_at"):
            setattr(job, name, getattr(approval, name))
        job.source_payload = approval.source_payload or approval.model_dump(mode="json")
