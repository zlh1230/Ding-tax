from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import APP_ENV
from app.core.database import get_db
from app.api.auth import CurrentOperator, require_operator
from app.models import InvoiceJob, InvoiceJobStatus
from app.schemas.invoice_job import InvoiceJobRead, InvoiceJobSummary
from app.services.invoice_job_service import InvoiceJobConflictError, InvoiceJobService
from app.services.mock_approvals import import_mock_approvals

router = APIRouter(prefix="/api", tags=["invoice-jobs"])


def development_only() -> None:
    if APP_ENV != "development":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.get("/invoice-jobs", response_model=list[InvoiceJobRead])
def list_invoice_jobs(status: InvoiceJobStatus | None = None, current_operator: CurrentOperator = Depends(require_operator), db: Session = Depends(get_db)):
    query = select(InvoiceJob).order_by(InvoiceJob.ding_finished_at.desc(), InvoiceJob.created_at.desc())
    if status:
        query = query.where(InvoiceJob.status == status)
    return db.scalars(query).all()


@router.get("/invoice-jobs/summary", response_model=InvoiceJobSummary)
def invoice_job_summary(current_operator: CurrentOperator = Depends(require_operator), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(InvoiceJob.status, func.count()).group_by(InvoiceJob.status)).all())
    return InvoiceJobSummary(
        pending=counts.get(InvoiceJobStatus.PENDING, 0),
        processing=sum(counts.get(item, 0) for item in (InvoiceJobStatus.CLAIMED, InvoiceJobStatus.ISSUING, InvoiceJobStatus.WAITING_CONFIRMATION, InvoiceJobStatus.ISSUED, InvoiceJobStatus.UPLOADING)),
        completed=counts.get(InvoiceJobStatus.COMPLETED, 0),
        exceptions=sum(counts.get(item, 0) for item in (InvoiceJobStatus.ISSUE_FAILED, InvoiceJobStatus.UPLOAD_FAILED, InvoiceJobStatus.UNKNOWN_RESULT)),
    )


@router.get("/invoice-jobs/{job_id}", response_model=InvoiceJobRead)
def get_invoice_job(job_id: int, current_operator: CurrentOperator = Depends(require_operator), db: Session = Depends(get_db)):
    job = db.get(InvoiceJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice job not found")
    return job


@router.post("/invoice-jobs/{job_id}/claim", response_model=InvoiceJobRead)
def claim_invoice_job(job_id: int, current_operator: CurrentOperator = Depends(require_operator), db: Session = Depends(get_db)):
    development_only()
    try:
        return InvoiceJobService().claim(db, job_id, current_operator.user_id)
    except InvoiceJobConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post("/dev/mock-approvals/import")
def import_development_mock_approvals(db: Session = Depends(get_db)):
    development_only()
    return import_mock_approvals(db)
