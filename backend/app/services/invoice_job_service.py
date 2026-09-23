from datetime import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import InvoiceJob, InvoiceJobStatus
from app.models.invoice_job import utc_now


class InvoiceJobConflictError(Exception):
    pass


ALLOWED_TRANSITIONS = {
    InvoiceJobStatus.PENDING: {InvoiceJobStatus.CLAIMED},
    InvoiceJobStatus.CLAIMED: {InvoiceJobStatus.ISSUING, InvoiceJobStatus.ISSUE_FAILED},
    InvoiceJobStatus.ISSUING: {InvoiceJobStatus.WAITING_CONFIRMATION, InvoiceJobStatus.ISSUE_FAILED},
    InvoiceJobStatus.WAITING_CONFIRMATION: {InvoiceJobStatus.ISSUED, InvoiceJobStatus.UNKNOWN_RESULT},
    InvoiceJobStatus.ISSUED: {InvoiceJobStatus.UPLOADING},
    InvoiceJobStatus.UPLOADING: {InvoiceJobStatus.COMPLETED, InvoiceJobStatus.UPLOAD_FAILED},
}


class InvoiceJobService:
    def claim(self, session: Session, job_id: int, operator_id: str) -> InvoiceJob:
        now = utc_now()
        result = session.execute(
            update(InvoiceJob)
            .where(InvoiceJob.id == job_id, InvoiceJob.status == InvoiceJobStatus.PENDING)
            .values(status=InvoiceJobStatus.CLAIMED, operator_id=operator_id, claimed_at=now, updated_at=now)
        )
        if result.rowcount != 1:
            session.rollback()
            raise InvoiceJobConflictError("Invoice job is unavailable for claim")
        session.commit()
        return session.get(InvoiceJob, job_id)

    def transition(self, session: Session, job: InvoiceJob, target: InvoiceJobStatus) -> InvoiceJob:
        if target not in ALLOWED_TRANSITIONS.get(job.status, set()):
            raise InvoiceJobConflictError(f"Illegal transition: {job.status} -> {target}")
        now = utc_now()
        job.status = target
        job.updated_at = now
        if target == InvoiceJobStatus.ISSUING:
            job.started_at = now
        elif target == InvoiceJobStatus.ISSUED:
            job.issued_at = now
        elif target == InvoiceJobStatus.COMPLETED:
            job.completed_at = now
        session.commit()
        session.refresh(job)
        return job
